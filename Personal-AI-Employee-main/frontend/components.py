"""UI components module for the Personal AI Employee Streamlit frontend.

This module provides reusable UI components, custom CSS, badges, cards,
metric rows, timelines, and headers built with a clean, professional design system.
"""

from __future__ import annotations

import hashlib
import html
import os
from datetime import datetime
from typing import Any, Optional

import streamlit as st

# Import constants from frontend.task_reader with fallback support
try:
    from frontend.task_reader import (
        SOURCE_ICONS,
        STATUS_APPROVED,
        STATUS_COLORS,
        STATUS_COMPLETED,
        STATUS_IN_PROGRESS,
        STATUS_NEW,
        STATUS_PENDING_APPROVAL,
        STATUS_PLANNED,
        STATUS_REJECTED,
    )
except ImportError:
    try:
        from task_reader import (
            SOURCE_ICONS,
            STATUS_APPROVED,
            STATUS_COLORS,
            STATUS_COMPLETED,
            STATUS_IN_PROGRESS,
            STATUS_NEW,
            STATUS_PENDING_APPROVAL,
            STATUS_PLANNED,
            STATUS_REJECTED,
        )
    except ImportError:
        # Fallback constants if task_reader module is not yet imported
        STATUS_NEW = "New"
        STATUS_IN_PROGRESS = "In Progress"
        STATUS_PENDING_APPROVAL = "Pending Approval"
        STATUS_COMPLETED = "Completed"
        STATUS_APPROVED = "Approved"
        STATUS_REJECTED = "Rejected"
        STATUS_PLANNED = "Planned"

        STATUS_COLORS = {
            STATUS_NEW: "#EF4444",              # Red
            STATUS_IN_PROGRESS: "#F59E0B",     # Amber / Yellow
            STATUS_PENDING_APPROVAL: "#F97316", # Orange
            STATUS_PLANNED: "#3B82F6",          # Blue
            STATUS_COMPLETED: "#10B981",        # Green
            STATUS_APPROVED: "#059669",         # Emerald
            STATUS_REJECTED: "#DC2626",         # Dark Red
        }

        SOURCE_ICONS = {
            "WhatsApp": "💬",
            "Gmail": "✉️",
            "Email": "📧",
            "LinkedIn": "💼",
            "Twitter": "🐦",
            "Facebook": "📘",
            "File": "📁",
            "Odoo": "🏢",
            "System": "⚙️",
        }


# ==============================================================================
# Helper Utilities
# ==============================================================================

