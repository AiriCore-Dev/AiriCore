import hashlib
import random


def seed_for(scope: str, week_index: int, user_id: str, node_id: str) -> int:
    raw = "|".join((str(scope), str(week_index), str(user_id), str(node_id))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def stream(seed: int, label: str) -> random.Random:
    raw = f"{seed}|{label}".encode("utf-8")
    return random.Random(int.from_bytes(hashlib.sha256(raw).digest()[:8], "big"))
