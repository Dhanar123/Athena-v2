"""
Configuration loader for all watchers and services.
All values read from environment variables (via .env file).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root (parent of this file's directory)
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _resolve_path(env_key: str, default_rel: str) -> Path:
    raw = os.getenv(env_key, default_rel)
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


class Config:
    # ── Core paths ─────────────────────────────────────────────────── #
    VAULT_PATH = _resolve_path("VAULT_PATH", "./AI_Employee_Vault")
    DROP_FOLDER_PATH = str(_resolve_path("DROP_FOLDER_PATH", "./drop_folder"))

    # ── Gmail ──────────────────────────────────────────────────────── #
    GMAIL_CREDENTIALS_PATH = str(_resolve_path("GMAIL_CREDENTIALS_PATH", "./credentials.json"))
    GMAIL_TOKEN_PATH = str(_resolve_path("GMAIL_TOKEN_PATH", "./watchers/token.pickle"))
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "120"))

    # ── WhatsApp ───────────────────────────────────────────────────── #
    WHATSAPP_SESSION_PATH = str(_resolve_path("WHATSAPP_SESSION_PATH", "./.whatsapp_session"))
    WHATSAPP_CHECK_INTERVAL = int(os.getenv("WHATSAPP_CHECK_INTERVAL", "30"))

    # ── LinkedIn ───────────────────────────────────────────────────── #
    LINKEDIN_SESSION_PATH = str(_resolve_path("LINKEDIN_SESSION_PATH", "./.linkedin_session"))
    LINKEDIN_CHECK_INTERVAL = int(os.getenv("LINKEDIN_CHECK_INTERVAL", "300"))

    # ── Twitter ───────────────────────────────────────────────────── #
    TWITTER_SESSION_PATH = str(_resolve_path("TWITTER_SESSION_PATH", "./.twitter_session"))
    TWITTER_CHECK_INTERVAL = int(os.getenv("TWITTER_CHECK_INTERVAL", "300"))

    # ── Facebook ──────────────────────────────────────────────────── #
    FACEBOOK_SESSION_PATH = str(_resolve_path("FACEBOOK_SESSION_PATH", "./.facebook_session"))
    FACEBOOK_CHECK_INTERVAL = int(os.getenv("FACEBOOK_CHECK_INTERVAL", "300"))

    # ── Behaviour ─────────────────────────────────────────────────── #
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

    # ── Derived vault sub-paths (convenience) ─────────────────────── #
    NEEDS_ACTION = VAULT_PATH / "Needs_Action"
    DONE         = VAULT_PATH / "Done"
    LOGS         = VAULT_PATH / "Logs"
    PLANS        = VAULT_PATH / "Plans"
    PENDING      = VAULT_PATH / "Pending_Approval"
    APPROVED     = VAULT_PATH / "Approved"
    REJECTED     = VAULT_PATH / "Rejected"