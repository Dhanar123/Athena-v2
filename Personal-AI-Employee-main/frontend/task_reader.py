"""
Core data layer for the Streamlit frontend of Personal AI Employee.

Reads and monitors the AI_Employee_Vault structure, parses markdown task files
with YAML frontmatter, reads JSON audit logs, and provides HITL approval actions.
"""

from pathlib import Path
from datetime import datetime
import json
import logging
import os
import shutil
from dotenv import load_dotenv

try:
    import yaml
except ImportError:
    yaml = None

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# Status constants
STATUS_NEW = "New"
STATUS_IN_PROGRESS = "In Progress"
STATUS_PENDING_APPROVAL = "Pending Approval"
STATUS_COMPLETED = "Completed"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_PLANNED = "Planned"

# Source display names
SOURCE_DISPLAY = {
    "email": "Gmail",
    "gmail": "Gmail",
    "whatsapp": "WhatsApp",
    "whatsapp_web": "WhatsApp",
    "linkedin": "LinkedIn",
    "calendar": "Calendar",
    "file_drop": "File Drop",
    "plan": "Plan",
    "invoice_approval": "Invoice",
}

# Sources to HIDE
HIDDEN_SOURCES = {"twitter", "facebook", "odoo"}
HIDDEN_PREFIXES = ("SOCIAL_TWITTER_", "SOCIAL_FACEBOOK_")

SOURCE_ICONS = {
    "Gmail": "📧",
    "WhatsApp": "💬",
    "LinkedIn": "💼",
    "Calendar": "📅",
    "File Drop": "📁",
    "Plan": "📋",
    "Invoice": "💰",
    "Unknown": "📄",
}

STATUS_COLORS = {
    STATUS_NEW: "#EF4444",
    STATUS_IN_PROGRESS: "#F59E0B",
    STATUS_PENDING_APPROVAL: "#F97316",
    STATUS_COMPLETED: "#10B981",
    STATUS_APPROVED: "#10B981",
    STATUS_REJECTED: "#6B7280",
    STATUS_PLANNED: "#3B82F6",
}


