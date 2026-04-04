# Auto Comparison: 3 Benchmark Modes

Generated: 2026-04-03T09:38:06.920250

## Summary Table

| Mode | Label | Avg Latency (s) | P95 (s) | P99 (s) | Success Rate | Errors | Avg Papers | Peak Memory (MB) | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU-4 | Q-Faith | Q-AnsRel | Q-CtxPrec | Q-Evidence | Q-TTFT(s) | Q-Total(s) | Q-FPR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Current Version | LangGraph + Guardrails | 3.0937 | 3.0100 | 3.0100 | 100.0% | 0 | 5.0 | 38.4 | 0.0693 | 0.0058 | 0.0522 | 0.0000 | 0.8025 | 0.8443 | 0.6875 | 0.6875 | 1.8941 | 6.5299 | 0.0000 |
| Without Guardrails | LangGraph (No Guardrails) | 2.7550 | 3.0036 | 3.0036 | 100.0% | 0 | 5.0 | 38.6 | 0.0693 | 0.0058 | 0.0522 | 0.0000 | 0.8686 | 0.6723 | 0.6875 | 0.6875 | 0.9452 | 6.3720 | 0.0000 |
| LangGraph Only | LangGraph Core Only | 0.6556 | 0.6584 | 0.6584 | 100.0% | 0 | 1.0 | 25.3 | 0.0852 | 0.0274 | 0.0742 | 0.0000 | 0.8307 | 0.7943 | 0.6875 | 0.6875 | 0.8407 | 4.3550 | 0.0000 |

## Source Files

- `C:\Users\fudha\Desktop\scholarflow\backend\benchmark_current_version.json`
- `C:\Users\fudha\Desktop\scholarflow\backend\benchmark_without_guardrails.json`
- `C:\Users\fudha\Desktop\scholarflow\backend\benchmark_langgraph_only.json`
