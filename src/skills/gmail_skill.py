"""Gmail skill — read inbox, search, send, and mark messages via Google Gmail API.

Implements CR-046a: Gmail integration for Xochitl.

Capabilities:
  - Inbox summary (last N unread messages)
  - Search emails by query (from, subject, date, label)
  - Read a specific email by index (after listing) or by ID
  - Send an email (to, subject, body)
  - Mark as read / archive

Auth: uses ~/.xochitl/google_token.json via google_auth.get_service()
Scopes required: gmail.readonly, gmail.send, gmail.modify (all already granted).
"""
# Implements FR-GMAIL-001 (read inbox)
# Implements FR-GMAIL-002 (search)
# Implements FR-GMAIL-003 (send)
# Implements FR-GMAIL-004 (mark read / archive)
# Implements CR-046a

from __future__ import annotations

import base64
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.skills.base import Skill

# ── Intent keyword groups ─────────────────────────────────────────────────────

_READ_KEYWORDS = (
    "check my email",
    "check email",
    "check inbox",
    "check my inbox",
    "check in my inbox",
    "check in email",
    "email inbox",
    "my inbox",
    "in my inbox",
    "new emails",
    "unread emails",
    "any emails",
    "what's in my inbox",
    "whats in my inbox",
    "show me my emails",
    "show my emails",
    "open my email",
    "read my email",
    "any new mail",
    "check mail",
    "got any emails",
    "got any mail",
    "any messages",
)

_SEARCH_KEYWORDS = (
    "find emails",
    "find email",
    "search my email",
    "search email",
    "emails from",
    "email from",
    "emails about",
    "email about",
    "look up email",
)

_SEND_KEYWORDS = (
    "send an email",
    "send email",
    "email to ",
    "write an email",
    "draft an email",
    "compose an email",
)

_MARK_KEYWORDS = (
    "mark as read",
    "mark email as read",
    "archive that email",
    "archive the email",
    "mark that read",
)


