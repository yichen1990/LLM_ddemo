# app/postprocess.py
import json
from typing import Callable, Type, TypeVar, Any
from pydantic import ValidationError

T = TypeVar("T")


def _extract_first_json_object(text: str) -> str:
    """
    Extract the first top-level JSON object from a string, even if surrounded by prose/markdown.
    Works by scanning for matching braces.
    """
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    # If we never closed braces, return original
    return text


def parse_or_repair(
    raw: str,
    model_cls: Type[T],
    repair_fn: Callable[[str, str], str],
    max_tries: int = 5,
) -> T:
    """
    Try to parse raw as JSON -> validate with Pydantic.
    If it fails, attempt repair. Also tries extracting the first JSON object from raw.
    """
    last = raw

    for _ in range(max_tries + 1):
        candidate = _extract_first_json_object(last)

        try:
            obj: Any = json.loads(candidate)
            return model_cls.model_validate(obj)
        except (json.JSONDecodeError, ValidationError) as e:
            last = repair_fn(last, str(e))

    raise RuntimeError("Failed to produce valid JSON after repair attempts.")