def format_timestamp(ts: Any) -> str:
    """Format various timestamp representations into a readable date/time string.

    Examples:
        - ISO string: '2026-03-09T09:31:56Z' -> 'Mar 09, 2026 at 09:31 AM'
        - Datetime object -> 'Mar 09, 2026 at 09:31 AM'

    Args:
        ts: A datetime object, numeric epoch timestamp, or date string.

    Returns:
        Formatted human-friendly timestamp string.
    """
    if not ts:
        return "Unknown date"

    if isinstance(ts, (int, float)):
        try:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%b %d, %Y at %I:%M %p")
        except Exception:
            return str(ts)

    if isinstance(ts, datetime):
        return ts.strftime("%b %d, %Y at %I:%M %p")

    ts_str = str(ts).strip()

    # Handle ISO formats with trailing Z or timezone offsets
    iso_candidate = ts_str
    if iso_candidate.endswith("Z"):
        iso_candidate = iso_candidate[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(iso_candidate)
        return dt.strftime("%b %d, %Y at %I:%M %p")
    except Exception:
        pass

    # Try common alternative datetime formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d_%H%M%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(ts_str, fmt)
            return dt.strftime("%b %d, %Y at %I:%M %p")
        except Exception:
            continue

    return ts_str


def _sanitize_val(val: Any) -> str:
    """Sanitize values to ensure sensitive file paths are not exposed.

    Args:
        val: Any raw metadata or attribute value.

    Returns:
        Sanitized string, stripping directory paths if a file path is detected.
    """
    if val is None:
        return "N/A"
    s = str(val).strip()

    # Detect Windows or Unix file paths and return just the filename
    if ("\\" in s or "/" in s) and (":" in s or s.startswith("/") or s.startswith(".")):
        return os.path.basename(s.replace("\\", "/"))

    return s


# ==============================================================================
# CSS Injection
# ==============================================================================

def inject_custom_css() -> None:
    """Inject custom CSS for the clean, professional design system.

    Styles:
    - Hides Streamlit's default hamburger menu, header decoration, and footer.
    - Sets page background and typography colors.
    - Styles cards (.task-card), status badges (.status-badge), and source badges (.source-badge).
    - Styles metrics containers (.metric-container), section headers (.section-header),
      and detailed content blocks (.detail-content).
    """
    custom_css = """
    <style>
    /* Hide Streamlit default hamburger menu and footer */
    #MainMenu {visibility: hidden; display: none;}
    footer {visibility: hidden; display: none;}
    header [data-testid="stDecoration"] {display: none;}

    /* Background and typography */
    .stApp {
        background-color: #FAFBFC;
        color: #1F2937;
    }

    /* Task Card Container */
    .task-card {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .task-card:hover {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
    }

    /* Status Badge */
    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #FFFFFF !important;
        text-transform: capitalize;
        letter-spacing: 0.02em;
        line-height: 1.4;
        white-space: nowrap;
    }

    /* Source Badge */
    .source-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
        background-color: #F3F4F6;
        color: #374151;
        border: 1px solid #E5E7EB;
        line-height: 1.4;
        white-space: nowrap;
    }

    /* Metric Cards */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 0.85rem 1rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }

    .metric-container {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    }

    /* Section Header */
    .section-header {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1F2937;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Task Detail Content */
    .detail-content {
        padding: 0.85rem 1.15rem;
        border-left: 3px solid #2563EB;
        background-color: #F9FAFB;
        border-radius: 0 8px 8px 0;
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
        color: #374151;
        font-size: 0.9rem;
        line-height: 1.6;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-word;
    }

    /* Activity Timeline */
    .timeline-container {
        border-left: 2px solid #E5E7EB;
        margin-left: 0.75rem;
        padding-left: 1.25rem;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .timeline-item {
        position: relative;
        padding-bottom: 1.25rem;
    }

    .timeline-item:last-child {
        padding-bottom: 0.25rem;
    }

    .timeline-dot {
        position: absolute;
        left: -1.65rem;
        top: 0.2rem;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: #2563EB;
        border: 2px solid #FFFFFF;
        box-shadow: 0 0 0 1px #E5E7EB;
    }

    .timeline-time {
        font-size: 0.75rem;
        font-weight: 500;
        color: #6B7280;
        margin-bottom: 2px;
    }

    .timeline-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #1F2937;
    }

    .timeline-body {
        font-size: 0.85rem;
        color: #4B5563;
        margin-top: 4px;
        background-color: #FFFFFF;
        padding: 8px 12px;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


# ==============================================================================
# Metric Cards
# ==============================================================================

def render_metric_cards(counts: dict) -> None:
    """Display task counts as a row of metric cards.

    Uses a 7-column layout displaying:
    - Total tasks (with delta showing new task count)
    - New (red indicator)
    - In Progress (yellow indicator)
    - Pending Approval (orange indicator)
    - Planned (blue indicator)
    - Completed (green indicator)
    - Approved + Rejected combined metrics

    Args:
        counts: Dictionary of status names/keys to their counts.
    """
    counts = counts or {}

    def _get_val(*keys: str) -> int:
        for k in keys:
            if k in counts and isinstance(counts[k], (int, float)):
                return int(counts[k])
            # Case-insensitive and slug search
            k_slug = str(k).lower().replace(" ", "_").replace("-", "_")
            for ck, cv in counts.items():
                if str(ck).lower().replace(" ", "_").replace("-", "_") == k_slug:
                    try:
                        return int(cv)
                    except (ValueError, TypeError):
                        pass
        return 0

    new_count = _get_val(STATUS_NEW, "new", "needs_action", "needs action")
    in_prog_count = _get_val(STATUS_IN_PROGRESS, "in_progress", "in progress")
    pending_count = _get_val(STATUS_PENDING_APPROVAL, "pending_approval", "pending", "awaiting_approval")
    planned_count = _get_val(STATUS_PLANNED, "planned", "plans", "plan")
    completed_count = _get_val(STATUS_COMPLETED, "completed", "done")
    approved_count = _get_val(STATUS_APPROVED, "approved")
    rejected_count = _get_val(STATUS_REJECTED, "rejected")

    total_count = _get_val("total", "all")
    if total_count == 0:
        total_count = (
            new_count
            + in_prog_count
            + pending_count
            + planned_count
            + completed_count
            + approved_count
            + rejected_count
        )

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

    with col1:
        delta_str = f"+{new_count} new" if new_count > 0 else None
        st.metric(
            label="📊 Total",
            value=total_count,
            delta=delta_str,
            help="Total tasks tracked across all stages",
        )
    with col2:
        st.metric(
            label="🔴 New",
            value=new_count,
            help="Newly detected tasks awaiting triage",
        )
    with col3:
        st.metric(
            label="🟡 In Progress",
            value=in_prog_count,
            help="Tasks currently being processed",
        )
    with col4:
        st.metric(
            label="🟠 Pending",
            value=pending_count,
            help="Actions awaiting human approval",
        )
    with col5:
        st.metric(
            label="🔵 Planned",
            value=planned_count,
            help="Structured plans waiting for execution",
        )
    with col6:
        st.metric(
            label="🟢 Completed",
            value=completed_count,
            help="Successfully finished tasks",
        )
    with col7:
        st.metric(
            label="⚖️ Appr / Rej",
            value=f"{approved_count} / {rejected_count}",
            help=f"Approved: {approved_count} | Rejected: {rejected_count}",
        )


# ==============================================================================
# Badges
# ==============================================================================

def render_status_badge(status: str) -> str:
    """Return an HTML string for a colored status pill badge.

    Args:
        status: The task status string (e.g. 'New', 'Pending Approval').

    Returns:
        HTML span formatted with status badge styling and matching background color.
    """
    if not status:
        status = "Unknown"

    color = STATUS_COLORS.get(status)
    if not color:
        # Check case-insensitively
        status_norm = str(status).strip().lower()
        for k, v in STATUS_COLORS.items():
            if str(k).strip().lower() == status_norm:
                color = v
                break
    if not color:
        color = "#6B7280"

    return f'<span class="status-badge" style="background-color:{color};">{html.escape(str(status))}</span>'


def render_source_badge(source_display: str) -> str:
    """Return an HTML string with icon + source name.

    Args:
        source_display: The source display name (e.g. 'WhatsApp', 'Email').

    Returns:
        HTML span with icon and source display badge.
    """
    if not source_display:
        source_display = "File"

    icon = SOURCE_ICONS.get(source_display)
    if not icon:
        # Check case-insensitively
        source_norm = str(source_display).strip().lower()
        for k, v in SOURCE_ICONS.items():
            if str(k).strip().lower() == source_norm:
                icon = v
                break
    if not icon:
        icon = "📄"

    return f'<span class="source-badge">{icon} {html.escape(str(source_display))}</span>'


# ==============================================================================
# Task Card & Actions
# ==============================================================================

def _execute_task_action(
    filepath: str,
    action: str,
    vault_path: Optional[str] = None,
) -> None:
    """Execute approval or rejection on a pending task file.

    Args:
        filepath: Full path to the task file.
        action: Either 'approve' or 'reject'.
        vault_path: Optional path to vault root.
    """
    if not filepath:
        st.error(f"Cannot {action} task: Missing file path.")
        return

    try:
        try:
            from frontend.task_reader import TaskReader
        except ImportError:
            try:
                from task_reader import TaskReader
            except ImportError:
                TaskReader = None

        if TaskReader is None:
            st.error("TaskReader module could not be imported.")
            return

        reader = TaskReader(vault_path) if vault_path else TaskReader()
        action_fn = getattr(reader, f"{action}_task", None)
        if not callable(action_fn):
            st.error(f"TaskReader has no method '{action}_task'.")
            return

        result = action_fn(filepath)
        success = True
        msg = f"Task successfully {action}d."

        if isinstance(result, tuple) and len(result) >= 2:
            success = bool(result[0])
            msg = str(result[1])
        elif isinstance(result, bool):
            success = result
            msg = f"Task successfully {action}d." if success else f"Failed to {action} task."
        elif isinstance(result, str):
            msg = result

        if success:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    except Exception as exc:
        st.error(f"Error while attempting to {action} task: {exc}")


def render_task_card(
    task: dict,
    show_actions: bool = False,
    vault_path: Optional[str] = None,
) -> None:
    """Render a single task as a card with metadata, body expander, and actions.

    Displays:
    - Title (`task["_title"]`)
    - Source badge and status badge on the same line
    - Priority if available (from frontmatter `priority` field)
    - Formatted timestamp (`task["_timestamp"]`)
    - An expander labeled "View Details" showing frontmatter metadata and body content
    - Approve / Reject buttons if `show_actions=True` and status is Pending Approval

    Args:
        task: Dictionary containing task data and metadata.
        show_actions: Whether to show approval/rejection action buttons.
        vault_path: Optional vault directory path for TaskReader.
    """
    if not task or not isinstance(task, dict):
        return

    # Extract core properties safely
    raw_title = task.get("_title") or task.get("title") or "Untitled Task"
    title = _sanitize_val(raw_title)

    raw_status = task.get("_status") or task.get("status") or STATUS_NEW
    source_display = task.get("_source_display") or task.get("_source") or task.get("source") or "File"
    priority = task.get("priority") or task.get("_priority")
    raw_timestamp = (
        task.get("_timestamp")
        or task.get("created")
        or task.get("timestamp")
        or task.get("date")
    )
    formatted_time = format_timestamp(raw_timestamp)

    status_badge_html = render_status_badge(str(raw_status))
    source_badge_html = render_source_badge(str(source_display))

    # Priority badge if present
    priority_badge_html = ""
    if priority:
        p_str = str(priority).strip()
        p_lower = p_str.lower()
        if "high" in p_lower or "urgent" in p_lower:
            p_bg = "#EF4444"
        elif "med" in p_lower:
            p_bg = "#F59E0B"
        else:
            p_bg = "#6B7280"
        priority_badge_html = (
            f'<span class="status-badge" style="background-color:{p_bg}; '
            f'font-size:0.75rem; margin-right:4px;">⚡ {html.escape(p_str.upper())}</span>'
        )

    # Render card container
    try:
        container = st.container(border=True)
    except TypeError:
        container = st.container()

    with container:
        # Card header line
        header_html = f"""
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem; gap: 0.5rem; flex-wrap: wrap;">
            <div style="font-size: 1.05rem; font-weight: 600; color: #1F2937;">{html.escape(title)}</div>
            <div style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
                {priority_badge_html}
                {source_badge_html}
                {status_badge_html}
            </div>
        </div>
        <div style="font-size: 0.8rem; color: #6B7280; margin-bottom: 0.5rem;">
            🕒 {html.escape(formatted_time)}
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        # Expander for full details
        with st.expander("View Details", expanded=False):
            # Frontmatter metadata (excluding internal keys starting with _)
            meta_items = {
                k: v for k, v in task.items()
                if not str(k).startswith("_")
            }
            if meta_items:
                st.markdown("**Metadata**")
                table_lines = ["| Property | Value |", "| :--- | :--- |"]
                for k, v in meta_items.items():
                    val_str = _sanitize_val(v)
                    safe_val = str(val_str).replace("|", "\\|").replace("\n", " ")
                    table_lines.append(f"| **{html.escape(str(k))}** | `{safe_val}` |")
                st.markdown("\n".join(table_lines))
            else:
                st.caption("No frontmatter metadata recorded.")

            # Full body content
            body = task.get("_body", "")
            if body and str(body).strip():
                st.markdown("**Content**")
                st.markdown(
                    f'<div class="detail-content">{html.escape(str(body).strip())}</div>',
                    unsafe_allow_html=True,
                )

        # Pending approval action buttons
        status_norm = str(raw_status).strip().lower().replace("_", " ")
        is_pending = (
            status_norm == STATUS_PENDING_APPROVAL.lower()
            or "pending" in status_norm
            or "awaiting" in status_norm
        )

        if show_actions and is_pending:
            filepath = str(task.get("_filepath", ""))
            unique_seed = filepath if filepath else f"{title}_{id(task)}"
            hash_key = hashlib.sha256(unique_seed.encode("utf-8")).hexdigest()[:12]

            col_app, col_rej = st.columns(2)
            with col_app:
                if st.button(
                    "✅ Approve",
                    key=f"btn_approve_{hash_key}",
                    use_container_width=True,
                    type="primary",
                ):
                    _execute_task_action(filepath, "approve", vault_path)
            with col_rej:
                if st.button(
                    "❌ Reject",
                    key=f"btn_reject_{hash_key}",
                    use_container_width=True,
                ):
                    _execute_task_action(filepath, "reject", vault_path)


# ==============================================================================
# Task List & Filtering
# ==============================================================================

def render_task_list(
    tasks: list,
    show_actions: bool = False,
    vault_path: Optional[str] = None,
) -> None:
    """Render a list of tasks as cards.

    If the list is empty, an informational message is displayed.

    Args:
        tasks: List of task dictionaries.
        show_actions: Whether to display action buttons for pending approval tasks.
        vault_path: Optional path to the vault directory.
    """
    if not tasks:
        st.info("No tasks found.")
        return

    for task in tasks:
        render_task_card(task, show_actions=show_actions, vault_path=vault_path)


def render_filters(tasks: list) -> tuple[str, str]:
    """Render status and source filter selectbox controls in two columns.

    Args:
        tasks: List of task dictionaries from which to extract available filter options.

    Returns:
        tuple[str, str]: The selected (status_filter, source_filter).
    """
    statuses = set()
    sources = set()

    for t in (tasks or []):
        if not isinstance(t, dict):
            continue
        status = t.get("_status") or t.get("status")
        if status:
            statuses.add(str(status))
        source = t.get("_source_display") or t.get("_source") or t.get("source")
        if source:
            sources.add(str(source))

    status_options = ["All"] + sorted(list(statuses))
    source_options = ["All"] + sorted(list(sources))

    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            options=status_options,
            index=0,
            key="filter_status_select",
        )
    with col2:
        source_filter = st.selectbox(
            "Filter by Source",
            options=source_options,
            index=0,
            key="filter_source_select",
        )

    return status_filter, source_filter


