import sqlite3
import re
import math
from pathlib import Path
from datetime import datetime, timezone
from runtime.memory.config import MEMORY_WEIGHTS, TYPE_BONUS

DB = Path(__file__).parent / "memory.db"


def connect():
    return sqlite3.connect(DB)


def remember(memory_type, content, source=None, importance=0.5):
    with connect() as db:
        db.execute(
            """
            INSERT INTO memories
            (type, content, source, importance)
            VALUES (?, ?, ?, ?)
            """,
            (memory_type, content, source, importance),
        )
        db.commit()


def _words(text):
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def _recency_score(created_at):
    try:
        created = datetime.fromisoformat(
            created_at.replace(" ", "T")
        ).replace(tzinfo=timezone.utc)

        age_days = max(
            0,
            (datetime.now(timezone.utc) - created).total_seconds() / 86400
        )

        return math.exp(-age_days / 30)

    except Exception:
        return 0.5


def search(query, limit=10):
    query_words = _words(query)

    if not query_words:
        return []

    with connect() as db:
        rows = db.execute(
            """
            SELECT id, type, content, source,
                   importance, created_at
            FROM memories
            """
        ).fetchall()

    scored = []

    for row in rows:
        memory_id, memory_type, content, source, importance, created_at = row

        memory_words = _words(content)

        if not memory_words:
            continue

        overlap = query_words & memory_words

        if not overlap:
            continue

        relevance = len(overlap) / len(query_words)
        recency = _recency_score(created_at)

        type_bonus = TYPE_BONUS.get(memory_type, 0.0)

        score = (
            relevance * MEMORY_WEIGHTS["relevance"]
            + float(importance) * MEMORY_WEIGHTS["importance"]
            + recency * MEMORY_WEIGHTS["recency"]
            + type_bonus
        )

        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [(round(score,4),row) for score, row in scored[:limit]]


def build_context(query, max_chars=3000):
    memories = search(query, limit=20)

    selected = []
    used = 0
    seen = set()

    for score, memory in memories:
        if score < 0.45:
            continue

        memory_id, memory_type, content, source, importance, created_at = memory

        # Avoid repeated or near-identical memory entries.
        normalized = re.sub(r"\d+(?:\.\d+)?", "#", content.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()

        if normalized in seen:
            continue

        seen.add(normalized)
        block = f"[{memory_type} | score={score}] {content}"

        if used + len(block) > max_chars:
            continue

        selected.append(block)
        used += len(block) + 1

    return "\n".join(selected)


def recent(limit=10):
    with connect() as db:
        return db.execute(
            """
            SELECT id, type, content, importance, created_at
            FROM memories
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


if __name__ == "__main__":
    print("Memory manager ready.")


def remember_episode(task, tool, result, verified):
    parts = []

    if tool == "system_info" and isinstance(result, dict):
        cpu = result.get("cpu_cores")
        memory = result.get("memory", "")
        gpu = result.get("gpu", "")

        if cpu:
            parts.append(f"CPU cores: {cpu}")

        # Parse the Mem line by columns.
        for line in memory.splitlines():
            if line.startswith("Mem:"):
                fields = line.split()

                if len(fields) >= 7:
                    parts.append(f"RAM available: {fields[6]}")

            elif line.startswith("Swap:"):
                fields = line.split()

                if len(fields) >= 4:
                    parts.append(
                        f"Swap total/free: {fields[1]}/{fields[3]}"
                    )

        if "Adreno (TM) 650" in gpu:
            parts.append("GPU: Adreno 650")

        parts.append("Backend: Vulkan")

    else:
        parts.append(str(result))

    content = (
        f"Task: {task} | "
        f"Tool: {tool} | "
        f"Facts: {'; '.join(parts)} | "
        f"Verified: {verified}"
    )

    remember(
        "episodic",
        content,
        source="runtime",
        importance=0.6,
    )
