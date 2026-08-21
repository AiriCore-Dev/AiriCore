from dataclasses import dataclass


@dataclass(frozen=True)
class VoteSummary:
    week_index: int
    counts: dict[str, int]
    percentages: dict[str, float]
    winner: str
    priority: str


def normalized_user_id(user_id: str | int) -> str:
    value = str(user_id).strip()
    if not value or not value.isdigit():
        raise ValueError("用户身份无效")
    return value
