import sys
import os

# Ensure the workspace is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app import app
import db

client = TestClient(app)

def test_full_poll_flow():
    # Clean up previous db file if exists
    if os.path.exists(db.DB_FILE):
        os.remove(db.DB_FILE)
        
    print("1. Creating a poll...")
    poll_payload = {
        "title": "Weekly Planning Meeting",
        "description": "Align on current objectives and tasks",
        "duration": "30",
        "timezone": "America/New_York",
        "organizer_name": "Alice Smith",
        "organizer_email": "alice@example.com",
        "slots": [
            {"id": "slot-1", "start_time": "2026-07-06T14:00:00Z", "end_time": "2026-07-06T14:30:00Z"},
            {"id": "slot-2", "start_time": "2026-07-07T15:00:00Z", "end_time": "2026-07-07T15:30:00Z"}
        ]
    }
    
    response = client.post("/api/polls", json=poll_payload)
    assert response.status_code == 201, f"Failed creation: {response.text}"
    created_poll = response.json()
    assert created_poll["title"] == "Weekly Planning Meeting"
    assert created_poll["duration"] == "30"
    assert len(created_poll["slots"]) == 2
    poll_id = created_poll["id"]
    print(f"   Success! Poll ID: {poll_id}")
    
    print("\n2. Getting poll details...")
    response = client.get(f"/api/polls/{poll_id}")
    assert response.status_code == 200
    fetched_poll = response.json()
    assert fetched_poll["id"] == poll_id
    print("   Success!")
    
    print("\n3. Voting on the poll...")
    vote_payload = {
        "voter_name": "Bob Jones",
        "voter_email": "bob@example.com",
        "choices": {
            "slot-1": "yes",
            "slot-2": "if_need_be"
        }
    }
    response = client.post(f"/api/polls/{poll_id}/vote", json=vote_payload)
    assert response.status_code == 200
    voted_poll = response.json()
    assert len(voted_poll["votes"]) == 1
    assert voted_poll["votes"][0]["voter_name"] == "Bob Jones"
    assert voted_poll["votes"][0]["choices"]["slot-1"] == "yes"
    print("   Success!")
    
    print("\n4. Submitting a second vote...")
    vote_payload_2 = {
        "voter_name": "Charlie Brown",
        "voter_email": "charlie@example.com",
        "choices": {
            "slot-1": "no",
            "slot-2": "yes"
        }
    }
    response = client.post(f"/api/polls/{poll_id}/vote", json=vote_payload_2)
    assert response.status_code == 200
    voted_poll_2 = response.json()
    assert len(voted_poll_2["votes"]) == 2
    print("   Success!")
    
    print("\n5. Finalizing a slot...")
    finalize_payload = {
        "slot_id": "slot-2"
    }
    response = client.post(f"/api/polls/{poll_id}/finalize", json=finalize_payload)
    assert response.status_code == 200
    finalized_poll = response.json()
    assert finalized_poll["finalized_slot_id"] == "slot-2"
    print("   Success!")
    
    print("\nAll integration tests passed successfully!")

def test_one_on_one_flow():
    print("\n--- Starting One-on-One Scheduler Flow Test ---")
    print("1. Creating a 1-on-1 poll...")
    poll_payload = {
        "poll_type": "one_on_one",
        "title": "Quick Consultation",
        "description": "Book a 1-on-1 slot",
        "duration": "15",
        "timezone": "UTC",
        "organizer_name": "Dr. Smith",
        "organizer_email": "smith@example.com",
        "slots": [
            {"id": "slot-a", "start_time": "2026-07-06T10:00:00Z", "end_time": "2026-07-06T10:15:00Z"},
            {"id": "slot-b", "start_time": "2026-07-06T11:00:00Z", "end_time": "2026-07-06T11:15:00Z"}
        ]
    }
    response = client.post("/api/polls", json=poll_payload)
    assert response.status_code == 201
    poll = response.json()
    assert poll["poll_type"] == "one_on_one"
    poll_id = poll["id"]
    print("   Success!")

    print("\n2. Voter selects slot-b as YES (books it)...")
    vote_payload = {
        "voter_name": "Daniel White",
        "voter_email": "daniel@example.com",
        "choices": {
            "slot-a": "no",
            "slot-b": "yes"
        }
    }
    response = client.post(f"/api/polls/{poll_id}/vote", json=vote_payload)
    assert response.status_code == 200
    voted_poll = response.json()
    
    # 1-on-1 should auto-finalize the selected slot-b!
    assert voted_poll["finalized_slot_id"] == "slot-b"
    print("   Success! Slot-b was auto-finalized.")

    print("\nOne-on-one integration tests passed successfully!")

if __name__ == "__main__":
    try:
        test_full_poll_flow()
        test_one_on_one_flow()
    except AssertionError as e:
        print(f"Test failure: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
