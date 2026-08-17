from __future__ import annotations

from pathlib import Path
from typing import Any


def load_yaml_subset(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ModuleNotFoundError:
        lines = [
            (len(raw) - len(raw.lstrip(" ")), raw.strip())
            for raw in path.read_text(encoding="utf-8").splitlines()
            if raw.strip() and not raw.lstrip().startswith("#")
        ]
        parser = _SubsetYamlParser(lines)
        return parser.parse_mapping(0)


class _SubsetYamlParser:
    def __init__(self, lines: list[tuple[int, str]]) -> None:
        self.lines = lines
        self.index = 0

    def parse_block(self, indent: int) -> Any:
        if self.index >= len(self.lines):
            return None
        current_indent, text = self.lines[self.index]
        if current_indent < indent:
            return None
        if text.startswith("- "):
            return self.parse_list(current_indent)
        return self.parse_mapping(current_indent)

    def parse_mapping(self, indent: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        while self.index < len(self.lines):
            current_indent, text = self.lines[self.index]
            if current_indent < indent or text.startswith("- "):
                break
            if current_indent > indent:
                break
            key, value = _split_key_value(text)
            self.index += 1
            if value == "":
                if self.index < len(self.lines) and self.lines[self.index][0] > current_indent:
                    result[key] = self.parse_block(self.lines[self.index][0])
                else:
                    result[key] = None
            else:
                result[key] = _parse_scalar(value)
        return result

    def parse_list(self, indent: int) -> list[Any]:
        result: list[Any] = []
        while self.index < len(self.lines):
            current_indent, text = self.lines[self.index]
            if current_indent != indent or not text.startswith("- "):
                break
            content = text[2:].strip()
            self.index += 1
            if not content:
                item: Any = self.parse_block(indent + 2)
                result.append(item)
                continue
            if ":" in content:
                key, value = _split_key_value(content)
                item = {key: _parse_scalar(value) if value else self.parse_block(indent + 2)}
                if self.index < len(self.lines) and self.lines[self.index][0] > indent:
                    nested = self.parse_mapping(indent + 2)
                    item.update(nested)
                result.append(item)
            else:
                result.append(_parse_scalar(content))
        return result


def _split_key_value(text: str) -> tuple[str, str]:
    key, _, value = text.partition(":")
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "":
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value == "[]":
        return []
    if value == "{}":
        return {}
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
