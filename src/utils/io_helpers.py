import json
from pathlib import Path
from typing import Any, Dict


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _to_yaml(value: Any, level: int = 0) -> str:
    indent = "  " * level
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{indent}{k}:")
                lines.append(_to_yaml(v, level + 1))
            else:
                lines.append(f"{indent}{k}: {json.dumps(v)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}-")
                lines.append(_to_yaml(item, level + 1))
            else:
                lines.append(f"{indent}- {json.dumps(item)}")
        return "\n".join(lines)
    return f"{indent}{json.dumps(value)}"


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(_to_yaml(payload) + "\n", encoding="utf-8")
