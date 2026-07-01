import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "polls_db.json")

def _init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f)

def _read_db() -> Dict:
    _init_db()
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def _write_db(data: Dict):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def create_poll(poll_data: dict) -> dict:
    db = _read_db()
    poll_id = str(uuid.uuid4())
    
    poll = {
        "id": poll_id,
        "poll_type": poll_data.get("poll_type", "group"),
        "title": poll_data.get("title", ""),
        "description": poll_data.get("description", ""),
        "duration": poll_data.get("duration", "30"),
        "timezone": poll_data.get("timezone", "UTC"),
        "organizer_name": poll_data.get("organizer_name", ""),
        "organizer_email": poll_data.get("organizer_email", ""),
        "slots": poll_data.get("slots", []), # List of dicts: {"id": str, "start_time": str(ISO), "end_time": str(ISO)}
        "votes": [], # List of dicts: {"voter_name": str, "voter_email": str, "choices": dict}
        "finalized_slot_id": None,
        "created_at": datetime.utcnow().isoformat()
    }
    
    db[poll_id] = poll
    _write_db(db)
    return poll

def get_poll(poll_id: str) -> Optional[dict]:
    db = _read_db()
    return db.get(poll_id)

def submit_vote(poll_id: str, vote_data: dict) -> Optional[dict]:
    db = _read_db()
    if poll_id not in db:
        return None
    
    poll = db[poll_id]
    
    # Check if this voter has already voted, if so, update their vote.
    voter_name = vote_data.get("voter_name", "").strip()
    voter_email = vote_data.get("voter_email", "").strip()
    choices = vote_data.get("choices", {}) # dict of slot_id -> choice ("yes", "no", "if_need_be")
    
    existing_vote_idx = -1
    for idx, v in enumerate(poll["votes"]):
        if v["voter_name"].lower() == voter_name.lower() and v["voter_email"].lower() == voter_email.lower():
            existing_vote_idx = idx
            break
            
    new_vote = {
        "voter_name": voter_name,
        "voter_email": voter_email,
        "choices": choices,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if existing_vote_idx != -1:
        poll["votes"][existing_vote_idx] = new_vote
    else:
        poll["votes"].append(new_vote)
        
    # Auto-finalize if it is a 1-on-1 poll and voter said "yes" to a slot
    if poll.get("poll_type") == "one_on_one":
        for slot_id, choice in choices.items():
            if choice == "yes":
                poll["finalized_slot_id"] = slot_id
                break

    db[poll_id] = poll
    _write_db(db)
    return poll

def finalize_poll(poll_id: str, slot_id: str) -> Optional[dict]:
    db = _read_db()
    if poll_id not in db:
        return None
        
    poll = db[poll_id]
    
    # Check if the slot_id is valid
    valid_slots = [s["id"] for s in poll["slots"]]
    if slot_id not in valid_slots and slot_id is not None:
        return None
        
    poll["finalized_slot_id"] = slot_id
    db[poll_id] = poll
    _write_db(db)
    return poll