def render_filtered_task_list(
    tasks: list,
    show_actions: bool = False,
    vault_path: Optional[str] = None,
) -> None:
    """Combine filter controls and the resulting filtered task list rendering.

    Workflow:
    1. Render filter selectbox controls
    2. Filter tasks based on current selections
    3. Display the count of filtered tasks
    4. Render the filtered list of task cards

    Args:
        tasks: Full list of task dictionaries.
        show_actions: Whether to display action buttons for pending approval tasks.
        vault_path: Optional path to the vault directory.
    """
    all_tasks = tasks or []

    # 1. Show filter controls
    status_filter, source_filter = render_filters(all_tasks)

    # 2. Filter tasks based on selections
    filtered_tasks = all_tasks
    if status_filter != "All":
        filtered_tasks = [
            t for t in filtered_tasks
            if str(t.get("_status") or t.get("status", "")).strip().lower() == status_filter.strip().lower()
        ]
    if source_filter != "All":
        filtered_tasks = [
            t for t in filtered_tasks
            if str(t.get("_source_display") or t.get("_source") or t.get("source", "")).strip().lower() == source_filter.strip().lower()
        ]

    # 3. Show count of filtered tasks
    st.caption(f"Showing **{len(filtered_tasks)}** of **{len(all_tasks)}** tasks")

    # 4. Render filtered task list
    render_task_list(filtered_tasks, show_actions=show_actions, vault_path=vault_path)


