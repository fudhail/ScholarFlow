"""Utilities for running one benchmark stage at a time."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:  # pragma: no cover
    class _PsutilFallback:
        @staticmethod
        def cpu_count():
            import os
            return os.cpu_count() or 1

        @staticmethod
        def virtual_memory():
            class _V:
                total = 0
            return _V()

    psutil = _PsutilFallback()

from benchmark_real import (
    RESEARCH_QUERIES,
    LocalFaissRetriever,
    _chunk_text,
    evaluate_with_ragas,
    evidence_hit_metric,
    generate_answer_with_ttft,
    load_qasper_examples,
    run_memory_test,
    run_stage,
)


SCRIPT_DIR = Path(__file__).parent


def _environment_info() -> Dict[str, Any]:
    return {
        "cpu_count": psutil.cpu_count(),
        "total_memory_gb": psutil.virtual_memory().total / (1024 ** 3),
    }


async def run_qasper_for_mode(
    *,
    with_guardrails: bool,
    max_papers: int = 4,
    max_qas_per_paper: int = 2,
    top_k: int = 6,
) -> Dict[str, Any]:
    """Run QASPER battery and compute RAGAS metrics for one stage mode."""
    from app.services.guardrails_service import GuardrailContext, check_intent_guardrails

    examples = load_qasper_examples(max_papers=max_papers, max_qas_per_paper=max_qas_per_paper)
    retriever = LocalFaissRetriever()

    rows: List[Dict[str, Any]] = []
    block_events: List[Dict[str, Any]] = []

    for ex in examples:
        chunks = _chunk_text(ex["paper_text"], chunk_size=520, overlap=90)
        retriever.build(chunks)
        contexts = retriever.retrieve(ex["question"], top_k=top_k)

        gate_elapsed = 0.0
        early_exit = False

        if with_guardrails:
            g0 = time.perf_counter()
            decision = check_intent_guardrails(GuardrailContext(query=ex["question"], intent_raw="SEARCH"))
            gate_elapsed = time.perf_counter() - g0
            if decision.status == "BLOCK":
                early_exit = True
                block_events.append({
                    "query": ex["question"],
                    "reason": decision.reason,
                    "decision_source": decision.decision_source,
                    "gate_latency_s": round(gate_elapsed, 4),
                    "is_valid_academic": True,
                })

        if early_exit:
            answer = "[BLOCKED_BY_GUARDRAIL]"
            ttft_s = 0.0
            total_s = round(gate_elapsed, 4)
        else:
            answer, ttft_s, total_s_raw = await generate_answer_with_ttft(ex["question"], contexts)
            ttft_s = round(ttft_s + gate_elapsed, 4)
            total_s = round(total_s_raw + gate_elapsed, 4)

        rows.append({
            "question": ex["question"],
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ex.get("answer", ""),
            "evidence_hit": evidence_hit_metric(contexts, ex.get("gold_evidence", [])),
            "ttft_s": ttft_s,
            "total_latency_s": total_s,
            "early_exit": early_exit,
        })

    ragas_scores = evaluate_with_ragas(rows)

    def _avg(rows_local: List[Dict[str, Any]], key: str) -> float:
        if not rows_local:
            return 0.0
        return round(statistics.mean(float(r.get(key, 0.0)) for r in rows_local), 4)

    valid_academic = len(examples)
    fp_blocks = len(block_events)
    fpr = round(fp_blocks / max(valid_academic, 1), 4)

    return {
        "dataset": "allenai/qasper",
        "examples_used": len(examples),
        "with_guardrails": with_guardrails,
        "metrics": {
            "faithfulness": ragas_scores.get("faithfulness", 0.0),
            "answer_relevance": ragas_scores.get("answer_relevancy", 0.0),
            "context_precision": ragas_scores.get("context_precision", 0.0),
            "evidence_hit_rate": _avg(rows, "evidence_hit"),
            "ttft_s": _avg(rows, "ttft_s"),
            "total_latency_s": _avg(rows, "total_latency_s"),
            "early_exit_rate": _avg(rows, "early_exit"),
            "fpr": fpr,
            "false_positive_blocks": fp_blocks,
            "valid_academic_questions": valid_academic,
        },
        "block_events": block_events,
    }


async def run_single_stage_benchmark(
    *,
    stage_key: str,
    runner: Any,
    output_name: str,
    queries: Optional[List[str]] = None,
    run_qasper: bool = True,
    qasper_with_guardrails: bool = False,
) -> Dict[str, Any]:
    """Run one benchmark stage and persist JSON output in backend/."""
    active_queries = queries or RESEARCH_QUERIES

    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "environment": _environment_info(),
        "stage_key": stage_key,
        "queries": active_queries,
    }

    results["stage"] = await run_stage(runner, active_queries)
    results["memory"] = await run_memory_test(runner)
    if run_qasper:
        results["qasper"] = await run_qasper_for_mode(with_guardrails=qasper_with_guardrails)

    out_path = SCRIPT_DIR / output_name
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)

    return {
        "output": str(out_path),
        "result": results,
    }
