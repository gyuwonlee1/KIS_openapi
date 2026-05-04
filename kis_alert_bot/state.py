from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kis_alert_bot.models import Alert, ConditionResult


@dataclass
class AlertStateStore:
    path: Path
    data: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "AlertStateStore":
        state_path = Path(path)
        if not state_path.exists():
            return cls(path=state_path)
        with state_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            data = {}
        return cls(path=state_path, data=data)

    def update_result(self, result: ConditionResult) -> Alert | None:
        key = result.state_key
        previous = self.data.get(key, {})
        if bool(previous.get("done", False)):
            return None

        was_matched = bool(previous.get("matched", False))
        last_alerted_at = _parse_datetime(previous.get("last_alerted_at"))
        should_alert = False
        is_reentry = False

        if result.matched:
            if not was_matched:
                should_alert = True
                is_reentry = last_alerted_at is not None
            elif _cooldown_elapsed(result, last_alerted_at):
                should_alert = True
                is_reentry = True

        entry = {
            "matched": result.matched,
            "last_evaluated_at": result.evaluated_at.astimezone(timezone.utc).isoformat(),
            "current_price": result.current_price,
            "threshold": result.threshold,
        }
        if should_alert:
            entry["last_alerted_at"] = result.evaluated_at.astimezone(timezone.utc).isoformat()
            if result.condition.delete_after_alert:
                entry["done"] = True
                entry["completed_at"] = result.evaluated_at.astimezone(timezone.utc).isoformat()
        elif previous.get("last_alerted_at"):
            entry["last_alerted_at"] = previous["last_alerted_at"]
        if previous.get("done"):
            entry["done"] = previous["done"]
        if previous.get("completed_at"):
            entry["completed_at"] = previous["completed_at"]

        self.data[key] = entry
        if should_alert:
            return Alert(result=result, is_reentry=is_reentry)
        return None

    def is_done(self, key: str) -> bool:
        return bool(self.data.get(key, {}).get("done", False))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")


def _cooldown_elapsed(result: ConditionResult, last_alerted_at: datetime | None) -> bool:
    cooldown_minutes = result.condition.cooldown_minutes
    if cooldown_minutes is None or last_alerted_at is None:
        return False
    elapsed = result.evaluated_at.astimezone(timezone.utc) - last_alerted_at
    return elapsed.total_seconds() >= cooldown_minutes * 60


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
