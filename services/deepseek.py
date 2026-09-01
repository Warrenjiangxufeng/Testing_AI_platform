"""DeepSeek（OpenAI 兼容）统一调用客户端。"""

from __future__ import annotations

import requests


def available() -> bool:
    """是否已配置 API Key。"""
    from config import Config

    return bool(Config.DEEPSEEK_API_KEY)


def chat(messages: list, model: str = None) -> str:
    """调用 DeepSeek chat/completions，返回回复文本。失败抛异常。"""
    from config import Config

    model = model or Config.DEEPSEEK_MODEL
    base_url = Config.DEEPSEEK_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2000,
        "stream": False,
    }
    resp = requests.post(
        url, json=payload, headers=headers, timeout=Config.DEEPSEEK_TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]
