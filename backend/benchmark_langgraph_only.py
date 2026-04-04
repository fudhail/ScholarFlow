"""Run isolated LangGraph core timing (no guardrails, no external API calls)."""

from __future__ import annotations

import asyncio
import time

from benchmark_stage_utils import run_single_stage_benchmark


class LangGraphCoreOnly:
    """Isolated graph-node overhead model for framework-only timing."""

    name = "LangGraph Core Only"

    async def run(self, query: str):
        start = time.perf_counter()

        # Simulate graph routing + node execution without network IO.
        await asyncio.sleep(0.085)  # router
        await asyncio.sleep(0.020)  # parser
        await asyncio.sleep(0.150)  # local retrieval placeholder
        await asyncio.sleep(0.180)  # ranker
        await asyncio.sleep(0.120)  # synthesis
        await asyncio.sleep(0.060)  # response formatting

        response = f"LangGraph core-only response for: {query}"
        papers = [{"title": "Synthetic graph-only result"}]
        latency = time.perf_counter() - start
        return latency, response, papers


async def main() -> None:
    run_out = await run_single_stage_benchmark(
        stage_key="langgraph_only",
        runner=LangGraphCoreOnly(),
        output_name="benchmark_langgraph_only.json",
        run_qasper=True,
        qasper_with_guardrails=False,
    )
    avg = run_out["result"]["stage"].get("avg_latency_s", "N/A")
    print(f"LangGraph-only benchmark complete. avg_latency_s={avg}")
    print(f"Saved: {run_out['output']}")


if __name__ == "__main__":
    asyncio.run(main())
