from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Type


def read_json_file(
    path: str | Path,
    default: Any,
    *,
    expected_type: Type[Any] | tuple[Type[Any], ...] | None = None,
) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return copy.deepcopy(default)

    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return copy.deepcopy(default)

    if expected_type is not None and not isinstance(data, expected_type):
        return copy.deepcopy(default)
    return data


def write_json_file(path: str | Path, payload: Any) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