class TaskReader:
    """
    Data layer responsible for parsing and managing tasks, logs, and metadata
    stored within the AI Employee vault.
    """

    def __init__(self, vault_path: Path = None):
        """
        Initialize TaskReader with vault path and shortcuts to subfolders.

        Args:
            vault_path: Path to the vault directory. Defaults to env var VAULT_PATH
                        or './AI_Employee_Vault'.
        """
        if vault_path is not None:
            self.vault_path = Path(vault_path)
        else:
            env_vault = os.getenv("VAULT_PATH")
            if env_vault:
                self.vault_path = Path(env_vault)
            else:
                project_root = Path(__file__).parent.parent
                default_path = project_root / "AI_Employee_Vault"
                if default_path.exists():
                    self.vault_path = default_path
                else:
                    self.vault_path = Path("./AI_Employee_Vault")

        # Shortcuts to vault subfolders
        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.in_progress_dir = self.vault_path / "In_Progress"
        self.done_dir = self.vault_path / "Done"
        self.pending_approval_dir = self.vault_path / "Pending_Approval"
        self.approved_dir = self.vault_path / "Approved"
        self.rejected_dir = self.vault_path / "Rejected"
        self.plans_dir = self.vault_path / "Plans"
        self.logs_dir = self.vault_path / "Logs"
        self.briefings_dir = self.vault_path / "Briefings"

        # Alternative alias shortcuts
        self.needs_action_path = self.needs_action_dir
        self.in_progress_path = self.in_progress_dir
        self.done_path = self.done_dir
        self.pending_approval_path = self.pending_approval_dir
        self.approved_path = self.approved_dir
        self.rejected_path = self.rejected_dir
        self.plans_path = self.plans_dir
        self.logs_path = self.logs_dir
        self.briefings_path = self.briefings_dir

        self.folder_status_map = {
            "Needs_Action": STATUS_NEW,
            "In_Progress": STATUS_IN_PROGRESS,
            "Pending_Approval": STATUS_PENDING_APPROVAL,
            "Done": STATUS_COMPLETED,
            "Approved": STATUS_APPROVED,
            "Rejected": STATUS_REJECTED,
            "Plans": STATUS_PLANNED,
        }

    @staticmethod
    def _parse_datetime(val) -> datetime | None:
        """
        Parse datetime from diverse string or date representations, converting
        to a naive datetime for uniform sorting.

        Args:
            val: Date/time value (str, datetime, int, float, etc.)

        Returns:
            datetime or None: Parsed naive datetime object.
        """
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.replace(tzinfo=None) if val.tzinfo is not None else val
        if hasattr(val, "year") and hasattr(val, "month") and hasattr(val, "day"):
            # datetime.date instance
            return datetime(val.year, val.month, val.day)
        if isinstance(val, (int, float)):
            try:
                return datetime.fromtimestamp(val)
            except Exception:
                return None

        val_str = str(val).strip()
        if not val_str:
            return None

        # Normalize trailing Z to ISO UTC offset
        iso_str = val_str.replace("Z", "+00:00") if val_str.endswith("Z") else val_str
        try:
            parsed = datetime.fromisoformat(iso_str)
            return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
        except Exception:
            pass

        date_formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
        ]
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(val_str, fmt)
                return parsed
            except Exception:
                continue

        return None

    @staticmethod
    def _parse_simple_yaml(lines: list[str]) -> dict:
        """
        Fallback parser for simple YAML key-value pairs without requiring PyYAML.

        Args:
            lines: Frontmatter lines.

        Returns:
            dict: Parsed key-value mapping.
        """
        data = {}
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                val = v.strip().strip('"').strip("'")
                data[k.strip()] = val
        return data

    def parse_frontmatter(self, filepath: Path) -> dict:
        """
        Parse YAML-style frontmatter from a markdown file (between '---' delimiters).

        Args:
            filepath: Path to the markdown file.

        Returns:
            dict: Parsed frontmatter dictionary including calculated metadata fields:
                  _filepath, _filename, _folder, _status, _content, _body,
                  _source_display, _source_icon, _title, _timestamp.
                  Returns empty dict on file access error.
        """
        path = Path(filepath)
        if not path.exists() or not path.is_file():
            return {}

        try:
            raw_content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return {}

        frontmatter_data = {}
        body = raw_content

        lines = raw_content.splitlines()
        if lines and lines[0].strip() == "---":
            closing_idx = -1
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    closing_idx = i
                    break

            if closing_idx != -1:
                fm_lines = lines[1:closing_idx]
                body = "\n".join(lines[closing_idx + 1:])
                fm_text = "\n".join(fm_lines)
                try:
                    if yaml is not None:
                        parsed = yaml.safe_load(fm_text)
                        if isinstance(parsed, dict):
                            frontmatter_data = parsed
                        else:
                            frontmatter_data = self._parse_simple_yaml(fm_lines)
                    else:
                        frontmatter_data = self._parse_simple_yaml(fm_lines)
                except Exception:
                    frontmatter_data = self._parse_simple_yaml(fm_lines)

        if not isinstance(frontmatter_data, dict):
            frontmatter_data = {}

        task = dict(frontmatter_data)

        # 1. _filepath
        try:
            task["_filepath"] = str(path.resolve())
        except Exception:
            task["_filepath"] = str(path)

        # 2. _filename
        task["_filename"] = path.name

        # 3. _folder & 4. _status
        folder_name = ""
        try:
            rel_path = path.resolve().relative_to(self.vault_path.resolve())
            folder_name = rel_path.parts[0] if rel_path.parts else ""
        except Exception:
            for part in reversed(path.parts[:-1]):
                if part in self.folder_status_map:
                    folder_name = part
                    break
            if not folder_name:
                folder_name = path.parent.name

        task["_folder"] = folder_name
        task["_status"] = self.folder_status_map.get(
            folder_name,
            str(frontmatter_data.get("status", "Unknown")),
        )

        # 5. _content
        task["_content"] = raw_content

        # 6. _body
        task["_body"] = body

        # 7. _source_display
        source_val = str(task.get("source", "")).lower().strip()
        type_val = str(task.get("type", "")).lower().strip()

        display_name = SOURCE_DISPLAY.get(source_val) or SOURCE_DISPLAY.get(type_val)
        if not display_name:
            fname_upper = path.name.upper()
            if fname_upper.startswith("EMAIL_"):
                display_name = "Gmail"
            elif fname_upper.startswith("WHATSAPP_"):
                display_name = "WhatsApp"
            elif fname_upper.startswith("PLAN_"):
                display_name = "Plan"
            elif fname_upper.startswith("APPROVAL_"):
                display_name = "Invoice"
            elif fname_upper.startswith("FILE_"):
                display_name = "File Drop"
            elif fname_upper.startswith("SOCIAL_LINKEDIN_"):
                display_name = "LinkedIn"
            else:
                display_name = "Unknown"

        task["_source_display"] = display_name

        # 8. _source_icon
        task["_source_icon"] = SOURCE_ICONS.get(display_name, SOURCE_ICONS.get("Unknown", "📄"))

        # 9. _title
        title = ""
        for bline in body.splitlines():
            stripped = bline.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

        if not title:
            subject = task.get("subject")
            if subject:
                title = str(subject).strip()

        if not title:
            title = path.stem.replace("_", " ")

        task["_title"] = title

        # 10. _timestamp
        ts = None
        if "received" in task:
            ts = self._parse_datetime(task["received"])
        if ts is None and "created" in task:
            ts = self._parse_datetime(task["created"])
        if ts is None:
            try:
                ts = datetime.fromtimestamp(path.stat().st_mtime)
            except Exception:
                ts = datetime.now()

        if ts and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)

        task["_timestamp"] = ts

        return task

    def _should_show_task(self, task: dict) -> bool:
        """
        Check if a task should be shown in the UI.

        Returns False if the task's type/source is in HIDDEN_SOURCES or if the
        filename starts with HIDDEN_PREFIXES or is not a .md file.

        Args:
            task: Task dictionary.

        Returns:
            bool: True if allowed in UI, False otherwise.
        """
        filename = task.get("_filename", "")
        if not filename.lower().endswith(".md"):
            return False

        if filename.startswith(HIDDEN_PREFIXES):
            return False

        task_type = str(task.get("type", "")).lower().strip()
        if task_type in HIDDEN_SOURCES:
            return False

        task_source = str(task.get("source", "")).lower().strip()
        if task_source in HIDDEN_SOURCES:
            return False

        return True

    def _scan_folder(self, folder: Path, status: str) -> list[dict]:
        """
        Scan a folder (and its subfolders recursively) for .md files.
        Parse each file, set _status to the given status, and filter through _should_show_task().

        Args:
            folder: Directory to scan.
            status: Status string to assign.

        Returns:
            list[dict]: List of task dictionaries.
        """
        folder_path = Path(folder)
        if not folder_path.exists() or not folder_path.is_dir():
            return []

        tasks = []
        try:
            for filepath in folder_path.rglob("*.md"):
                if not filepath.is_file():
                    continue
                try:
                    task = self.parse_frontmatter(filepath)
                    if not task:
                        continue
                    task["_status"] = status
                    if self._should_show_task(task):
                        tasks.append(task)
                except Exception as e:
                    logger.error(f"Error parsing task {filepath}: {e}")
        except Exception as e:
            logger.error(f"Error scanning folder {folder_path}: {e}")

        return tasks

    def get_all_tasks(self) -> list[dict]:
        """
        Scan all vault folders (Needs_Action, In_Progress, Pending_Approval, Done,
        Approved, Rejected, Plans) and return combined list sorted by _timestamp descending.

        Returns:
            list[dict]: List of all visible tasks sorted newest first.
        """
        folders_to_scan = [
            (self.needs_action_dir, STATUS_NEW),
            (self.in_progress_dir, STATUS_IN_PROGRESS),
            (self.pending_approval_dir, STATUS_PENDING_APPROVAL),
            (self.done_dir, STATUS_COMPLETED),
            (self.approved_dir, STATUS_APPROVED),
            (self.rejected_dir, STATUS_REJECTED),
            (self.plans_dir, STATUS_PLANNED),
        ]

        all_tasks = []
        for folder, status in folders_to_scan:
            all_tasks.extend(self._scan_folder(folder, status))

        all_tasks.sort(
            key=lambda t: t.get("_timestamp") or datetime.min,
            reverse=True,
        )
        return all_tasks

    def get_tasks_by_status(self, status: str) -> list[dict]:
        """
        Filter get_all_tasks() by _status.

        Args:
            status: Status name to match.

        Returns:
            list[dict]: Tasks matching the status.
        """
        return [task for task in self.get_all_tasks() if task.get("_status") == status]

    def get_tasks_by_source(self, source_display: str) -> list[dict]:
        """
        Filter get_all_tasks() by _source_display.

        Args:
            source_display: Display name to match (e.g. 'Gmail', 'WhatsApp').

        Returns:
            list[dict]: Tasks matching the source display name.
        """
        return [
            task for task in self.get_all_tasks()
            if task.get("_source_display") == source_display
        ]

    def get_task_counts(self) -> dict:
        """
        Return dictionary with task counts per status and total.

        Returns:
            dict: {"New": N, "In Progress": N, "Pending Approval": N, "Completed": N,
                   "Approved": N, "Rejected": N, "Planned": N, "Total": N}
        """
        tasks = self.get_all_tasks()
        counts = {
            STATUS_NEW: 0,
            STATUS_IN_PROGRESS: 0,
            STATUS_PENDING_APPROVAL: 0,
            STATUS_COMPLETED: 0,
            STATUS_APPROVED: 0,
            STATUS_REJECTED: 0,
            STATUS_PLANNED: 0,
            "Total": len(tasks),
        }
        for task in tasks:
            status = task.get("_status")
            if status in counts:
                counts[status] += 1
        return counts

    def get_pending_approvals(self) -> list[dict]:
        """
        Return tasks from Pending_Approval/ folder only, sorted by timestamp descending.

        Returns:
            list[dict]: Pending approval tasks.
        """
        tasks = self._scan_folder(self.pending_approval_dir, STATUS_PENDING_APPROVAL)
        tasks.sort(
            key=lambda t: t.get("_timestamp") or datetime.min,
            reverse=True,
        )
        return tasks

    def get_recent_activity(self, limit: int = 10) -> list[dict]:
        """
        Return the N most recent tasks across all folders, sorted by timestamp descending.

        Args:
            limit: Maximum number of recent tasks to return.

        Returns:
            list[dict]: Top N most recent tasks.
        """
        tasks = self.get_all_tasks()
        return tasks[:limit]

    def get_log_entries(self, limit: int = 20) -> list[dict]:
        """
        Read JSON log files from Logs/ folder. Each log file is a JSON array
        of log entry objects. Combine all entries, sort by timestamp descending,
        and return top N entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            list[dict]: Most recent log entries.
        """
        entries = []
        if not self.logs_dir.exists() or not self.logs_dir.is_dir():
            return []

        try:
            for log_file in self.logs_dir.glob("*.json"):
                if not log_file.is_file():
                    continue
                try:
                    content = log_file.read_text(encoding="utf-8", errors="replace")
                    data = json.loads(content)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                entries.append(item)
                    elif isinstance(data, dict):
                        entries.append(data)
                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")
        except Exception as e:
            logger.error(f"Error scanning logs folder {self.logs_dir}: {e}")

        def _get_entry_ts(entry: dict) -> datetime:
            raw_ts = entry.get("timestamp") or entry.get("time") or entry.get("created")
            parsed = self._parse_datetime(raw_ts)
            return parsed or datetime.min

        entries.sort(key=_get_entry_ts, reverse=True)
        return entries[:limit]

    def get_dashboard_data(self) -> dict:
        """
        Retrieve summary files from the vault: Dashboard.md, Business_Goals.md,
        and verify Company_Handbook.md existence.

        Returns:
            dict: {
                "dashboard_content": str or None,
                "business_goals": str or None,
                "handbook_exists": bool
            }
        """
        dashboard_content = None
        dashboard_file = self.vault_path / "Dashboard.md"
        if dashboard_file.exists() and dashboard_file.is_file():
            try:
                dashboard_content = dashboard_file.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.error(f"Error reading Dashboard.md: {e}")

        business_goals = None
        goals_file = self.vault_path / "Business_Goals.md"
        if goals_file.exists() and goals_file.is_file():
            try:
                business_goals = goals_file.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.error(f"Error reading Business_Goals.md: {e}")

        handbook_file = self.vault_path / "Company_Handbook.md"
        if not handbook_file.exists():
            handbook_file = self.vault_path / "Handbook.md"
        handbook_exists = handbook_file.exists() and handbook_file.is_file()

        return {
            "dashboard_content": dashboard_content,
            "business_goals": business_goals,
            "handbook_exists": handbook_exists,
        }

    def approve_task(self, filepath: str) -> bool:
        """
        Move the task file at filepath to the Approved/ folder.

        Args:
            filepath: Path string of the task file to approve.

        Returns:
            bool: True on success, False on failure.
        """
        try:
            src = Path(filepath)
            if not src.exists() or not src.is_file():
                logger.error(f"Cannot approve task: file does not exist ({filepath})")
                return False

            self.approved_dir.mkdir(parents=True, exist_ok=True)
            dest = self.approved_dir / src.name

            if src.resolve() == dest.resolve():
                logger.info(f"Task is already in Approved directory: {filepath}")
                return True

            if dest.exists():
                dest.unlink()

            shutil.move(str(src), str(dest))
            logger.info(f"Approved task: moved {src} to {dest}")
            return True
        except Exception as e:
            logger.error(f"Failed to approve task {filepath}: {e}", exc_info=True)
            return False

    def reject_task(self, filepath: str) -> bool:
        """
        Move the task file at filepath to the Rejected/ folder.

        Args:
            filepath: Path string of the task file to reject.

        Returns:
            bool: True on success, False on failure.
        """
        try:
            src = Path(filepath)
            if not src.exists() or not src.is_file():
                logger.error(f"Cannot reject task: file does not exist ({filepath})")
                return False

            self.rejected_dir.mkdir(parents=True, exist_ok=True)
            dest = self.rejected_dir / src.name

            if src.resolve() == dest.resolve():
                logger.info(f"Task is already in Rejected directory: {filepath}")
                return True

            if dest.exists():
                dest.unlink()

            shutil.move(str(src), str(dest))
            logger.info(f"Rejected task: moved {src} to {dest}")
            return True
        except Exception as e:
            logger.error(f"Failed to reject task {filepath}: {e}", exc_info=True)
            return False
