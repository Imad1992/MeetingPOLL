# MeetingPOLL 📅⚡

A premium, modern desktop-wrapped meeting poll and scheduling application built with a FastAPI backend, native `pywebview` client frame, and a gorgeous light-themed SPA (Single Page Application) frontend.

---

## 🌟 Key Features

### 1. Dual Scheduling Modes
* **Group Poll (Doodle Style)**:
  - Coordinate meetings for multiple participants.
  - Voters submit their availability (Yes / Maybe / No) for multiple proposed slots.
  - Interactive, heatmapped agreement matrix shows the best slot at a glance.
  - Organizer reviews results and manually finalizes the official meeting time.
* **1-on-1 Scheduler (Calendly Style)**:
  - First-come-first-served booking.
  - Voters pick exactly one slot from the options to confirm.
  - The first selected "Yes" vote automatically books and finalizes the meeting, locking other choices.
  - Displays a clean status table showing booked, available, and unavailable slots.

### 2. Desktop Wrapper
* Launches the application inside a native, standalone desktop frame titled **MeetingPOLL** using the `pywebview` library.
* Automatically spins up the FastAPI backend in an isolated subprocess to prevent thread contention.
* Falls back gracefully to the default system browser if GUI dependencies are missing.

### 3. Professional Calendar & Messaging Integration
* **Add to Calendar (.ics)**: Dynamically generates and downloads an iCalendar (`.ics`) file for finalized meetings, enabling users to add the slot to Outlook, Google Calendar, or Apple Calendar with one click.
* **Email & Slack Invitations**: Generates copyable, pre-filled message drafts containing proposed times, description, and direct link.

### 4. High-End UI & Styling
* Curated light theme featuring smooth pastel animations (indigo and rose pink background orbs).
* Fluid hover transitions, custom grid styling, and responsive layout.
* Input character limits with real-time word/character count feedback.

---

## 🛠️ Technology Stack

* **Backend**: Python 3, FastAPI, Uvicorn, Pydantic.
* **Database**: Lightweight JSON-based local database (`db.json`) with automated auto-booking triggers.
* **Frontend**: HTML5, Vanilla CSS3 (custom layouts & animations), Vanilla ES6+ JavaScript.
* **Desktop Client**: `pywebview` (Edge WebView2 engine wrapper).

---

## 📁 File Structure

```
POLL/
├── app.py             # FastAPI backend API routes and asset mounting
├── db.py              # JSON file database operations and auto-finalization logic
├── run_desktop.py     # Independent subprocess uvicorn & pywebview wrapper launcher
├── test_poll.py       # Integration test suite for both Group and 1-on-1 flows
├── db.json            # Local JSON database storage file
├── static/            # Static assets served by the web app
│   ├── index.html     # SPA layout containing all three view sections
│   ├── style.css      # Custom HSL-based stylesheets & light-theme aesthetics
│   ├── app.js         # Frontend router, timezone helper, and API client scripts
│   └── logo.png       # Generated custom MeetingPOLL vector logo
└── README.md          # Project documentation (this file)
```

---

## 🚀 Quick Start Guide

### Prerequisites
Make sure you have Python 3.8+ installed on your system.

### 1. Install Dependencies
Run the following command to install the required libraries:
```bash
pip install fastapi uvicorn pydantic pywebview
```

### 2. Run the Desktop Application
Run the launcher wrapper to start both the server and the native desktop frame:
```bash
python run_desktop.py
```

### 3. Open in Browser (Optional)
If you prefer running in a web browser, start the server independently:
```bash
python -m uvicorn app:app --port 8000
```
Then navigate to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 4. Run Automated Tests
Run the integration test suite to verify the scheduling engines:
```bash
python test_poll.py
```
