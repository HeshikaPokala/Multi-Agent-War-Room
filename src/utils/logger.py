from datetime import datetime, timezone
from pathlib import Path


class TraceLogger:
    def __init__(self, trace_path: Path) -> None:
        self.trace_path = trace_path
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_path.write_text("", encoding="utf-8")

    def log(self, actor: str, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} | {actor:<18} | {message}\n")
