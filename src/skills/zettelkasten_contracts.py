"""Prompt contract loader and parser system for Zettelkasten skill.

Every LLM call in the skill goes through a contract:
  .txt  — prompt template with {{placeholders}}
  .yaml — parser type, temperature, fallback, grounding

Three parsers tolerate noisy local-model output:
  VOCAB_MATCH     — word-boundary search for a vocabulary token
  PREFIX_EXTRACT  — finds PREFIX: value lines (multiline, case-insensitive)
  PATTERN_EXTRACT — regex match anywhere in output
"""

import re
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


class ContractLoader:
    """Load, fill, call, and parse prompt contracts from _System/Prompt Library/."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.library_path = vault_path / "_System" / "Prompt Library"
        self._cache: dict[str, tuple[str, dict]] = {}

    def available(self) -> bool:
        return self.library_path.exists() and _YAML_AVAILABLE

    # ── Loading ────────────────────────────────────────────────────────────────

    def _load(self, name: str) -> tuple[str, dict]:
        if name in self._cache:
            return self._cache[name]
        txt_file = self.library_path / f"{name}.txt"
        yaml_file = self.library_path / f"{name}.yaml"
        if not txt_file.exists() or not yaml_file.exists():
            raise FileNotFoundError(f"Contract not found: {name}")
        template = txt_file.read_text(encoding="utf-8")
        contract = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        self._cache[name] = (template, contract)
        return template, contract

    # ── Template filling ───────────────────────────────────────────────────────

    @staticmethod
    def _fill(template: str, **kwargs) -> str:
        for key, value in kwargs.items():
            template = template.replace(f"{{{{{key}}}}}", str(value) if value is not None else "")
        return template

    # ── Parsers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _vocab_match(output: str, vocabulary: list[str]) -> Optional[str]:
        """Word-boundary search — tolerates preamble, explanation, case variation."""
        pattern = r"\b(" + "|".join(re.escape(v) for v in vocabulary) + r")\b"
        match = re.search(pattern, output, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _prefix_extract(output: str, prefix: str, max_results: Optional[int]) -> Optional[list[str]]:
        """Finds all PREFIX: value lines — tolerates extra lines and markdown noise."""
        pattern = rf"^{re.escape(prefix)}:\s*(.+)$"
        results = re.findall(pattern, output, re.MULTILINE | re.IGNORECASE)
        results = [r.strip() for r in results if r.strip()]
        if not results:
            return None
        if max_results:
            results = results[:max_results]
        return results

    @staticmethod
    def _pattern_extract(output: str, pattern: str) -> Optional[str]:
        """Extracts first regex match from anywhere in output."""
        match = re.search(pattern, output)
        return match.group(0) if match else None

    def _parse(self, output: str, contract: dict) -> Any:
        parser = contract.get("parser", "")
        config = contract.get("parser_config", {})
        if parser == "VOCAB_MATCH":
            return self._vocab_match(output, config.get("vocabulary", []))
        if parser == "PREFIX_EXTRACT":
            return self._prefix_extract(output, config.get("prefix", ""), config.get("max"))
        if parser == "PATTERN_EXTRACT":
            return self._pattern_extract(output, config.get("pattern", ""))
        return None

    # ── Grounding ──────────────────────────────────────────────────────────────

    def _apply_grounding(self, results: list[str], grounding_path: str) -> list[str]:
        """Drop results not present in the grounding file (e.g. vault-taxonomy.md)."""
        gfile = self.vault_path / grounding_path
        if not gfile.exists():
            return results
        content = gfile.read_text(encoding="utf-8").lower()
        kept = []
        for r in results:
            normalised = r.lstrip("#").lower().strip()
            if normalised in content or r.lower() in content:
                kept.append(r)
        return kept

    # ── Fallback ───────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_fallback(contract: dict, fallback_kwargs: dict) -> Any:
        fallback = contract.get("fallback", {})
        fb_type = fallback.get("type", "NONE")
        if fb_type == "SKIP":
            return None
        if fb_type == "NONE":
            return []
        if fb_type == "FIRST":
            return "__FIRST__"
        if fb_type == "VALUE":
            value = str(fallback.get("value", ""))
            for k, v in fallback_kwargs.items():
                value = value.replace(f"{{{{{k}}}}}", str(v))
            return value
        return None

    # ── LLM call (single-turn, no history) ────────────────────────────────────

    @staticmethod
    def _call_llm(prompt: str, temperature: float) -> str:
        """Fresh single-turn call — no chat history, no system prompt."""
        try:
            from src.llm_interface import call_local, call_cloud
            messages = [{"role": "user", "content": prompt}]
            response = call_local(messages, temperature=temperature)
            if response.error or not response.content.strip():
                response = call_cloud(messages, temperature=temperature)
            return response.content or ""
        except Exception:
            return ""

    # ── Public interface ───────────────────────────────────────────────────────

    def call(self, contract_name: str, **kwargs) -> Any:
        """
        Load contract → fill template → call LLM → parse output.
        Retries once on parse failure, then applies the contract fallback.
        Returns parsed value, fallback value, or None (SKIP).
        """
        if not self.available():
            return None
        try:
            template, contract = self._load(contract_name)
        except (FileNotFoundError, Exception):
            return None

        prompt = self._fill(template, **kwargs)
        temperature = float(contract.get("temperature", 0))

        output = self._call_llm(prompt, temperature)
        result = self._parse(output, contract)

        if result is None:
            output = self._call_llm(prompt, temperature)
            result = self._parse(output, contract)

        if result is None:
            return self._apply_fallback(contract, kwargs)

        grounding = contract.get("grounding")
        if grounding and isinstance(result, list):
            result = self._apply_grounding(result, grounding)

        return result


def get_loader(vault_path: Optional[Path] = None) -> Optional[ContractLoader]:
    """Return a ContractLoader if vault is configured and contracts are available."""
    if vault_path is None:
        try:
            from src.skills.zettelkasten_skill import _get_vault
            vault_path = _get_vault()
        except Exception:
            return None
    if vault_path is None:
        return None
    loader = ContractLoader(vault_path)
    return loader if loader.available() else None