# ==============================================================================
# Activity Log Timeline
# ==============================================================================

def render_log_timeline(logs: list) -> None:
    """Render recent activity logs as an aesthetic visual timeline.

    For each log entry, displays:
    - Formatted timestamp
    - Action type
    - Relevant details (actor, target, result, or metadata attributes)

    Args:
        logs: List of log dictionaries. If empty, displays an info banner.
    """
    if not logs:
        st.info("No recent activity.")
        return

    with st.container():
        timeline_items_html = []
        for entry in logs:
            if not isinstance(entry, dict):
                continue

            raw_time = (
                entry.get("timestamp")
                or entry.get("created")
                or entry.get("time")
                or entry.get("date")
            )
            time_formatted = format_timestamp(raw_time)

            raw_action = (
                entry.get("action_type")
                or entry.get("action")
                or entry.get("type")
                or "Activity"
            )
            action_title = str(raw_action).replace("_", " ").title()

            # Gather relevant details
            detail_parts = []

            if "actor" in entry and entry["actor"]:
                detail_parts.append(
                    f"<strong>Actor:</strong> {html.escape(_sanitize_val(entry['actor']))}"
                )
            if "target" in entry and entry["target"]:
                detail_parts.append(
                    f"<strong>Target:</strong> {html.escape(_sanitize_val(entry['target']))}"
                )
            if "result" in entry and entry["result"]:
                res_str = str(entry["result"]).upper()
                res_color = (
                    "#10B981" if any(w in res_str for w in ("SUCCESS", "OK", "TRUE"))
                    else "#EF4444" if any(w in res_str for w in ("FAIL", "ERROR", "FALSE"))
                    else "#6B7280"
                )
                detail_parts.append(
                    f"<strong>Result:</strong> <span style='color:{res_color}; font-weight:600;'>{html.escape(res_str)}</span>"
                )

            # Check other informative log attributes
            for key in ("action_taken", "intent", "source_file", "plan_file", "details", "message"):
                if key in entry and entry[key]:
                    k_disp = key.replace("_", " ").title()
                    v_disp = _sanitize_val(entry[key])
                    detail_parts.append(
                        f"<strong>{html.escape(k_disp)}:</strong> {html.escape(str(v_disp))}"
                    )

            # Fallback if no known keys were present
            if not detail_parts:
                for k, v in entry.items():
                    if (
                        k not in ("timestamp", "created", "time", "date", "action_type", "action", "type")
                        and not str(k).startswith("_")
                    ):
                        detail_parts.append(
                            f"<strong>{html.escape(str(k))}:</strong> {html.escape(str(_sanitize_val(v)))}"
                        )

            details_html = "<br>".join(detail_parts) if detail_parts else "<em>No additional details recorded</em>"

            item_html = f"""
            <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-time">🕒 {html.escape(time_formatted)}</div>
                <div class="timeline-title">{html.escape(action_title)}</div>
                <div class="timeline-body">{details_html}</div>
            </div>
            """
            timeline_items_html.append(item_html)

        full_html = f"""
        <div class="timeline-container">
            {"".join(timeline_items_html)}
        </div>
        """
        st.markdown(full_html, unsafe_allow_html=True)


