# THIS FILE TIMES THE EXPENSIVE STEPS IN A REQUEST (embedding, Elasticsearch
# search, Ollama generation) SO SLOW REQUESTS ARE DEBUGGABLE.
#
# This is deliberately NOT a full tracing stack (OpenTelemetry, Jaeger) -
# that's built for tracking a request across many services. SentinelCopilot
# is one Python process talking to two local dependencies, so a plain
# step -> milliseconds dict, returned in the API response and logged
# server-side, gives the same practical answer ("where did the time go?")
# with zero extra infrastructure. Revisit if/when Phase 4's Kafka consumer
# makes this an actual multi-process system.

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("sentinelcopilot")


class Trace:
    """Collects named step durations for ONE request. Create a fresh Trace
    per request - it's a local variable, not shared state, so concurrent
    requests never interfere with each other's timings."""

    def __init__(self):
        self.steps: dict[str, float] = {}

    @contextmanager
    def step(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.steps[name] = round((time.perf_counter() - start) * 1000, 1)

    def total_ms(self) -> float:
        return round(sum(self.steps.values()), 1)

    def log(self, endpoint: str, question: str, cached: bool = False):
        if cached:
            logger.info("%s question=%r cache=hit", endpoint, question)
            return
        parts = " ".join(f"{k}={v}ms" for k, v in self.steps.items())
        logger.info(
            "%s question=%r cache=miss %s total=%sms",
            endpoint, question, parts, self.total_ms(),
        )
