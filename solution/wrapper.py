"""YOUR mitigation + observability layer. The simulator calls mitigate() around the
opaque agent (a REAL LLM) for every request. This is the ONLY place observability can
live -- the agent is silent. Legal moves: retry / cache / route / guardrail / sanitize
/ fallback / session-reset / PROMPT ROUTING, plus your own logging/tracing/metrics.
Illegal: hardcoding answers, importing the agent internals, reading instructor files,
network exfiltration.

  call_next(question, config) -> result   # the only way to reach the black box
  context = {"session_id","turn_index","qid","cache": <shared dict>, "cache_lock": <Lock>}
  result  = {"answer","status","steps","trace","meta":{latency_ms,usage,...}}

PROMPT ROUTING: you can override the agent's system prompt PER REQUEST by setting it in
the config you pass to call_next, e.g.:
    conf = dict(config); conf["system_prompt"] = my_better_prompt
    result = call_next(question, conf)
(Or just edit solution/prompt.txt for a single static prompt used on every request.)
"""
from __future__ import annotations
import time
from telemetry.logger import logger
from telemetry.cost import cost_from_usage
from telemetry.redact import redact_value

def mitigate(call_next, question, config, context):
    start = time.perf_counter()
    
    max_retries = config.get("retry", {}).get("max_attempts", 3)
    result = None
    
    for attempt in range(max_retries):
        try:
            result = call_next(question, config)
            if result.get("status") != "error":
                break
        except Exception as e:
            logger.log_event("agent_exception", {"attempt": attempt, "error": str(e)})
            if attempt == max_retries - 1:
                result = {"status": "error", "answer": "System unavailable.", "meta": {}, "trace": []}
                
    if not result:
        result = {"status": "error", "answer": "Unknown error", "meta": {}, "trace": []}

    latency_ms = int((time.perf_counter() - start) * 1000)
    meta = result.get("meta", {})
    usage = meta.get("usage", {})
    cost = cost_from_usage(config.get("model", ""), usage)
    
    if "answer" in result and isinstance(result["answer"], str):
        result["answer"] = redact_value(result["answer"])

    log_data = {
        "session_id": context.get("session_id"),
        "qid": context.get("qid"),
        "latency_ms": latency_ms,
        "cost_usd": cost,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "status": result.get("status"),
        "answer_preview": result.get("answer", "")[:100],
        "tool_calls": len(result.get("trace", [])),
    }
    logger.log_event("agent_request_completed", log_data)

    return result