class GmailSkill(Skill):
    """Read, search, send, and manage Gmail messages."""

    # ── Skill interface ───────────────────────────────────────────────────────

    def can_handle(self, user_input: str, context: dict) -> float:
        """Return confidence that this is a Gmail query.

        Args:
            user_input: Raw user message.
            context: Assembled session context.

        Returns:
            0.95 for send/search, 0.90 for inbox read, 0.0 otherwise.
        """
        q = user_input.lower()
        if any(k in q for k in _SEND_KEYWORDS):
            return 0.95
        if any(k in q for k in _SEARCH_KEYWORDS):
            return 0.95
        if any(k in q for k in _READ_KEYWORDS):
            return 0.90
        if any(k in q for k in _MARK_KEYWORDS):
            return 0.90
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion prompt shown before executing.

        Args:
            user_input: Raw user message.
            context: Assembled session context.

        Returns:
            Short offer string.
        """
        q = user_input.lower()
        if any(k in q for k in _SEND_KEYWORDS):
            return "I can send that email via Gmail. Want me to?"
        return "I can check your Gmail inbox. Want me to?"

    def tool_definition(self) -> dict:
        """Return the LLM tool descriptor for system prompt injection.

        Returns:
            Dict with name, description, when, and params keys.
        """
        return {
            "name": "GmailSkill",
            "description": (
                "Reads inbox, searches, sends emails, and marks messages "
                "via Google Gmail API."
            ),
            "when": (
                "user wants to check email, read inbox, find an email from someone, "
                "send an email, or mark/archive an email"
            ),
            "params": {
                "intent": "'inbox' | 'search' | 'read' | 'send' | 'mark_read' | 'archive'",
                "query": "Gmail search query e.g. 'from:boss@company.com' or 'subject:invoice'",
                "index": "1-based index into the last shown email list (for 'read' intent)",
                "to": "Recipient email address for send",
                "subject": "Email subject for send",
                "body": "Email body text for send",
                "max_results": "Number of emails to list (default 5)",
            },
            "examples": [
                "check my email",
                "what's in my inbox",
                "any new messages?",
                "send an email to mom",
                "find emails from my boss",
                "read the first email",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Dispatch to the appropriate Gmail operation.

        Args:
            user_input: Raw user message.
            context: Assembled session context.
            params: LLM-extracted params (intent, query, index, to, subject, body).

        Returns:
            Formatted result string or error message.
        """
        try:
            from src.google_auth import get_service
            gmail = get_service("gmail", "v1")
        except FileNotFoundError as exc:
            return str(exc)
        except Exception as exc:
            return f"Gmail auth error: {exc}"

        intent = (params.get("intent") or "").lower()
        q = user_input.lower()

        if not intent:
            if any(k in q for k in _SEND_KEYWORDS):
                intent = "send"
            elif any(k in q for k in _SEARCH_KEYWORDS):
                intent = "search"
            elif any(k in q for k in _MARK_KEYWORDS):
                intent = "mark_read"
            else:
                intent = "inbox"

        if intent == "send":
            return self._send(gmail, user_input, context, params)
        if intent == "search":
            return self._search(gmail, user_input, context, params)
        if intent == "read":
            return self._read_by_index(gmail, context, params)
        if intent in ("mark_read", "archive"):
            return self._mark_read(gmail, context, params, archive=(intent == "archive"))
        return self._inbox(gmail, context, params)

    # ── Inbox ─────────────────────────────────────────────────────────────────

    def _inbox(self, gmail, context: dict, params: dict) -> str:
        """List recent unread inbox messages.

        Args:
            gmail: Authenticated Gmail API service.
            context: Session context (stores last email list).
            params: max_results override.

        Returns:
            Formatted inbox summary string.
        """
        max_results = int(params.get("max_results") or 5)
        try:
            resp = gmail.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=max_results,
            ).execute()
        except Exception as exc:
            return f"Gmail error listing inbox: {exc}"

        messages = resp.get("messages", [])
        if not messages:
            return "Your inbox is clear — no unread messages."

        summaries = []
        for i, msg_ref in enumerate(messages, 1):
            meta = _get_message_meta(gmail, msg_ref["id"])
            summaries.append((msg_ref["id"], meta))
            context.setdefault("gmail_last_list", []).append(msg_ref["id"])

        context["gmail_last_list"] = [s[0] for s in summaries]
        return _format_inbox(summaries, unread_only=True)

    # ── Search ────────────────────────────────────────────────────────────────

    def _search(self, gmail, user_input: str, context: dict, params: dict) -> str:
        """Search Gmail with a query string.

        Args:
            gmail: Authenticated Gmail API service.
            user_input: Raw user message (used for query extraction fallback).
            context: Session context.
            params: query and max_results params.

        Returns:
            Formatted search results string.
        """
        query = (params.get("query") or "").strip()
        max_results = int(params.get("max_results") or 5)

        if not query:
            query = _extract_search_query(user_input)
        if not query:
            return "What would you like to search for? Try: 'find emails from boss@company.com'"

        try:
            resp = gmail.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()
        except Exception as exc:
            return f"Gmail search error: {exc}"

        messages = resp.get("messages", [])
        if not messages:
            return f"No emails found for: '{query}'"

        summaries = []
        for msg_ref in messages:
            meta = _get_message_meta(gmail, msg_ref["id"])
            summaries.append((msg_ref["id"], meta))

        context["gmail_last_list"] = [s[0] for s in summaries]
        header = f"Search results for '{query}':"
        return _format_inbox(summaries, header=header)

    # ── Read full email ───────────────────────────────────────────────────────

    def _read_by_index(self, gmail, context: dict, params: dict) -> str:
        """Read the full body of an email by its 1-based list index.

        Args:
            gmail: Authenticated Gmail API service.
            context: Session context (contains gmail_last_list).
            params: index param (1-based).

        Returns:
            Formatted full email string or error.
        """
        last_list: list = context.get("gmail_last_list", [])
        if not last_list:
            return "No emails listed yet. Try 'check my email' first."

        index = int(params.get("index") or 1)
        if index < 1 or index > len(last_list):
            return f"Index {index} is out of range — I have {len(last_list)} emails listed."

        msg_id = last_list[index - 1]
        try:
            msg = gmail.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as exc:
            return f"Gmail error reading message: {exc}"

        return _format_full_message(msg)

    # ── Mark read / archive ───────────────────────────────────────────────────

    def _mark_read(
        self, gmail, context: dict, params: dict, archive: bool = False
    ) -> str:
        """Mark the most recent listed email as read, optionally archiving it.

        Args:
            gmail: Authenticated Gmail API service.
            context: Session context (contains gmail_last_list).
            params: index param (default 1).
            archive: If True, also remove INBOX label.

        Returns:
            Confirmation string or error.
        """
        last_list: list = context.get("gmail_last_list", [])
        if not last_list:
            return "No emails listed yet. Try 'check my email' first."

        index = int(params.get("index") or 1)
        if index < 1 or index > len(last_list):
            return f"Index {index} is out of range — I have {len(last_list)} emails listed."

        msg_id = last_list[index - 1]
        remove_labels = ["UNREAD"]
        if archive:
            remove_labels.append("INBOX")

        try:
            gmail.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": remove_labels},
            ).execute()
        except Exception as exc:
            return f"Gmail error: {exc}"

        action = "archived" if archive else "marked as read"
        return f"Email #{index} {action}."

    # ── Send ──────────────────────────────────────────────────────────────────

    def _send(self, gmail, user_input: str, context: dict, params: dict) -> str:
        """Compose and send an email.

        Args:
            gmail: Authenticated Gmail API service.
            user_input: Raw user message (fallback extraction).
            context: Session context.
            params: to, subject, body params.

        Returns:
            Confirmation string or error.
        """
        to      = (params.get("to") or "").strip()
        subject = (params.get("subject") or "").strip()
        body    = (params.get("body") or "").strip()

        if not to:
            return "I need a recipient. Try: 'send an email to name@example.com'"
        if not subject and not body:
            return "I need at least a subject or body to send. What should the email say?"

        subject = subject or "(no subject)"

        try:
            raw = _build_raw_message(to=to, subject=subject, body=body)
            gmail.users().messages().send(
                userId="me",
                body={"raw": raw},
            ).execute()
        except Exception as exc:
            return f"Gmail send error: {exc}"

        return f"Email sent to {to} — subject: '{subject}'."


