import json
import os
import uuid
import hashlib
import secrets
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
        "invite_emails": poll_data.get("invite_emails", []), # List of strings
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

def hash_password(password: str, salt: bytes = None) -> tuple:
    if salt is None:
        salt = secrets.token_bytes(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return pwd_hash.hex(), salt.hex()

def create_user(email: str, password_plain: str, name: str) -> Optional[dict]:
    email = email.lower().strip()
    if get_user(email):
        return None
        
    pwd_hash, salt = hash_password(password_plain)
    user = {
        "email": email,
        "password_hash": pwd_hash,
        "salt": salt,
        "name": name.strip(),
        "created_at": datetime.utcnow().isoformat()
    }
    
    if r_client:
        r_client.set(f"user:{email}", json.dumps(user))
    else:
        db = _read_db()
        if "__users__" not in db:
            db["__users__"] = {}
        db["__users__"][email] = user
        db["__users__"][email]["polls"] = []
        _write_db(db)
        
    return user

def get_user(email: str) -> Optional[dict]:
    email = email.lower().strip()
    if r_client:
        user_str = r_client.get(f"user:{email}")
        if user_str:
            return json.loads(user_str)
        return None
    else:
        db = _read_db()
        return db.get("__users__", {}).get(email)

def authenticate_user(email: str, password_plain: str) -> Optional[str]:
    email = email.lower().strip()
    user = get_user(email)
    if not user:
        return None
        
    pwd_hash, _ = hash_password(password_plain, bytes.fromhex(user["salt"]))
    if pwd_hash != user["password_hash"]:
        return None
        
    token = str(uuid.uuid4())
    
    if r_client:
        r_client.setex(f"session:{token}", 604800, email)
    else:
        db = _read_db()
        if "__sessions__" not in db:
            db["__sessions__"] = {}
        db["__sessions__"][token] = email
        _write_db(db)
        
    return token

def get_user_by_session(token: str) -> Optional[dict]:
    if not token:
        return None
        
    if r_client:
        email = r_client.get(f"session:{token}")
        if email:
            return get_user(email)
        return None
    else:
        db = _read_db()
        email = db.get("__sessions__", {}).get(token)
        if email:
            return get_user(email)
        return None

def delete_session(token: str):
    if r_client:
        r_client.delete(f"session:{token}")
    else:
        db = _read_db()
        if "__sessions__" in db and token in db["__sessions__"]:
            del db["__sessions__"][token]
            _write_db(db)

def link_poll_to_user(email: str, poll_id: str):
    email = email.lower().strip()
    if r_client:
        r_client.sadd(f"user:{email}:polls", poll_id)
    else:
        db = _read_db()
        if "__users__" in db and email in db["__users__"]:
            if "polls" not in db["__users__"][email]:
                db["__users__"][email]["polls"] = []
            if poll_id not in db["__users__"][email]["polls"]:
                db["__users__"][email]["polls"].append(poll_id)
            _write_db(db)

def get_user_polls(email: str) -> List[dict]:
    email = email.lower().strip()
    poll_ids = []
    if r_client:
        poll_ids = list(r_client.smembers(f"user:{email}:polls"))
    else:
        db = _read_db()
        if "__users__" in db and email in db["__users__"]:
            poll_ids = db["__users__"][email].get("polls", [])
            
    polls = []
    for pid in poll_ids:
        poll = get_poll(pid)
        if poll:
            polls.append(poll)
    return polls
