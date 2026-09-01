"""轻量级性能压测器：多线程并发请求 + 汇总。"""

from __future__ import annotations

import json
import threading
import time

import requests


class _LoadWorker(threading.Thread):
    def __init__(self, spec, results, lock, index):
        super().__init__()
        self.spec = spec
        self.results = results
        self.lock = lock
        self.index = index

    def run(self):
        method = self.spec.get("method", "GET").upper()
        url = self.spec.get("url", "")
        hdrs = self.spec.get("headers", {})
        body = self.spec.get("body", None)
        timeout = min(self.spec.get("timeout", 10), 10)
        try:
            started = time.time()
            resp = requests.request(
                method, url, headers=hdrs, data=body, timeout=timeout
            )
            elapsed = time.time() - started
            ok = 200 <= resp.status_code < 400
        except Exception:  # noqa: BLE001
            elapsed = timeout
            ok = False
        with self.lock:
            self.results.append((ok, elapsed * 1000))


def run(url: str, method: str, concurrent: int, total: int, headers: str = "", body: str = "") -> dict:
    """执行简单并发压测，返回汇总指标。"""
    concurrent = max(1, min(int(concurrent or 1), 50))
    total = max(1, min(int(total or 1), 2000))
    try:
        hdrs = json.loads(headers) if headers.strip() else {}
    except json.JSONDecodeError:
        hdrs = {}
    try:
        payload = json.loads(body) if body.strip() else None
    except json.JSONDecodeError:
        payload = body

    results: list[tuple[bool, float]] = []
    lock = threading.Lock()
    spec = {"method": method, "url": url, "headers": hdrs, "body": payload}

    started = time.time()
    sent = 0
    while sent < total:
        batch = min(concurrent, total - sent)
        workers = [
            _LoadWorker(spec, results, lock, i)
            for i in range(batch)
        ]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        sent += batch
    elapsed = time.time() - started

    if elapsed <= 0:
        elapsed = 0.001
    success = sum(1 for ok, _ in results if ok)
    failed = len(results) - success
    latencies = sorted(ms for _, ms in results)
    avg_ms = sum(latencies) / len(latencies) if latencies else 0
    p95_ms = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0
    max_ms = latencies[-1] if latencies else 0

    return {
        "success": success,
        "failed": failed,
        "qps": round(len(results) / elapsed, 2),
        "avg_ms": round(avg_ms, 1),
        "p95_ms": round(p95_ms, 1),
        "max_ms": round(max_ms, 1),
        "error_rate": round(failed / len(results) * 100 if results else 0, 2),
        "elapsed": round(elapsed, 2),
    }

