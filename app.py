from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional
import os

import db
import notifications

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is missing or invalid."
        )
    token = authorization.split(" ")[1]
    user = db.get_user_by_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token."
        )
    return user


app = FastAPI(title="Calendar Meeting Poll API")

# Enable CORS so frontend can communicate with backend locally if run on a different port/host
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schemas
class TimeSlot(BaseModel):
    id: str
    start_time: str # ISO formatted string (UTC)
    end_time: str # ISO formatted string (UTC)

class PollCreate(BaseModel):
    poll_type: str = "group" # "group" or "one_on_one"
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""
    duration: str # e.g. "15", "30", "60", "Custom (45)"
    timezone: str = "UTC"
    organizer_name: str = Field(..., min_length=1)
    organizer_email: EmailStr
    slots: List[TimeSlot]
    invite_emails: Optional[List[str]] = []

class VoteSubmit(BaseModel):
    voter_name: str = Field(..., min_length=1)
    voter_email: EmailStr
    choices: Dict[str, str] # slot_id -> "yes" | "no" | "if_need_be"

class FinalizeRequest(BaseModel):
    slot_id: Optional[str] = None # Slot ID to finalize, or None to clear

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Authentication routes
@app.post("/api/auth/register")
def register_user(req: RegisterRequest):
    user = db.create_user(req.email, req.password, req.name)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )
    return {"message": "Account created successfully. Please sign in."}

@app.post("/api/auth/login")
def login_user(req: LoginRequest):
    token = db.authenticate_user(req.email, req.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password."
        )
    user = db.get_user(req.email)
    return {
        "session_token": token,
        "user": {
            "email": user["email"],
            "name": user["name"]
        }
    }

@app.post("/api/auth/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        db.delete_session(token)
    return {"message": "Logged out successfully."}

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "name": current_user["name"]
    }

@app.get("/api/my-polls")
def get_user_polls_route(current_user: dict = Depends(get_current_user)):
    return db.get_user_polls(current_user["email"])

@app.post("/api/polls", status_code=status.HTTP_201_CREATED)
def create_new_poll(poll: PollCreate, background_tasks: BackgroundTasks, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in to create a poll."
        )
    token = authorization.split(" ")[1]
    user = db.get_user_by_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again."
        )
        
    if not poll.slots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one time slot must be provided."
        )
        
    poll_dict = poll.dict()
    poll_dict["organizer_email"] = user["email"]
    poll_dict["organizer_name"] = user["name"]
    
    created_poll = db.create_poll(poll_dict)
    db.link_poll_to_user(user["email"], created_poll["id"])
    
    if poll.invite_emails:
        background_tasks.add_task(
            notifications.send_invite_emails,
            created_poll["id"],
            created_poll["title"],
            created_poll["organizer_name"],
            poll.invite_emails
        )
    return created_poll

@app.get("/api/polls/{poll_id}")
def get_poll_details(poll_id: str):
    poll = db.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found"
        )
    return poll

@app.post("/api/polls/{poll_id}/vote")
def submit_poll_vote(poll_id: str, vote: VoteSubmit, background_tasks: BackgroundTasks):
    poll = db.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found"
        )
    
    if poll.get("finalized_slot_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This poll has already been finalized and is locked."
        )
        
    # Verify voter provided choices for valid slots
    valid_slot_ids = {s["id"] for s in poll["slots"]}
    for slot_id in vote.choices:
        if slot_id not in valid_slot_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid slot ID: {slot_id}"
            )
            
    # Verify all choices are valid
    valid_choices = {"yes", "no", "if_need_be"}
    for choice in vote.choices.values():
        if choice not in valid_choices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid choice '{choice}'. Must be 'yes', 'no', or 'if_need_be'."
            )
            
    updated_poll = db.submit_vote(poll_id, vote.dict())
    
    # Schedule email notification to the organizer in the background
    background_tasks.add_task(notifications.send_vote_notification, updated_poll, vote.dict())
    
    return updated_poll

@app.post("/api/polls/{poll_id}/finalize")
def finalize_poll_meeting(poll_id: str, req: FinalizeRequest, authorization: Optional[str] = Header(None)):
    poll = db.get_poll(poll_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found"
        )
        
    # Verify authorization and owner
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must be logged in to finalize this meeting."
        )
    token = authorization.split(" ")[1]
    user = db.get_user_by_session(token)
    if not user or user["email"].lower() != poll["organizer_email"].lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organizer who created this poll can finalize it."
        )
        
    updated_poll = db.finalize_poll(poll_id, req.slot_id)
    if not updated_poll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid slot ID selected for finalization."
        )
    return updated_poll

# Serve static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure static directory exists
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Calendar Meeting Poll API is running. Please add an index.html in {STATIC_DIR}."}

@app.get("/poll/{poll_id}")
def view_poll_route(poll_id: str):
    # Route helper to redirect voter or organizer to frontend SPA page
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Calendar Poll {poll_id}. Frontend static folder is missing index.html in {STATIC_DIR}."}
