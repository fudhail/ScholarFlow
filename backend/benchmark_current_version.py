"""Run only current production-like stage: LangGraph + Guardrails."""

from __future__ import annotations

import asyncio

from benchmark_real import LangGraphWithGuardrails
from benchmark_stage_utils import run_single_stage_benchmark


async def main() -> None:
    run_out = await run_single_stage_benchmark(
        stage_key="current_version",
        runner=LangGraphWithGuardrails(),
        output_name="benchmark_current_version.json",
        run_qasper=True,
        qasper_with_guardrails=True,
    )
    avg = run_out["result"]["stage"].get("avg_latency_s", "N/A")
    print(f"Current version benchmark complete. avg_latency_s={avg}")
    print(f"Saved: {run_out['output']}")


if __name__ == "__main__":
    asyncio.run(main())
