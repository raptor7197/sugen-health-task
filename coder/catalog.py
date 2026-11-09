from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STEM_SPLIT = re.compile(r"[&/]")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return STEM_SPLIT.split(value.strip())[0].strip().upper() or None


@dataclass(frozen=True)
class Category:
    code: str
    title: str
    chapter: str
    leaf: bool
    residual: bool
    depth: int
    tokens: tuple[str, ...]


class Catalogue:
    def __init__(self, rows: list[dict[str, Any]]):
        self.categories: dict[str, Category] = {}
        for row in rows:
            code = normalize_code(row.get("code"))
            title = str(row.get("title") or "").strip()
            if not code or not title:
                continue
            category = Category(
                code=code,
                title=title,
                chapter=str(row.get("chapter", "")),
                leaf=bool(row.get("leaf", False)),
                residual=bool(row.get("residual", False)),
                depth=int(row.get("depth", 0)),
                tokens=tuple(token.lower() for token in TOKEN_RE.findall(title)),
            )
            self.categories[code] = category
        if not self.categories:
            raise ValueError("MMS catalogue contains no valid categories")
        self.codes = frozenset(self.categories)

    @classmethod
    def load(cls, path: str | Path) -> "Catalogue":
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, list):
            raise ValueError("MMS catalogue must be a JSON list")
        return cls(data)

    def get(self, code: str) -> Category | None:
        return self.categories.get(normalize_code(code) or "")
