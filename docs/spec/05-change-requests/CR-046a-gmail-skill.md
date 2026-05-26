# CR-046a — Gmail Skill

| Field       | Value                          |
|-------------|--------------------------------|
| CR ID       | CR-046a                        |
| Status      | Implemented                    |
| Priority    | High                           |
| Author      | Jason / Xochitl session        |
| Created     | 2026-05-25                     |
| Depends on  | google_auth.py (OAuth, done)   |
| Implements  | FR-GMAIL-001–004               |

## Problem Statement

Xochitl has OAuth credentials and working Google auth (verified 2026-05-25) but
no skill to actually read or send Gmail. Email is a core JARVIS capability and a
prerequisite for Morning Briefing (CR-046).

## Solution

Add `src/skills/gmail_skill.py` backed by Gmail API v1. Four operations:

| Intent     | What it does                                        |
|------------|-----------------------------------------------------|
| `inbox`    | List last N unread messages with from/subject/snippet |
| `search`   | Query by Gmail search syntax (from:, subject:, etc.) |
| `read`     | Open full body of email #N from the last shown list  |
| `send`     | Compose and send a new email                         |
| `mark_read`| Remove UNREAD label from email #N                    |
| `archive`  | Remove UNREAD + INBOX labels from email #N           |

Context tracking: `gmail_last_list` stored in session context so user can say
"read the first one" after any inbox or search listing.

## Requirements

| ID           | Description                                                          |
|--------------|----------------------------------------------------------------------|
| FR-GMAIL-001 | Xochitl shall list unread inbox messages with from/subject/date/snippet |
| FR-GMAIL-002 | Xochitl shall search Gmail using natural-language or explicit queries |
| FR-GMAIL-003 | Xochitl shall send email given a recipient, subject, and body         |
| FR-GMAIL-004 | Xochitl shall mark emails as read or archive them by index            |
| NFR-GMAIL-001 | No email credentials or content shall be logged or persisted to disk  |

## Acceptance Criteria

| ID             | Criterion                                                             |
|----------------|-----------------------------------------------------------------------|
| AC-CR046a-001  | `can_handle("check my email")` returns ≥ 0.90                        |
| AC-CR046a-002  | `can_handle("send an email to bob")` returns ≥ 0.90                  |
| AC-CR046a-003  | `can_handle("find emails from alice")` returns ≥ 0.90                |
| AC-CR046a-004  | `can_handle("what is the weather")` returns 0.0                      |
| AC-CR046a-005  | `_extract_search_query("emails from alice@gmail.com")` returns `"from:alice@gmail.com"` |
| AC-CR046a-006  | `_format_inbox()` includes sender, subject, and snippet              |
| AC-CR046a-007  | `_format_full_message()` includes From, To, Subject, Date, body      |
| AC-CR046a-008  | `_build_raw_message()` returns a non-empty base64 string             |
| AC-CR046a-009  | Missing auth returns FileNotFoundError message, not an exception      |

## Files Changed

| File                                      | Change                         |
|-------------------------------------------|--------------------------------|
| `src/skills/gmail_skill.py`               | New — GmailSkill               |
| `src/chat.py`                             | Register GmailSkill in builtins |
| `smoke_test.py`                           | 9 new AC tests                 |
| `docs/spec/05-change-requests/CR-046a-*`  | This file                      |

## Auth

Uses `src/google_auth.get_service("gmail", "v1")` — token at `~/.xochitl/google_token.json`.
Scopes already granted: `gmail.readonly`, `gmail.send`, `gmail.modify`.

## Future Work

- Reply to email (thread-aware)
- Label management
- Attachment handling
- Used by Morning Briefing (CR-046) for overnight email summary
