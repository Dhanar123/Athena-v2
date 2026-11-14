"""
Personal AI Employee - Real-Time Dashboard
Fetches live data from Gmail, Google Calendar via API,
and shows vault data for WhatsApp and LinkedIn.
"""

import os
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Page config (must be first Streamlit call)
st.set_page_config(
    page_title="Personal AI Employee",
    page_icon="🤖",
    layout="wide",
)

# Load .env
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


# Minimal CSS
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .card-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: #1f2937;
        margin-bottom: 0.3rem;
    }
    .card-meta {
        font-size: 0.8rem;
        color: #6b7280;
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0.6rem;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #e5e7eb;
    }
    .metric-box {
        text-align: center;
        padding: 0.8rem;
        background: #f9fafb;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
    }
    .metric-num {
        font-size: 1.8rem;
        font-weight: 700;
        color: #2563eb;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)


# ======================================================================== #
#  DATA FETCHERS - real-time from APIs                                      #
# ======================================================================== #

def _build_google_creds():
    """Build Google OAuth credentials from token.pickle or the refresh token in .env."""
    import pickle
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    # 1. Try saved token.pickle from GmailWatcher
    token_path = Path(__file__).parent / "watchers" / "token.pickle"
    if token_path.exists():
        try:
            with open(token_path, "rb") as f:
                creds = pickle.load(f)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    return creds
                except Exception:
                    pass
        except Exception:
            pass

    # 2. Try credentials from .env
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        return None

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        creds.refresh(Request())
        return creds
    except Exception:
        # Invalid or expired grant
        return None


def fetch_gmail(max_results=10):
    """Fetch recent unread emails from Gmail API."""
    try:
        creds = _build_google_creds()
        if not creds:
            st.info("Google authorization required to display live Gmail data. Please complete Google sign-in.")
            return []
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        result = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=max_results,
        ).execute()
        messages = result.get("messages", [])
        emails = []
        for msg_stub in messages[:max_results]:
            msg = service.users().messages().get(
                userId="me", id=msg_stub["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            emails.append({
                "id": msg_stub["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            })
        return emails
    except Exception as e:
        st.warning(f"Gmail sync notice: {e}")
        return []


def fetch_calendar(days_ahead=7, max_results=10):
    """Fetch upcoming calendar events from Google Calendar API."""
    try:
        creds = _build_google_creds()
        if not creds:
            return []
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        parsed = []
        for ev in events:
            start = ev.get("start", {})
            start_str = start.get("dateTime", start.get("date", ""))
            parsed.append({
                "summary": ev.get("summary", "(no title)"),
                "start": start_str,
                "location": ev.get("location", ""),
                "description": (ev.get("description") or "")[:200],
                "link": ev.get("htmlLink", ""),
            })
        return parsed
    except Exception as e:
        st.warning(f"Calendar sync notice: {e}")
        return []


def fetch_vault_tasks(source_filter=None):
    """Read vault tasks and hide duplicate WhatsApp cards."""
    vault = Path(os.getenv("VAULT_PATH", "./AI_Employee_Vault"))
    tasks = []

    folders = {
        "Needs_Action": "New",
        "In_Progress": "In Progress",
        "Pending_Approval": "Pending",
        "Done": "Done",
        "Plans": "Planned",
    }

    for folder_name, status_label in folders.items():
        folder = vault / folder_name
        if not folder.exists():
            continue

        for md_file in folder.rglob("*.md"):
            try:
                raw = md_file.read_text(
                    encoding="utf-8", errors="replace"
                )
            except Exception:
                continue

            meta = {}
            body = raw

            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].strip().splitlines():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            meta[key.strip()] = value.strip()
                    body = parts[2].strip()

            task_type = meta.get("type", "").lower()

            if source_filter and source_filter.lower() not in task_type:
                continue

            if task_type in ("twitter", "facebook"):
                continue

            if md_file.name.startswith(
                ("SOCIAL_TWITTER_", "SOCIAL_FACEBOOK_")
            ):
                continue

            title = meta.get("subject", "")
            if not title:
                for line in body.splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

            if not title:
                title = md_file.stem.replace("_", " ")

            # Extract sender from the task content.
            sender = (
                meta.get("sender")
                or meta.get("from")
                or meta.get("contact")
                or ""
            )

            for line in body.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith(
                    ("**sender:**", "sender:", "**from:**", "from:")
                ):
                    sender = (
                        stripped.split(":", 1)[1]
                        .replace("**", "")
                        .strip()
                    )
                    break

            # Extract the message ID stored by the watcher.
            msg_id = meta.get("msg_id", "").strip()

            task = {
                "title": title,
                "type": task_type,
                "source": meta.get("source", "unknown"),
                "priority": meta.get("priority", ""),
                "status": status_label,
                "received": meta.get("received", ""),
                "file": md_file.name,
                "preview": body[:300],
                "sender": sender,
                "msg_id": msg_id,
                "_path": str(md_file),
                "_mtime": md_file.stat().st_mtime,
            }
            tasks.append(task)

    # Keep the newest card for each WhatsApp message.
    if source_filter and source_filter.lower() == "whatsapp":
        unique = {}

        for task in sorted(
            tasks, key=lambda t: t["_mtime"], reverse=True
        ):
            preview = task["preview"].lower()
            sender = task["sender"].strip().lower()

            # Prefer stable IDs; use sender + message text as fallback.
            if task["msg_id"]:
                key = ("id", task["msg_id"])
            else:
                message_text = preview
                for marker in (
                    "## message preview",
                    "## suggested actions",
                    "## matched keyword",
                ):
                    if marker in message_text:
                        message_text = message_text.split(marker, 1)[0]

                key = (
                    "content",
                    sender,
                    " ".join(message_text.split()),
                )

            if key not in unique:
                unique[key] = task

        tasks = list(unique.values())

    # Remove internal fields before rendering.
    for task in tasks:
        task.pop("_path", None)
        task.pop("_mtime", None)

    return tasks



# ======================================================================== #
#  RENDER HELPERS                                                           #
# ======================================================================== #

def render_email_card(email):
    """Render a single email as a styled card."""
    sender = email["from"]
    if "<" in sender:
        name = sender.split("<")[0].strip().strip('"')
        addr = sender.split("<")[1].rstrip(">")
        sender_display = f"{name} ({addr})" if name else addr
    else:
        sender_display = sender
    snippet = email["snippet"][:150]
    if len(email["snippet"]) > 150:
        snippet += "..."
    st.markdown(
        '<div class="card">'
        f'<div class="card-title">&#x1F4E7; {email["subject"]}</div>'
        f'<div class="card-meta">{sender_display}</div>'
        f'<div style="font-size:0.82rem;color:#374151;margin-top:0.3rem;">{snippet}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_event_card(event):
    """Render a single calendar event as a styled card."""
    start = event["start"]
    try:
        if "T" in start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start_display = dt.strftime("%b %d, %Y  %I:%M %p")
        else:
            dt = datetime.strptime(start, "%Y-%m-%d")
            start_display = dt.strftime("%b %d, %Y") + "  (All day)"
    except Exception:
        start_display = start

    location = ""
    if event["location"]:
        location = f" | {event['location']}"
    st.markdown(
        '<div class="card">'
        f'<div class="card-title">&#x1F4C5; {event["summary"]}</div>'
        f'<div class="card-meta">{start_display}{location}</div>'
        '</div>',
        unsafe_allow_html=True,
    )



def render_vault_card(task):
    """Render a vault task with its message preview."""

    icons = {
        "whatsapp": "💬",
        "email": "📧",
        "gmail": "📧",
        "linkedin": "💼",
        "calendar": "📅",
    }

    icon = icons.get(task["type"], "📄")
    priority = task.get("priority", "").lower()

    priority_badge = ""
    if priority:
        color = "#ef4444" if priority == "high" else "#f59e0b"
        priority_badge = (
            f'<span style="background:{color};color:white;'
            f'padding:2px 8px;border-radius:10px;'
            f'font-size:0.7rem;margin-left:8px;">'
            f'{priority}</span>'
        )

    st.markdown(
        '<div class="card">'
        f'<div class="card-title">{icon} {task["title"]}'
        f'{priority_badge}</div>'
        f'<div class="card-meta">{task["status"]} | '
        f'{task.get("received", "Unknown time")}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    preview = task.get("preview", "").strip()
    if preview:
        with st.expander("View task details"):
            st.text(preview)
            st.caption(f'File: {task["file"]}')



# ======================================================================== #
#  MAIN UI                                                                  #
# ======================================================================== #

st.title("Personal AI Employee")
st.caption("Real-time overview from Gmail, Calendar, WhatsApp, and LinkedIn")

# Fetch all data
with st.spinner("Fetching live data..."):
    emails = fetch_gmail(max_results=10)
    events = fetch_calendar(days_ahead=7, max_results=10)
    whatsapp_tasks = fetch_vault_tasks(source_filter="whatsapp")
    linkedin_tasks = fetch_vault_tasks(source_filter="linkedin")

# Metric row
c1, c2, c3, c4 = st.columns(4)
for col, label, count in [
    (c1, "Unread Emails", len(emails)),
    (c2, "Upcoming Events", len(events)),
    (c3, "WhatsApp Tasks", len(whatsapp_tasks)),
    (c4, "LinkedIn Tasks", len(linkedin_tasks)),
]:
    col.markdown(
        '<div class="metric-box">'
        f'<div class="metric-num">{count}</div>'
        f'<div class="metric-label">{label}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# Two-column layout
left, right = st.columns(2)

with left:
    st.markdown(
        '<div class="section-title">Gmail - Unread Emails</div>',
        unsafe_allow_html=True,
    )
    if emails:
        for email in emails:
            render_email_card(email)
    else:
        st.info("No unread emails.")

    st.markdown("")

    st.markdown(
        '<div class="section-title">WhatsApp - Tasks</div>',
        unsafe_allow_html=True,
    )
    if whatsapp_tasks:
        for task in whatsapp_tasks:
            render_vault_card(task)
    else:
        st.info("No WhatsApp tasks in the vault.")

with right:
    st.markdown(
        '<div class="section-title">Calendar - Upcoming Events</div>',
        unsafe_allow_html=True,
    )
    if events:
        for event in events:
            render_event_card(event)
    else:
        st.info("No upcoming events.")

    st.markdown("")

    st.markdown(
        '<div class="section-title">LinkedIn - Tasks</div>',
        unsafe_allow_html=True,
    )
    if linkedin_tasks:
        for task in linkedin_tasks:
            render_vault_card(task)
    else:
        st.info("No LinkedIn tasks in the vault.")

# Footer controls
st.divider()
col_a, col_b = st.columns([1, 4])
with col_a:
    if st.button("Refresh", use_container_width=True):
        st.rerun()
with col_b:
    if st.toggle("Auto-refresh (30s)", value=False):
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=30_000, limit=None, key="auto_refresh")
        except ImportError:
            st.caption("Install streamlit-autorefresh for auto-refresh.")
