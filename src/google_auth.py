"""Google OAuth 2.0 authentication for Xochitl's Google suite skills.

Manages the full token lifecycle — first-run browser consent, token storage,
and silent refresh. All credentials and tokens live in ~/.xochitl/ so
Xochitl works from any directory on any machine.

Usage:
    from src.google_auth import get_service
    gmail   = get_service("gmail",    "v1")
    cal     = get_service("calendar", "v3")
    drive   = get_service("drive",    "v3")
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_XOCHITL_DIR   = Path.home() / ".xochitl"
_CREDENTIALS   = _XOCHITL_DIR / "google_credentials.json"
_TOKEN         = _XOCHITL_DIR / "google_token.json"

# ── Scopes ────────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _ensure_dir() -> None:
    """Create ~/.xochitl/ if it does not exist."""
    _XOCHITL_DIR.mkdir(exist_ok=True)


def get_credentials():
    """Return valid Google credentials, running the browser flow if needed.

    On first call: opens the browser for consent and saves token.json.
    On subsequent calls: loads token.json and refreshes silently if expired.

    Returns:
        google.oauth2.credentials.Credentials ready for use.

    Raises:
        FileNotFoundError: If google_credentials.json is missing from ~/.xochitl/.
        Exception: If the OAuth flow fails.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    _ensure_dir()

    creds: Optional[Credentials] = None

    # Load existing token — file first, then GOOGLE_TOKEN_JSON env var
    if _TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN), SCOPES)
    elif os.environ.get("GOOGLE_TOKEN_JSON"):
        creds = Credentials.from_authorized_user_info(
            json.loads(os.environ["GOOGLE_TOKEN_JSON"]), SCOPES
        )

    # Refresh or run full flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.debug("google_auth: refreshing expired token")
            creds.refresh(Request())
        else:
            logger.debug("google_auth: running browser consent flow")
            # Prefer GOOGLE_CREDENTIALS_JSON env var (Doppler) over file
            creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                logger.debug("google_auth: loading credentials from env var (Doppler)")
                flow = InstalledAppFlow.from_client_config(
                    json.loads(creds_json), SCOPES
                )
            elif _CREDENTIALS.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(_CREDENTIALS), SCOPES
                )
            else:
                raise FileNotFoundError(
                    f"Google credentials not found.\n"
                    f"Either set GOOGLE_CREDENTIALS_JSON in Doppler, or\n"
                    f"download google_credentials.json from Google Cloud Console\n"
                    f"and place it in {_XOCHITL_DIR}"
                )
            creds = flow.run_local_server(port=0)

        # Save for next run
        _TOKEN.write_text(creds.to_json(), encoding="utf-8")
        logger.debug("google_auth: token saved to %s", _TOKEN)

    return creds


def get_service(service_name: str, version: str):
    """Return an authenticated Google API service client.

    Args:
        service_name: Google API name e.g. 'gmail', 'calendar', 'drive'.
        version: API version e.g. 'v1', 'v3'.

    Returns:
        A googleapiclient Resource ready to make API calls.

    Example:
        gmail = get_service("gmail", "v1")
        result = gmail.users().messages().list(userId="me").execute()
    """
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build(service_name, version, credentials=creds)


def check_auth() -> dict:
    """Verify Google auth is working and return a status summary.

    Uses the Gmail profile endpoint (already in scope) rather than the
    oauth2 userinfo API so no extra API needs to be enabled.

    Returns:
        Dict with 'ok' bool, 'email' of the authed account, and 'scopes' list.
        If auth fails, 'ok' is False and 'error' contains the message.
    """
    try:
        gmail = get_service("gmail", "v1")
        profile = gmail.users().getProfile(userId="me").execute()
        return {
            "ok":     True,
            "email":  profile.get("emailAddress", "unknown"),
            "scopes": SCOPES,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
