
"""
WhatsApp Watcher - Silver Tier
Monitors WhatsApp Web for urgent messages using Playwright.

Improvements:
- Stable SHA-256 message fingerprints.
- Persistent duplicate detection across restarts.
- Processes individual chat rows instead of nearby chat-list lines.
- Extracts the sender and message preview separately.
- Prevents duplicate task creation for already processed messages.
"""

import hashlib
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from watchers.base_watcher import BaseWatcher
from watchers.config import Config


URGENT_KEYWORDS = [
    "urgent",
    "asap",
    "invoice",
    "payment",
    "emergency",
    "important",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]


class WhatsAppWatcher(BaseWatcher):

    def __init__(self):
        super().__init__(
            vault_path=Config.VAULT_PATH,
            check_interval=Config.WHATSAPP_CHECK_INTERVAL,
        )

        self.session_path = Path(Config.WHATSAPP_SESSION_PATH)
        self.session_path.mkdir(parents=True, exist_ok=True)

        self.processed_ids: set[str] = self._load_processed_ids()

    # ---------------------------------------------------------
    # Persistent duplicate detection
    # ---------------------------------------------------------

    def _processed_ids_file(self) -> Path:
        return self.logs / "processed_whatsapp.json"

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize whitespace and casing for comparison."""
        text = text.replace("\u00a0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip().casefold()

    def _make_message_id(self, sender: str, message: str) -> str:
        """
        Generate a deterministic fingerprint.

        Unlike Python's hash(), SHA-256 remains stable across
        Python process restarts.
        """
        normalized_sender = self._normalize_text(sender)
        normalized_message = self._normalize_text(message)

        content = f"{normalized_sender}|{normalized_message}"

        return hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

    def _load_processed_ids(self) -> set[str]:
        file_path = self._processed_ids_file()

        if not file_path.exists():
            return set()

        try:
            data = json.loads(
                file_path.read_text(encoding="utf-8")
            )

            if not isinstance(data, list):
                self.logger.warning(
                    "Processed WhatsApp IDs file is not a list."
                )
                return set()

            return {
                item for item in data
                if isinstance(item, str)
            }

        except (json.JSONDecodeError, OSError) as exc:
            self.logger.error(
                f"Could not load processed WhatsApp IDs: {exc}"
            )
            return set()

    def _save_processed_id(self, msg_id: str) -> None:
        """Persist processed IDs using an atomic file replacement."""
        if msg_id in self.processed_ids:
            return

        file_path = self._processed_ids_file()
        file_path.parent.mkdir(parents=True, exist_ok=True)

        updated_ids = self.processed_ids | {msg_id}
        temp_path = file_path.with_suffix(".tmp")

        try:
            temp_path.write_text(
                json.dumps(sorted(updated_ids), indent=2),
                encoding="utf-8",
            )

            temp_path.replace(file_path)
            self.processed_ids = updated_ids

        except OSError as exc:
            self.logger.error(
                f"Could not save processed WhatsApp ID: {exc}"
            )
            raise

    # ---------------------------------------------------------
    # Read individual chat rows
    # ---------------------------------------------------------

    def _get_chat_rows(self, page):
        """
        Find individual chat rows.

        WhatsApp Web changes its DOM occasionally, so try
        more than one selector.
        """
        selectors = [
            '#pane-side [data-testid="cell-frame-container"]',
            '#pane-side [role="listitem"]',
        ]

        for selector in selectors:
            rows = page.locator(selector)

            if rows.count() > 0:
                return rows

        return None

    def _extract_candidate(self, row_text: str):
        """
        Extract a sender and the urgent line from one chat row.

        This uses the visible chat-list preview, not the complete
        conversation history.
        """
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in row_text.splitlines()
            if line.strip()
        ]

        if len(lines) < 2:
            return None

        # The first visible line is usually the contact or group.
        sender = lines[0]

        if not sender:
            return None

        # Look for the line that contains an urgent keyword.
        matched_line = None

        for line in lines[1:]:
            lowered = line.casefold()

            if any(
                keyword in lowered
                for keyword in URGENT_KEYWORDS
            ):
                matched_line = line

        if not matched_line:
            return None

        # Avoid treating a sender name alone as a message.
        if self._normalize_text(matched_line) == (
            self._normalize_text(sender)
        ):
            return None

        return {
            "sender": sender,
            "text": matched_line,
            "matched_line": matched_line,
        }

    # ---------------------------------------------------------
    # Find new urgent messages
    # ---------------------------------------------------------

    def check_for_updates(self) -> list:
        """Find new urgent messages visible in WhatsApp Web."""

        if Config.DRY_RUN:
            self.logger.info(
                "[DRY RUN] Skipping WhatsApp browser session."
            )
            return []

        urgent_messages = []
        seen_this_scan: set[str] = set()
        browser_context = None

        try:
            with sync_playwright() as playwright:
                browser_context = (
                    playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.session_path),
                        headless=False,
                        args=BROWSER_ARGS,
                        user_agent=USER_AGENT,
                        slow_mo=80,
                    )
                )

                page = (
                    browser_context.pages[0]
                    if browser_context.pages
                    else browser_context.new_page()
                )

                page.goto(
                    "https://web.whatsapp.com",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                self.logger.info(
                    "Waiting for WhatsApp Web login and chat loading."
                )

                page.wait_for_timeout(40000)

                pane = page.query_selector("#pane-side")

                if not pane:
                    self.logger.error(
                        "WhatsApp chat list not found. "
                        "Check login status."
                    )
                    return []

                rows = self._get_chat_rows(page)

                if rows is None:
                    self.logger.error(
                        "Could not identify individual WhatsApp chat rows. "
                        "The WhatsApp Web DOM may have changed."
                    )
                    return []

                row_count = rows.count()

                self.logger.info(
                    f"Scanning {row_count} visible WhatsApp chat rows."
                )

                for index in range(row_count):
                    try:
                        row = rows.nth(index)

                        if not row.is_visible():
                            continue

                        row_text = row.inner_text(timeout=3000)
                        candidate = self._extract_candidate(row_text)

                        if not candidate:
                            continue

                        sender = candidate["sender"]
                        message_text = candidate["text"]

                        msg_id = self._make_message_id(
                            sender,
                            message_text,
                        )

                        # Skip IDs processed during earlier runs.
                        if msg_id in self.processed_ids:
                            continue

                        # Avoid duplicates within this scan.
                        if msg_id in seen_this_scan:
                            continue

                        seen_this_scan.add(msg_id)

                        urgent_messages.append({
                            "id": msg_id,
                            "sender": sender,
                            "text": message_text,
                            "matched_line": candidate["matched_line"],
                        })

                        self.logger.info(
                            "New potential urgent message detected "
                            f"from {sender!r}."
                        )

                    except Exception as row_exc:
                        self.logger.warning(
                            f"Could not inspect chat row {index}: "
                            f"{row_exc}"
                        )

                self.logger.info(
                    f"Found {len(urgent_messages)} new potential "
                    "urgent message(s)."
                )

        except Exception as exc:
            self.logger.error(
                f"WhatsApp browser error: {exc}",
                exc_info=True,
            )

        finally:
            if browser_context:
                try:
                    browser_context.close()
                except Exception:
                    pass

        return urgent_messages

    # ---------------------------------------------------------
    # Create a task in the AI Employee Vault
    # ---------------------------------------------------------

    def create_action_file(self, message: dict) -> Path:
        """Create a Markdown task in the Needs Action folder."""

        msg_id = message["id"]

        # Guard against duplicate calls from the processing loop.
        if msg_id in self.processed_ids:
            self.logger.info(
                f"Skipping already processed WhatsApp message: {msg_id}"
            )

            # Return the existing task if it can be found.
            for folder_name in [
                "Needs_Action",
                "In_Progress",
                "Pending_Approval",
                "Done",
            ]:
                folder = self.vault_path / folder_name

                if not folder.exists():
                    continue

                for existing_file in folder.glob("WHATSAPP_*.md"):
                    try:
                        content = existing_file.read_text(
                            encoding="utf-8"
                        )

                        if re.search(
                            rf"(?m)^msg_id:\s*{re.escape(msg_id)}\s*$",
                            content,
                        ):
                            return existing_file

                    except OSError:
                        continue

            # The ID was previously processed but its task file
            # is no longer in the standard folders.
            # Do not recreate it automatically.
            raise FileNotFoundError(
                "This WhatsApp message was already processed, "
                "but its existing task file could not be found."
            )

        timestamp = datetime.now()

        filepath = (
            self.needs_action
            / f"WHATSAPP_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.md"
        )

        filepath.parent.mkdir(parents=True, exist_ok=True)

        sender = message.get("sender", "Unknown sender")
        message_text = message.get("text", "")
        matched_line = message.get("matched_line", "N/A")

        content = f"""---
