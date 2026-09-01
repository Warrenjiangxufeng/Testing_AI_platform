"""HTTP 接口请求执行器，基于 requests。"""

from __future__ import annotations

import json
import time

import requests


def send(method: str, url: str, headers: str, body: str, timeout: int = 15) -> dict:
    """发送一次 HTTP 请求，返回结构化结果。"""
    method = (method or "GET").upper()
    try:
        hdrs = json.loads(headers) if headers.strip() else {}
    except json.JSONDecodeError:
        hdrs = {}
    try:
        payload = json.loads(body) if body.strip() else None
    except json.JSONDecodeError:
        payload = body

    started = time.time()
    try:
        resp = requests.request(
            method, url, headers=hdrs, data=payload, timeout=timeout
        )
        elapsed = (time.time() - started) * 1000
        try:
            text = resp.text
        except Exception:  # noqa: BLE001
            text = "无法解析响应"
        return {
            "ok": True,
            "status_code": resp.status_code,
            "time_ms": round(elapsed, 1),
            "body": text[:4000],
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.time() - started) * 1000
        return {
            "ok": False,
            "status_code": None,
            "time_ms": round(elapsed, 1),
            "body": "",
            "error": str(exc),
        }

