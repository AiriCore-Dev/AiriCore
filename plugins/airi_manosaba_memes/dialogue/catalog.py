import json
import math
from dataclasses import dataclass
from pathlib import Path


CATEGORIES = ("场景", "插图", "特效")
GRID_COLUMNS = 5
GRID_ROWS = 5
PAGE_SIZE = GRID_COLUMNS * GRID_ROWS


@dataclass(frozen=True, slots=True)
class BackgroundEntry:
    code: str
    category: str
    path: Path
    name: str


@dataclass(frozen=True, slots=True)
class BackgroundPage:
    entries: tuple[BackgroundEntry, ...]
    page: int
    total_pages: int
    start: int


class BackgroundCatalog:
    def __init__(self, root: Path | str | None = None):
        self.root = (
            Path(root)
            if root is not None
            else Path(__file__).resolve().parents[1] / "assets" / "dialogue"
        ).resolve()
        self._entries = self._load()
        self._by_code = {entry.code: entry for entry in self._entries}

    def _load(self) -> tuple[BackgroundEntry, ...]:
        try:
            payload = json.loads(
                (self.root / "backgrounds.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("背景目录无法读取") from error
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("背景目录版本无效")
        records = payload.get("backgrounds")
        if not isinstance(records, list):
            raise ValueError("背景目录格式无效")
        entries = []
        seen = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("背景目录条目格式无效")
            try:
                code = str(record["code"]).upper()
                category = str(record["category"])
                relative = Path(str(record["path"]))
                name = str(record["name"])
            except KeyError as error:
                raise ValueError("背景目录条目缺少字段") from error
            if (
                not re_fullmatch_background(code)
                or category not in CATEGORIES
                or not name
                or relative.is_absolute()
                or ".." in relative.parts
                or code in seen
            ):
                raise ValueError(f"背景目录条目无效：{code}")
            seen.add(code)
            entries.append(
                BackgroundEntry(
                    code=code,
                    category=category,
                    path=(self.root / relative).resolve(),
                    name=name,
                )
            )
        return tuple(entries)

    def entries(self, category: str | None = None) -> tuple[BackgroundEntry, ...]:
        if category is None:
            return self._entries
        if category not in CATEGORIES:
            raise ValueError(f"背景分类无效：{category}")
        return tuple(entry for entry in self._entries if entry.category == category)

    def get(self, code: str) -> BackgroundEntry:
        return self._by_code[code.strip().upper()]

    def page(self, category: str, page: int = 1) -> BackgroundPage:
        values = self.entries(category)
        total_pages = max(1, math.ceil(len(values) / PAGE_SIZE))
        bounded = min(max(int(page), 1), total_pages)
        offset = (bounded - 1) * PAGE_SIZE
        return BackgroundPage(
            entries=values[offset : offset + PAGE_SIZE],
            page=bounded,
            total_pages=total_pages,
            start=offset,
        )


def re_fullmatch_background(code: str) -> bool:
    return (
        len(code) == 6
        and code.startswith("@BG")
        and code[3:].isdigit()
    )
