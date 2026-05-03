"""YAML load/dump helpers shared across skills. Requires pyyaml>=6.0.0."""


def yaml_load(text: str) -> dict:
    """Safe YAML load. Returns empty dict on failure."""
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError as e:
        raise ImportError("pyyaml is required: pip install pyyaml>=6.0.0") from e
    except Exception:
        return {}


def yaml_dump(data: dict) -> str:
    """Safe YAML dump with unicode support."""
    try:
        import yaml
        return yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except ImportError as e:
        raise ImportError("pyyaml is required: pip install pyyaml>=6.0.0") from e
