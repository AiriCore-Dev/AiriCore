import json
import math
from dataclasses import dataclass
from pathlib import Path

from .parser import ITEM_RE


PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class ItemEntry:
    code: str
    name: str
    path: Path


@dataclass(frozen=True, slots=True)
class ItemPage:
    entries: tuple[ItemEntry, ...]
    page: int
    total_pages: int
    start: int


class ItemCatalog:
    def __init__(self, root: Path | str | None = None):
        self.root = (Path(root) if root is not None else Path(__file__).resolve().parents[1] / 'assets/evidence').resolve()
        try:
            payload = json.loads((self.root / 'items.json').read_text(encoding='utf-8'))
            if not isinstance(payload, dict) or payload.get('version') != 1 or not isinstance(payload.get('items'), list):
                raise ValueError('物品目录格式无效')
            entries = []
            seen = set()
            for record in payload['items']:
                code = record['code']
                name = record['name']
                relative = Path(record['path'])
                path = (self.root / relative).resolve()
                if not isinstance(code, str) or not ITEM_RE.fullmatch(code) or code != code.upper() or code in seen or not isinstance(name, str) or not name.strip() or relative.is_absolute() or not path.is_relative_to(self.root) or '..' in relative.parts:
                    raise ValueError('物品目录条目无效')
                seen.add(code)
                entries.append(ItemEntry(code, name, path))
            self._entries = tuple(entries)
            self._by_code = {entry.code: entry for entry in entries}
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ValueError('物品目录无法读取或格式无效') from error

    def entries(self) -> tuple[ItemEntry, ...]:
        return self._entries

    def get(self, code: str) -> ItemEntry:
        return self._by_code[code.strip().upper()]

    def page(self, page: int = 1) -> ItemPage:
        total = max(1, math.ceil(len(self._entries) / PAGE_SIZE))
        bounded = min(max(page, 1), total)
        start = (bounded - 1) * PAGE_SIZE
        return ItemPage(self._entries[start:start + PAGE_SIZE], bounded, total, start)
