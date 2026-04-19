from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class EvalReport(BaseModel):
    task: str
    dataset_path: str
    sample_count: int
    metrics: dict[str, Any]
    samples: list[dict[str, Any]]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def stdout_summary(self) -> str:
        metric_chunks = ", ".join(f"{key}={value}" for key, value in self.metrics.items())
        return (
            f"task={self.task} samples={self.sample_count} "
            f"dataset={self.dataset_path} {metric_chunks}"
        )
