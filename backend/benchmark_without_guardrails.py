"""Run only LangGraph stage with guardrails disabled."""

from __future__ import annotations

import asyncio

from benchmark_real import LangGraphNoGuardrails
from benchmark_stage_utils import run_single_stage_benchmark


async def main() -> None:
    run_out = await run_single_stage_benchmark(
        stage_key="without_guardrails",
        runner=LangGraphNoGuardrails(),
        output_name="benchmark_without_guardrails.json",
        run_qasper=True,
        qasper_with_guardrails=False,
    )
    avg = run_out["result"]["stage"].get("avg_latency_s", "N/A")
    print(f"Without-guardrails benchmark complete. avg_latency_s={avg}")
    print(f"Saved: {run_out['output']}")


if __name__ == "__main__":
    asyncio.run(main())
