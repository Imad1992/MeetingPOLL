import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Support Vercel KV / Redis if configured in the environment
KV_URL = os.environ.get("KV_URL") or os.environ.get("REDIS_URL")

if KV_URL:
    import redis
    # Using decode_responses=True ensures we get native string types back from Redis
    r_client = redis.from_url(KV_URL, decode_responses=True)
else:
    r_client = None

# Determine database file location based on environment
# Vercel's serverless runtime is read-only except for /tmp.
IS_VERCEL = "VERCEL" in os.environ or os.environ.get("VERCEL") == "1"

if IS_VERCEL and not KV_URL:
    # Use /tmp as ephemeral fallback so the website works immediately for testing without KV linked
    DB_FILE = "/tmp/polls_db.json"
else:
    DB_FILE = os.path.join(BASE_DIR, "polls_db.json")

def _init_db():
    if r_client:
        return
    if not os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "w") as f:
                json.dump({}, f)
        except Exception:
            pass

def _read_db() -> Dict:
    _init_db()
    if r_client:
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_db(data: Dict):
    if r_client:
        return
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def create_poll(poll_data: dict) -> dict:
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
    
    if r_client:
        r_client.set(f"poll:{poll_id}", json.dumps(poll))
    else:
        db = _read_db()
        db[poll_id] = poll
        _write_db(db)
        
    return poll

def get_poll(poll_id: str) -> Optional[dict]:
    if r_client:
        poll_str = r_client.get(f"poll:{poll_id}")
        if poll_str:
            return json.loads(poll_str)
        return None
    else:
        db = _read_db()
        return db.get(poll_id)

def submit_vote(poll_id: str, vote_data: dict) -> Optional[dict]:
    poll = get_poll(poll_id)
    if not poll:
        return None
    
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

    if r_client:
        r_client.set(f"poll:{poll_id}", json.dumps(poll))
    else:
        db = _read_db()
        db[poll_id] = poll
        _write_db(db)
        
    return poll

def finalize_poll(poll_id: str, slot_id: str) -> Optional[dict]:
    poll = get_poll(poll_id)
    if not poll:
        return None
    
    # Check if the slot_id is valid
    valid_slots = [s["id"] for s in poll["slots"]]
    if slot_id not in valid_slots and slot_id is not None:
        return None
        
    poll["finalized_slot_id"] = slot_id
    
    if r_client:
        r_client.set(f"poll:{poll_id}", json.dumps(poll))
    else:
        db = _read_db()
        db[poll_id] = poll
        _write_db(db)
        
    return poll
