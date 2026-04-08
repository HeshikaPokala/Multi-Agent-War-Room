import csv
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Dict, List


@lru_cache(maxsize=16)
def load_feedback(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize_sentiment(rows: List[Dict[str, str]]) -> Dict[str, object]:
    sentiment_counts = Counter(r["sentiment"] for r in rows)
    tag_counts = Counter()
    for row in rows:
        for tag in row["tags"].split(";"):
            tag_counts[tag.strip()] += 1
    top_issues = [tag for tag, _ in tag_counts.most_common(6)]
    return {
        "sentiment_counts": dict(sentiment_counts),
        "top_issue_tags": top_issues,
        "negative_ratio": round(sentiment_counts.get("negative", 0) / max(len(rows), 1), 3),
    }
