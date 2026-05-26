"""Local Ollama + cloud Gemini/Anthropic LLM calls with tiered routing and fallback."""
# Implements NFR-SEC-001 (Local execution only for Tiers 0–3 — Ollama runs on-device; cloud only for Tier 4+)

import time
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Generator

from src.secrets import get_secret

# ── Config (DB-backed secrets, env var fallback) ──────────────────────────────

# Defaults reflect the high-VRAM tier — model_manager.select_model() overrides these
# dynamically at call time based on actual free VRAM. Change via secrets/env if needed.
LOCAL_MODEL          = get_secret("LOCAL_MODEL",          "phi3.5:3.8b-mini-instruct-q8_0")
LOCAL_THINKING_MODEL = get_secret("LOCAL_THINKING_MODEL", "phi4:14b-q4_K_M")
LOCAL_CODING_MODEL   = get_secret("LOCAL_CODING_MODEL",   "qwen2.5-coder:14b-instruct-q4_K_M")
ROUTER_MODEL         = get_secret("ROUTER_MODEL", "gemma2:2b")
OLLAMA_URL           = get_secret("OLLAMA_URL", "http://localhost:11434")
LOCAL_PROVIDER       = get_secret("LOCAL_PROVIDER", "ollama")
LM_STUDIO_URL        = get_secret("LM_STUDIO_URL", "http://localhost:1234/v1")

CLOUD_PROVIDER    = get_secret("CLOUD_PROVIDER", "gemini")
# gemini-1.5-flash: free tier 1,500 RPD / 15 RPM — far more generous than 2.0-flash free tier.
# Override via Doppler/secrets (CLOUD_MODEL_PRO, CLOUD_MODEL_FLASH) to use paid models.
CLOUD_MODEL       = get_secret("CLOUD_MODEL",       "gemini-1.5-flash")
CLOUD_MODEL_PRO   = get_secret("CLOUD_MODEL_PRO",   "gemini-1.5-flash")
CLOUD_MODEL_FLASH = get_secret("CLOUD_MODEL_FLASH", "gemini-1.5-flash")
GEMINI_API_KEY    = get_secret("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY", "")



