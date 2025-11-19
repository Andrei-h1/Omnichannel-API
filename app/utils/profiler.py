import time
import logging

logger = logging.getLogger("profiler")

def now():
    return time.time()

def step(start_ts: float, label: str) -> float:
    elapsed = (time.time() - start_ts) * 1000
    logger.info(f"[IMAGE PROFILER] {label}: {elapsed:.2f} ms")
    return time.time()
