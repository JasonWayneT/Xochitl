"""YAML load/dump helpers shared across skills."""


def yaml_load(text: str) -> dict:
    """Safe YAML load. Returns empty dict on failure."""
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _simple_yaml_load(text)
    except Exception:
        return {}


def yaml_dump(data: dict) -> str:
    """Safe YAML dump with unicode support and a stdlib fallback."""
    try:
        import yaml
        return yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except ImportError:
        return _simple_yaml_dump(data)


def _simple_yaml_dump(data: dict, indent: int = 0) -> str:
    lines: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.append(_simple_yaml_dump(value, indent + 2).rstrip())
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{pad}  -")
                    lines.append(_simple_yaml_dump(item, indent + 4).rstrip())
                else:
                    lines.append(f"{pad}  - {_format_scalar(item)}")
        else:
            lines.append(f"{pad}{key}: {_format_scalar(value)}")
    return "\n".join(lines) + "\n"


def _simple_yaml_load(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]
    rows = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            rows.append((len(raw) - len(raw.lstrip(" ")), stripped))

    for index, (indent, line) in enumerate(rows):
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if line.startswith("- "):
            value = _parse_scalar(line[2:].strip())
            if isinstance(parent, list):
                parent.append(value)
            continue

        if ":" not in line or not isinstance(parent, dict):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            parent[key] = _parse_scalar(value)
            continue

        next_row = rows[index + 1] if index + 1 < len(rows) else None
        child: dict | list = [] if next_row and next_row[0] > indent and next_row[1].startswith("- ") else {}
        parent[key] = child
        stack.append((indent, child))
    return root


def _format_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or text.strip() != text or any(ch in text for ch in ":#[]{}"):
        return repr(text)
    return text


def _parse_scalar(value: str):
    if value in {"null", "None"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