# ==============================================================================
# Page Headers
# ==============================================================================

def render_dashboard_header() -> None:
    """Render the dashboard page header with title, subtitle, and divider."""
    st.markdown(
        """
        <div style="margin-bottom: 0.75rem;">
            <h1 style="margin: 0; color: #1F2937; font-weight: 700; font-size: 2.1rem; display: flex; align-items: center; gap: 0.6rem;">
                🤖 Personal AI Employee
            </h1>
            <p style="margin: 0.25rem 0 0 0; color: #6B7280; font-size: 1.05rem;">
                Dashboard Overview
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()


def render_approval_center_header() -> None:
    """Render the approval center header with title and explanatory workflow banner."""
    st.markdown(
        """
        <div style="margin-bottom: 0.75rem;">
            <h1 style="margin: 0; color: #1F2937; font-weight: 700; font-size: 2.1rem; display: flex; align-items: center; gap: 0.6rem;">
                ✅ Approval Center
            </h1>
            <p style="margin: 0.25rem 0 0 0; color: #6B7280; font-size: 1.05rem;">
                Review and approve actions requiring human oversight
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "💡 **Human-in-the-Loop (HITL) Workflow:** Review proposed tasks below. "
        "Approving moves the action to the execution pipeline, while rejecting cancels it."
    )
    st.divider()