type: whatsapp
source: whatsapp_web
received: {timestamp.isoformat()}
priority: high
status: pending
sender: {json.dumps(sender, ensure_ascii=False)}
msg_id: {msg_id}
---

# WhatsApp Urgent Message

**Sender:** {sender}

**Received:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

**Priority:** High

## Message Preview

{message_text}

## Matched Keyword

{matched_line}

## Suggested Actions

- [ ] Review the message and sender
- [ ] Reply if appropriate
- [ ] Generate an invoice if requested
- [ ] Escalate payment-related issues if needed

---
*Created by WhatsApp Watcher*
"""

        # Write the task first. Save the fingerprint only if the
        # file creation succeeds.
        filepath.write_text(content, encoding="utf-8")

        try:
            self._save_processed_id(msg_id)

        except Exception:
            # Avoid leaving an untracked file that could be
            # created again on the next scan.
            try:
                filepath.unlink(missing_ok=True)
            except OSError:
                self.logger.exception(
                    "Could not remove an untracked WhatsApp task file."
                )
            raise

        self.logger.info(
            f"Created WhatsApp action file: {filepath.name}"
        )

        return filepath

    # ---------------------------------------------------------
    # Send a WhatsApp reply
    # ---------------------------------------------------------

    def send_reply(self, to: str, message: str) -> bool:
        """Send a WhatsApp message to a contact by phone number."""

        if Config.DRY_RUN:
            self.logger.info(
                f"[DRY RUN] Would send WhatsApp to {to}: {message}"
            )
            return True

        browser_context = None

        try:
            with sync_playwright() as playwright:
                browser_context = (
                    playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.session_path),
                        headless=False,
                        args=BROWSER_ARGS,
                        user_agent=USER_AGENT,
                        slow_mo=80,
                    )
                )

                page = (
                    browser_context.pages[0]
                    if browser_context.pages
                    else browser_context.new_page()
                )

                phone = (
                    to.replace("+", "")
                    .replace(" ", "")
                    .replace("-", "")
                )

                encoded_message = urllib.parse.quote(message)

                page.goto(
                    "https://web.whatsapp.com/send"
                    f"?phone={phone}&text={encoded_message}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                self.logger.info(f"Opening chat with {to}...")

                page.wait_for_timeout(15000)

                send_button = page.locator(
                    'button[aria-label="Send"]'
                ).last

                if (
                    send_button.count() > 0
                    and send_button.is_visible()
                ):
                    send_button.click()
                    page.wait_for_timeout(2000)

                    self.logger.info(f"Message sent to {to}")
                    return True

                self.logger.error(
                    "Send button not found. Check WhatsApp login "
                    "and the current WhatsApp Web interface."
                )
                return False

        except Exception as exc:
            self.logger.error(
                f"WhatsApp send error: {exc}",
                exc_info=True,
            )
            return False

        finally:
            if browser_context:
                try:
                    browser_context.close()
                except Exception:
                    pass


if __name__ == "__main__":
    watcher = WhatsAppWatcher()
    watcher.logger.info("Starting WhatsApp Watcher...")
    watcher.run()
