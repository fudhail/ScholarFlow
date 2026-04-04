"""Aggregate three stage benchmark JSON files into a single markdown comparison."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


BACKEND_DIR = Path(__file__).parent
REPO_ROOT = BACKEND_DIR.parent
DOCS_DIR = REPO_ROOT / "docs"

INPUT_FILES: List[Tuple[str, Path]] = [
    ("Current Version", BACKEND_DIR / "benchmark_current_version.json"),
    ("Without Guardrails", BACKEND_DIR / "benchmark_without_guardrails.json"),
    ("LangGraph Only", BACKEND_DIR / "benchmark_langgraph_only.json"),
]

OUTPUT_MD = DOCS_DIR / "RESULTS_PERFORMANCE_COMPARISON_AUTO.md"


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_num(value: Any, places: int = 4) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{places}f}"
    return "N/A"


def _safe_pct(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1f}%"
    return "N/A"


def _metric(stage: Dict[str, Any], key: str, fallback: str = "N/A") -> Any:
    if not isinstance(stage, dict):
        return fallback
    return stage.get(key, fallback)


def _quality(stage: Dict[str, Any], key: str) -> Any:
    quality = stage.get("quality_metrics", {}) if isinstance(stage, dict) else {}
    return quality.get(key, "N/A")


def _qasper(payload: Dict[str, Any], key: str) -> Any:
    qasper = payload.get("qasper", {}) if isinstance(payload, dict) else {}
    metrics = qasper.get("metrics", {}) if isinstance(qasper, dict) else {}
    return metrics.get(key, "N/A")


def build_markdown(rows: List[Dict[str, Any]]) -> str:
    generated_at = datetime.now().isoformat()

    lines: List[str] = []
    lines.append("# Auto Comparison: 3 Benchmark Modes")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")
    lines.append(
        "| Mode | Label | Avg Latency (s) | P95 (s) | P99 (s) | Success Rate | Errors | Avg Papers | Peak Memory (MB) | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU-4 | Q-Faith | Q-AnsRel | Q-CtxPrec | Q-Evidence | Q-TTFT(s) | Q-Total(s) | Q-FPR |"
    )
    lines.append(
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )

    for row in rows:
        stage = row["stage"]
        mem = row["memory"]
        lines.append(
            "| "
            f"{row['mode']} | "
            f"{_metric(stage, 'label')} | "
            f"{_safe_num(_metric(stage, 'avg_latency_s'))} | "
            f"{_safe_num(_metric(stage, 'p95_latency_s'))} | "
            f"{_safe_num(_metric(stage, 'p99_latency_s'))} | "
            f"{_safe_pct(_metric(stage, 'success_rate_pct'))} | "
            f"{_metric(stage, 'error_count')} | "
            f"{_safe_num(_metric(stage, 'avg_papers_returned'), 1)} | "
            f"{_safe_num(mem.get('peak_mb'), 1)} | "
            f"{_safe_num(_quality(stage, 'rouge_1'))} | "
            f"{_safe_num(_quality(stage, 'rouge_2'))} | "
            f"{_safe_num(_quality(stage, 'rouge_l'))} | "
            f"{_safe_num(_quality(stage, 'bleu_4'))} | "
            f"{_safe_num(_qasper(row['payload'], 'faithfulness'))} | "
            f"{_safe_num(_qasper(row['payload'], 'answer_relevance'))} | "
            f"{_safe_num(_qasper(row['payload'], 'context_precision'))} | "
            f"{_safe_num(_qasper(row['payload'], 'evidence_hit_rate'))} | "
            f"{_safe_num(_qasper(row['payload'], 'ttft_s'))} | "
            f"{_safe_num(_qasper(row['payload'], 'total_latency_s'))} | "
            f"{_safe_num(_qasper(row['payload'], 'fpr'))} |"
        )

    lines.append("")
    lines.append("## Source Files")
    lines.append("")
    for row in rows:
        lines.append(f"- `{row['source']}`")

    return "\n".join(lines) + "\n"


def main() -> None:
    rows: List[Dict[str, Any]] = []
    missing: List[Path] = []

    for mode, path in INPUT_FILES:
        if not path.exists():
            missing.append(path)
            continue

        payload = _load_json(path)
        rows.append(
            {
                "mode": mode,
                "source": path,
                "payload": payload,
                "stage": payload.get("stage", {}),
                "memory": payload.get("memory", {}),
            }
        )

    if missing:
        missing_list = "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(
            "Missing required benchmark file(s):\n"
            f"{missing_list}\n"
            "Run the corresponding benchmark scripts first."
        )

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    content = build_markdown(rows)
    with open(OUTPUT_MD, "w", encoding="utf-8") as handle:
        handle.write(content)

    print(f"Comparison markdown generated: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