# ── Module-level helpers ──────────────────────────────────────────────────────

def _get_message_meta(gmail, msg_id: str) -> dict:
    """Fetch message metadata (headers + snippet) without full body.

    Args:
        gmail: Authenticated Gmail API service.
        msg_id: Gmail message ID.

    Returns:
        Dict with keys: id, from_, subject, date, snippet, unread.
    """
    try:
        msg = gmail.users().messages().get(
            userId="me",
            id=msg_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
    except Exception:
        return {"id": msg_id, "from_": "unknown", "subject": "(error)", "date": "", "snippet": "", "unread": False}

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return {
        "id":      msg_id,
        "from_":   headers.get("From", "unknown"),
        "subject": headers.get("Subject", "(no subject)"),
        "date":    _friendly_date(headers.get("Date", "")),
        "snippet": msg.get("snippet", ""),
        "unread":  "UNREAD" in msg.get("labelIds", []),
    }


def _get_plain_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload.

    Args:
        payload: The 'payload' dict from a full Gmail message.

    Returns:
        Decoded plain-text body string.
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="ignore")

    for part in payload.get("parts", []):
        text = _get_plain_body(part)
        if text:
            return text

    # Fallback: try text/html and strip tags
    if mime_type == "text/html" and body_data:
        html = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", "", html).strip()

    return ""


def _format_inbox(summaries: list[tuple], header: str = "Inbox (unread):", unread_only: bool = False) -> str:
    """Format a list of (id, meta) tuples into a readable inbox view.

    Args:
        summaries: List of (message_id, meta_dict) tuples.
        header: Section header line.
        unread_only: If True, show unread indicator prefix.

    Returns:
        Multi-line formatted string.
    """
    lines = [header]
    for i, (msg_id, meta) in enumerate(summaries, 1):
        prefix = "● " if meta.get("unread") else "○ "
        lines.append(f"\n{prefix}{i}. {meta['from_']}")
        lines.append(f"   {meta['subject']}")
        if meta.get("date"):
            lines.append(f"   {meta['date']}")
        if meta.get("snippet"):
            snippet = meta["snippet"][:120].rstrip() + ("…" if len(meta["snippet"]) > 120 else "")
            lines.append(f"   {snippet}")

    lines.append(f"\nSay 'read email 1' to open any message.")
    return "\n".join(lines)


def _format_full_message(msg: dict) -> str:
    """Format a full Gmail message (with body) for terminal display.

    Args:
        msg: Full Gmail message dict (format='full').

    Returns:
        Multi-line formatted email string.
    """
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

    from_   = headers.get("From", "unknown")
    to      = headers.get("To", "unknown")
    subject = headers.get("Subject", "(no subject)")
    date    = _friendly_date(headers.get("Date", ""))
    body    = _get_plain_body(payload).strip()

    if not body:
        body = msg.get("snippet", "(no body)")

    # Trim very long bodies
    if len(body) > 2000:
        body = body[:2000].rstrip() + "\n\n[… message truncated]"

    lines = [
        f"From:    {from_}",
        f"To:      {to}",
        f"Subject: {subject}",
        f"Date:    {date}",
        "",
        body,
    ]
    return "\n".join(lines)


def _build_raw_message(to: str, subject: str, body: str) -> str:
    """Build a base64url-encoded RFC 2822 email ready for the Gmail send API.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        base64url-encoded string.
    """
    msg = MIMEMultipart()
    msg["to"]      = to
    msg["subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return raw


def _friendly_date(date_str: str) -> str:
    """Convert a RFC 2822 date string to a short readable format.

    Args:
        date_str: Raw date header value.

    Returns:
        Short date string or the original if parsing fails.
    """
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%b %d, %Y  %I:%M %p")
    except Exception:
        return date_str


def _extract_search_query(user_input: str) -> str:
    """Extract a Gmail search query from natural language.

    Args:
        user_input: Raw user message.

    Returns:
        Gmail query string (e.g. 'from:name@email.com') or empty string.
    """
    q = user_input.strip()
    patterns = [
        (r"emails?\s+from\s+(.+?)(?:\s+about\b|$)", lambda m: f"from:{m.group(1).strip()}"),
        (r"emails?\s+about\s+(.+?)(?:\s+from\b|$)", lambda m: f"subject:{m.group(1).strip()}"),
        (r"(?:find|search)\s+(?:for\s+)?emails?\s+(?:about\s+)?(.+)", lambda m: m.group(1).strip()),
    ]
    for pattern, builder in patterns:
        match = re.search(pattern, q, re.I)
        if match:
            return builder(match)
    return ""
