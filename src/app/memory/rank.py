# src/app/memory/rank.py

from datetime import datetime

def recency_score(created_at: str) -> int:
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", ""))
        age_days = (datetime.utcnow() - dt).days
        if age_days <= 30:
            return 2
        if age_days <= 90:
            return 1
    except Exception:
        pass
    return 0


def term_match_score(text: str, terms: list[str]) -> int:
    text_l = text.lower()
    hits = sum(1 for t in terms if t in text_l)
    return min(hits, 2)


def rank_items(
    items: list[dict],
    *,
    terms: list[str],
    source_preference: str | None,
    time_hint: str | None,
) -> list[dict]:

    for item in items:
        score = 0

        # Source preference
        if source_preference == item["type"]:
            score += 2

        # Time bias
        if time_hint == "recent":
            score += recency_score(item.get("created_at", ""))
        elif time_hint == "past":
            score += 2 - recency_score(item.get("created_at", ""))

        # Term matches
        score += term_match_score(item.get("content", ""), terms)

        item["_score"] = score

    return sorted(items, key=lambda x: x["_score"], reverse=True)