class RouteType(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    BMAD  = "bmad"


@dataclass
class LLMResponse:
    content: str
    route: RouteType
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None


# ── Streaming (local only) ────────────────────────────────────────────────────

def stream_local(
    messages: list[dict],
    system: str = "",
    model: str = "",
) -> Generator[str, None, None]:
    """Yield tokens from the local model as they arrive."""
    ensure_ollama_running()
    m = model or LOCAL_MODEL
    try:
        import ollama
        msgs = [{"role": "system", "content": system}, *messages] if system else messages
        for chunk in ollama.chat(model=m, messages=msgs, stream=True):
            token = chunk["message"]["content"]
            if token:
                yield token
    except Exception:
        return


# ── Cloud streaming ───────────────────────────────────────────────────────────
# Implements FR-UI-005 (LLM token streaming for conversational turns — CR-031)

def _stream_gemini(
    messages: list[dict],
    system: str = "",
    model: str = "",
) -> Generator[str, None, None]:
    """Yield tokens from Gemini via OpenAI-compatible streaming endpoint.

    Implements FR-UI-005 / TASK-UI-031-a.
    """
    if not GEMINI_API_KEY:
        return
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        full_messages = (
            [{"role": "system", "content": system}] if system else []
        ) + messages
        stream = client.chat.completions.create(
            model=model or CLOUD_MODEL,
            messages=full_messages,
            stream=True,
            max_tokens=4000,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception:
        return


def _stream_anthropic(
    messages: list[dict],
    system: str = "",
    model: str = "claude-sonnet-4-20250514",
) -> Generator[str, None, None]:
    """Yield tokens from Anthropic via native streaming context manager.

    Implements FR-UI-005 / TASK-UI-031-a.
    """
    if not ANTHROPIC_API_KEY:
        return
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        kwargs: dict = {
            "model": model,
            "max_tokens": 4000,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
    except Exception:
        return


def stream_cloud(
    messages: list[dict],
    system: str = "",
    model: str = "",
) -> Generator[str, None, None]:
    """Yield tokens from the configured cloud provider as they arrive.

    Dispatches to Gemini or Anthropic based on CLOUD_PROVIDER secret.
    Implements FR-UI-005 / TASK-UI-031-a.
    """
    m = model or CLOUD_MODEL
    if CLOUD_PROVIDER == "anthropic":
        yield from _stream_anthropic(messages, system=system, model=m)
    else:
        yield from _stream_gemini(messages, system=system, model=m)


# ── Local: Ollama ──────────────────────────────────────────────────

def call_ollama(
    messages: list[dict],
    system: str = "",
    model: str = LOCAL_MODEL,
    tools: list[dict] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    try:
        import ollama

        kwargs = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages] if system else messages,
            "options": {"temperature": temperature},
        }
        if tools:
            kwargs["tools"] = tools

        resp = ollama.chat(**kwargs)
        content = resp["message"]["content"] or ""
        if resp["message"].get("tool_calls"):
            content = json.dumps({"tool_calls": resp["message"]["tool_calls"]})

        return LLMResponse(content=content, route=RouteType.LOCAL)

    except Exception as e:
        return LLMResponse(content="", route=RouteType.LOCAL, error=str(e))


def list_ollama_models() -> list[str]:
    try:
        import ollama
        return [m["name"] for m in ollama.list().get("models", [])]
    except Exception as e:
        return [f"Error: {e}"]


def ping_ollama() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def ensure_ollama_running() -> bool:
    """Check if Ollama is running, and try to start it if not."""
    if ping_ollama():
        return True

    import subprocess
    import platform
    import time

    try:
        if platform.system() == "Windows":
            # Start Ollama tray app on Windows
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Start Ollama service on Linux/macOS
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # Wait up to 10s for it to wake up
        for _ in range(10):
            time.sleep(1)
            if ping_ollama():
                return True
    except Exception:
        pass

    return False


# ── Unified local dispatch ────────────────────────────────────────────────────

def call_local(
    messages: list[dict],
    system: str = "",
    model: str = "",
    tools: list[dict] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    ensure_ollama_running()
    m = model or LOCAL_MODEL
    return call_ollama(messages, system=system, model=m, tools=tools, temperature=temperature)


def ping_local() -> bool:
    return ping_ollama()


def list_local_models() -> list[str]:
    return list_ollama_models()


# ── Cloud: Gemini (OpenAI-compatible endpoint) ────────────────────────────────

# gemini-2.0-flash pricing per 1k tokens (approximate)
_GEMINI_COST_IN  = 0.00010 / 1000
_GEMINI_COST_OUT = 0.00040 / 1000

def call_gemini(
    messages: list[dict],
    system: str = "",
    model: str = CLOUD_MODEL,
    max_tokens: int = 4000,
    tools: list[dict] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    if not GEMINI_API_KEY:
        return LLMResponse(content="", route=RouteType.CLOUD, error="GEMINI_API_KEY not set")

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        kwargs = {"model": model, "messages": full_messages, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools

        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""

        if resp.choices[0].message.tool_calls:
            calls = [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in resp.choices[0].message.tool_calls
            ]
            content = json.dumps({"tool_calls": calls})

        tokens_in  = resp.usage.prompt_tokens if resp.usage else 0
        tokens_out = resp.usage.completion_tokens if resp.usage else 0
        cost = tokens_in * _GEMINI_COST_IN + tokens_out * _GEMINI_COST_OUT

        return LLMResponse(
            content=content, route=RouteType.CLOUD,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost,
        )

    except Exception as e:
        return LLMResponse(content="", route=RouteType.CLOUD, error=str(e))


# ── Cloud: Anthropic (fallback if configured) ─────────────────────────────────

_ANTHROPIC_COST_IN  = 0.003 / 1000
_ANTHROPIC_COST_OUT = 0.015 / 1000

def call_anthropic(
    messages: list[dict],
    system: str = "",
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4000,
    tools: list[dict] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    if not ANTHROPIC_API_KEY:
        return LLMResponse(content="", route=RouteType.CLOUD, error="ANTHROPIC_API_KEY not set")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages, "temperature": temperature}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        resp = client.messages.create(**kwargs)
        parts = []
        for block in resp.content:
            if block.type == "text":
                parts.append(block.text)
            elif block.type == "tool_use":
                parts.append(json.dumps({"tool_use": {"name": block.name, "input": block.input}}))

        tokens_in  = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens
        cost = tokens_in * _ANTHROPIC_COST_IN + tokens_out * _ANTHROPIC_COST_OUT

        return LLMResponse(
            content="\n".join(parts), route=RouteType.CLOUD,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost,
        )

    except Exception as e:
        return LLMResponse(content="", route=RouteType.CLOUD, error=str(e))


# ── Unified cloud dispatch ────────────────────────────────────────────────────

def call_cloud(
    messages: list[dict],
    system: str = "",
    model: str = "",
    max_tokens: int = 4000,
    tools: list[dict] = None,
    temperature: float = 0.7,
) -> LLMResponse:
    m = model or CLOUD_MODEL
    if CLOUD_PROVIDER == "anthropic":
        return call_anthropic(messages, system=system, model=m, max_tokens=max_tokens, tools=tools, temperature=temperature)
    return call_gemini(messages, system=system, model=m, max_tokens=max_tokens, tools=tools, temperature=temperature)


# ── Retry with exponential backoff ────────────────────────────────────────────

def call_with_retry(fn, *args, max_retries: int = 3, **kwargs) -> LLMResponse:
    for attempt in range(max_retries):
        result = fn(*args, **kwargs)
        if not result.error:
            return result
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    return result


# ── Confidence scoring ────────────────────────────────────────────────────────

def estimate_confidence(response: str) -> float:
    low_markers = [
        "i'm not sure", "i don't know", "i cannot", "i'm unable",
        "not certain", "not confident", "unclear", "uncertain",
    ]
    text = response.lower()
    for marker in low_markers:
        if marker in text:
            return 0.4
    if response.count("```") % 2 != 0:
        return 0.6
    return 0.85


# ── DECOMPOSE_PROMPT template ─────────────────────────────────────────────────

DECOMPOSE_PROMPT = """You are a senior project manager using the PARA methodology.

Project: {project_name}
Description: {project_description}
Priority: {project_priority}

{global_context}
{project_context}

Decompose this project into discrete, actionable tasks. Each task must:
- Be completable in 30 or 60 minutes
- Be independently executable
- Have a clear, verb-first description

Return ONLY a JSON array with no markdown wrapping:
[
  {{
    "description": "verb-first task description",
    "time_estimate_minutes": 30,
    "blocked_by": null
  }}
]
"""
