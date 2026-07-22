import time
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, TYPE_CHECKING

from . import llm_client

if TYPE_CHECKING:
    from .memory import GroupContext

logger = logging.getLogger("airi_llm")

KNOWLEDGE_MAX_ENTRIES = 150
KNOWLEDGE_CONTENT_MAX = 150
KNOWLEDGE_TAG_MAX = 5
KNOWLEDGE_EXTRACT_MIN_ENTRIES = 8
KNOWLEDGE_EXTRACT_INTERVAL_SECS = 600
KNOWLEDGE_ANALYZE_ENTRIES = 20
KNOWLEDGE_RETRIEVE_TOP_K = 4
KNOWLEDGE_SUMMARY_MAX_ENTRIES = 40


@dataclass
class KnowledgeEntry:
    entry_id: str
    content: str
    tags: List[str]
    created_at: float
    updated_at: float
    hit_count: int = 0


def _knowledge_index_summary(entries: List[KnowledgeEntry]) -> str:
    if not entries:
        return ""
    tail = entries[-KNOWLEDGE_SUMMARY_MAX_ENTRIES:]
    return "\n".join(f"[{e.entry_id}] {e.content}" for e in tail)


def _tag_prefilter(entries: List[KnowledgeEntry], message_text: str) -> List[KnowledgeEntry]:
    msg_lower = message_text.lower()
    return [e for e in entries if any(tag.lower() in msg_lower for tag in e.tags)]


async def extract_and_update(ctx: "GroupContext", gid: str, state: Any) -> None:
    from .memory import _render_entries_plain, _get_bg_lock

    now = time.time()
    if now - ctx.knowledge_updated_at < KNOWLEDGE_EXTRACT_INTERVAL_SECS:
        return
    if len(ctx.entries) < KNOWLEDGE_EXTRACT_MIN_ENTRIES:
        return

    lock = _get_bg_lock(state, gid)
    if lock.locked():
        return
    async with lock:
        ctx.knowledge_updated_at = now
        recent = list(ctx.entries)[-KNOWLEDGE_ANALYZE_ENTRIES:]
        convo = _render_entries_plain(recent)
        existing_summary = _knowledge_index_summary(ctx.knowledge)
        items = await llm_client.extract_knowledge(convo, existing_summary)
        if not items:
            return

        existing_contents = {e.content for e in ctx.knowledge}
        changed = False
        for item in items:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "")).strip()
            content = str(item.get("content", "")).strip()[:KNOWLEDGE_CONTENT_MAX]
            raw_tags = item.get("tags") or []
            tags = [str(t).strip()[:20] for t in raw_tags if str(t).strip()][:KNOWLEDGE_TAG_MAX]
            entry_id = str(item.get("entry_id", "")).strip()

            if action == "add" and content:
                if content in existing_contents:
                    continue
                existing_contents.add(content)
                ctx.knowledge_entry_count += 1
                new_id = f"k{ctx.knowledge_entry_count}"
                ctx.knowledge.append(KnowledgeEntry(
                    entry_id=new_id, content=content, tags=tags,
                    created_at=now, updated_at=now,
                ))
                changed = True
                logger.info(f"群 {gid} 知识库新增: {content[:50]}")
            elif action == "update" and entry_id and content:
                for e in ctx.knowledge:
                    if e.entry_id == entry_id:
                        existing_contents.discard(e.content)
                        e.content = content
                        existing_contents.add(content)
                        if tags:
                            e.tags = tags
                        e.updated_at = now
                        changed = True
                        break
            elif action == "delete" and entry_id:
                before = len(ctx.knowledge)
                ctx.knowledge = [e for e in ctx.knowledge if e.entry_id != entry_id]
                if len(ctx.knowledge) < before:
                    changed = True

        if len(ctx.knowledge) > KNOWLEDGE_MAX_ENTRIES:
            ctx.knowledge.sort(key=lambda e: (e.hit_count, e.updated_at))
            ctx.knowledge = ctx.knowledge[-KNOWLEDGE_MAX_ENTRIES:]
            changed = True

        if changed:
            state.dirty.add(gid)


async def retrieve_for_reply(ctx: "GroupContext", gid: str, state: Any, message_text: str) -> List[str]:
    if not ctx.knowledge or not message_text.strip():
        return []

    candidates = _tag_prefilter(ctx.knowledge, message_text)
    if not candidates:
        return []

    now = time.time()
    if len(candidates) <= 2:
        top = candidates[:KNOWLEDGE_RETRIEVE_TOP_K]
        for e in top:
            e.hit_count += 1
            e.updated_at = now
        state.dirty.add(gid)
        return [e.content for e in top]

    candidate_contents = [e.content for e in candidates]
    relevant_indices = await llm_client.score_knowledge_relevance(message_text, candidate_contents)
    if not relevant_indices:
        return []

    result = []
    for idx in relevant_indices[:KNOWLEDGE_RETRIEVE_TOP_K]:
        if 0 <= idx < len(candidates):
            e = candidates[idx]
            e.hit_count += 1
            e.updated_at = now
            result.append(e.content)

    if result:
        state.dirty.add(gid)
    return result
