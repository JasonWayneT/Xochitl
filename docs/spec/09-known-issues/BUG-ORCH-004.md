# BUG-ORCH-004 — Aggressive Cloud Fallback: Local-first intent ignored during systemic failures

## Status
**FIXED** — `src/router.py` `_route_local()`

## Root Cause
1. **Low Threshold**: `_route_local` had a `_failure_threshold` of 1. If a local model failed once (e.g. timeout, context length exceeded, or Ollama waking up), it immediately fell back to the cloud.
2. **Category Agnosticism**: The fallback logic didn't care which category was being processed. `file_operations` (reading large folder trees) often uses many tokens. When local failed, these huge prompts were sent to the Gemini Free Tier, immediately hitting 429 quota limits.
3. **Unexpected Cost**: The user expected local-only execution for these tiers, but the system was silently "leaking" requests to the cloud.

## Fix
1. **Force Local**: Added `_FORCE_LOCAL_CATEGORIES` (file_operations, task_management, etc.). These categories will now NEVER fall back to the cloud automatically. If they fail locally, they return the local error so the user can fix their local environment (e.g. pull a model or restart Ollama).
2. **Strict Confidence**: Local responses for these categories are now accepted even if confidence is lower than the threshold, prioritizing local availability over cloud accuracy for these specific tasks.

## Regression AC
`AC-BUG-ORCH-004`: A query classified as `file_operations` must never trigger a cloud LLM call unless the user explicitly forces it. It should fail locally rather than hitting cloud quotas.

## Date
2026-05-05
