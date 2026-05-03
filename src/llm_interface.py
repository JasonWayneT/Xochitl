"""Local Ollama + cloud Gemini/Anthropic LLM calls with tiered routing and fallback."""

import os
import time
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Generator

from dotenv import load_dotenv

load_dotenv()

# ── Config from .env ──────────────────────────────────────────────────────────

LOCAL_MODEL     = os.getenv("LOCAL_MODEL", "gemma4-e4b")
LOCAL_THINKING_MODEL = os.getenv("LOCAL_THINKING_MODEL", "gemma-4-26B-A4B-it-GGUF:UD-IQ4_X")
LOCAL_CODING_MODEL   = os.getenv("LOCAL_CODING_MODEL", "qwen2.5-coder:7b-instruct-q8_0")
ROUTER_MODEL    = os.getenv("ROUTER_MODEL", "gemma2:2b")
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://localhost:11434")

CLOUD_PROVIDER  = os.getenv("CLOUD_PROVIDER", "gemini")         # "gemini" or "anthropic"
CLOUD_MODEL     = os.getenv("CLOUD_MODEL", "gemini-1.5-pro")
CLOUD_MODEL_PRO = os.getenv("CLOUD_MODEL_PRO", "gemini-1.5-pro")
CLOUD_MODEL_FLASH = os.getenv("CLOUD_MODEL_FLASH", "gemini-2.0-flash")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")



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


# ── Local: Ollama ──────────────────────────────────────────────────

def call_ollama(
    messages: list[dict],
    system: str = "",
    model: str = LOCAL_MODEL,
    tools: list[dict] = None,
) -> LLMResponse:
    try:
        import ollama

        kwargs = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages] if system else messages,
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
) -> LLMResponse:
    ensure_ollama_running()
    m = model or LOCAL_MODEL
    return call_ollama(messages, system=system, model=m, tools=tools)


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

        kwargs = {"model": model, "messages": full_messages, "max_tokens": max_tokens}
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
) -> LLMResponse:
    if not ANTHROPIC_API_KEY:
        return LLMResponse(content="", route=RouteType.CLOUD, error="ANTHROPIC_API_KEY not set")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
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
) -> LLMResponse:
    m = model or CLOUD_MODEL
    if CLOUD_PROVIDER == "anthropic":
        return call_anthropic(messages, system=system, model=m, max_tokens=max_tokens, tools=tools)
    return call_gemini(messages, system=system, model=m, max_tokens=max_tokens, tools=tools)


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
