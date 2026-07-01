import os
import json
import urllib.request
from datetime import datetime

def format_time_slot(start_iso: str, end_iso: str, timezone_name: str = "UTC") -> str:
    try:
        # ISO string parsing. Replace Z with UTC offset format for wider compatibility
        start_str = start_iso.replace("Z", "+00:00")
        end_str = end_iso.replace("Z", "+00:00")
        
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
        
        start_formatted = start_dt.strftime("%A, %b %d @ %I:%M %p")
        end_formatted = end_dt.strftime("%I:%M %p")
        return f"{start_formatted} - {end_formatted} ({timezone_name})"
    except Exception:
        return f"{start_iso} to {end_iso}"

def send_vote_notification(poll: dict, vote: dict):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY is not configured. Skipping email notification.")
        return

    organizer_email = poll.get("organizer_email")
    organizer_name = poll.get("organizer_name", "Organizer")
    poll_title = poll.get("title", "Meeting Poll")
    poll_id = poll.get("id")
    voter_name = vote.get("voter_name", "A participant")
    voter_email = vote.get("voter_email", "no-email@example.com")
    choices = vote.get("choices", {})

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Construct choices list
    choices_html = ""
    for slot in poll.get("slots", []):
        slot_id = slot["id"]
        choice_val = choices.get(slot_id, "no")
        
        choice_text = {
            "yes": "<span style='color: #10b981; font-weight: bold;'>✅ Yes</span>",
            "if_need_be": "<span style='color: #f59e0b; font-weight: bold;'>🟡 Maybe</span>",
            "no": "<span style='color: #ef4444;'>❌ No</span>"
        }.get(choice_val, "<span style='color: #ef4444;'>❌ No</span>")
        
        formatted_slot = format_time_slot(slot["start_time"], slot["end_time"], poll.get("timezone", "UTC"))
        choices_html += f"<li style='margin-bottom: 8px;'><strong>{formatted_slot}</strong>: {choice_text}</li>"

    # Resolve production URL for results link
    production_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
    if not production_url:
        production_url = "meetingpoll.vercel.app"
    
    if not production_url.startswith("http"):
        production_url = f"https://{production_url}"
        
    results_link = f"{production_url}/poll/{poll_id}/results"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; background-color: #ffffff;">
        <h2 style="color: #4f46e5; margin-top: 0; font-size: 20px; font-weight: bold;">New Availability Submitted! 📅</h2>
        <p>Hi <strong>{organizer_name}</strong>,</p>
        <p><strong>{voter_name}</strong> ({voter_email}) has submitted their availability for your meeting: <strong style="color: #4f46e5;">{poll_title}</strong>.</p>
        
        <div style="background-color: #f9fafb; border-radius: 6px; padding: 16px; margin: 20px 0; border-left: 4px solid #4f46e5;">
            <h3 style="margin-top: 0; margin-bottom: 12px; font-size: 16px; color: #374151;">Availability Choices:</h3>
            <ul style="margin: 0; padding-left: 20px; line-height: 1.6;">
                {choices_html}
            </ul>
        </div>
        
        <p style="margin-top: 24px; text-align: center;">
            <a href="{results_link}" style="display: inline-block; background-color: #4f46e5; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px;">
                View Results Heatmap & Finalize
            </a>
        </p>
        
        <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 24px 0;" />
        <p style="font-size: 12px; color: #6b7280; text-align: center; margin-bottom: 0;">
            Sent by MeetingPOLL. Designed for seamless scheduling.
        </p>
    </div>
    """

    payload = {
        "from": "MeetingPOLL <onboarding@resend.dev>",
        "to": organizer_email,
        "subject": f"[{voter_name}] responded to: {poll_title}",
        "html": html_content
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as res:
            print(f"Resend notification successfully sent to {organizer_email}. Code {res.getcode()}")
    except Exception as e:
        print(f"Failed to send email notification to organizer: {e}")
