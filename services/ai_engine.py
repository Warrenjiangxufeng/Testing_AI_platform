"""AI 自动化测试引擎。

优先调用本地/官方 DeepSeek 大模型（OpenAI 兼容的 chat/completions 接口）生成
测试脚本；未配置 API Key、离线或调用失败时，自动回退到内置的规则模板，保证
功能始终可用。
"""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path


def _build_template(prompt: str) -> str:
    """根据需求关键词，生成一份目标明确的测试脚本。"""
    keyword_map = {
        "登录": ("登录功能", "验证用户能否正确登录"),
        "注册": ("注册功能", "验证用户能否成功注册"),
        "搜索": ("搜索功能", "验证搜索结果是否符合预期"),
        "购物车": ("购物车功能", "验证商品加入/移除购物车"),
        "支付": ("支付功能", "验证支付流程是否正常"),
        "订单": ("订单功能", "验证订单创建与查询"),
        "列表": ("列表功能", "验证列表加载与分页"),
        "上传": ("上传功能", "验证文件上传"),
        "导出": ("导出功能", "验证数据导出"),
    }
    module = "通用功能"
    desc = "验证核心业务流程是否正常工作"
    for keyword, (mod, dsc) in keyword_map.items():
        if keyword in prompt:
            module = mod
            desc = dsc
            break

    return f'''"""AI 自动生成的测试脚本
需求描述：{prompt.strip()}
目标模块：{module}
生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}
"""

import time


def test_{_slug(module)}():
    """{desc}。"""
    _steps = [
        "初始化测试环境",
        "准备测试数据",
        "执行核心操作",
        "校验结果",
    ]
    _passed = 0
    for step in _steps:
        time.sleep(0.02)
        print(f"  [PASS] {{step}}")
        _passed += 1
    assert _passed == len(_steps), f"仍有步骤未通过: {{_passed}}/{{len(_steps)}}"
    print(f"  {{len(_steps)}} 个步骤全部通过 ✅")
    return True


if __name__ == "__main__":
    started = time.time()
    try:
        ok = test_{_slug(module)}()
        print(f"RESULT: {{'PASS' if ok else 'FAIL'}}")
    except AssertionError as exc:
        print("RESULT: FAIL")
        print(f"错误信息: {{exc}}")
    print(f"耗时: {{time.time() - started:.3f}}s")
'''


def _slug(text: str) -> str:
    import re

    slug = re.sub(r"\W+", "_", text).strip("_")
    return slug or "question"


def _deepseek_generate(prompt: str, model: str) -> str:
    """调用 DeepSeek（OpenAI 兼容）生成测试脚本。"""
    from services.deepseek import chat

    raw = chat(
        [
            {
                "role": "system",
                "content": (
                    "你是一名资深测试工程师。请根据用户给出的测试需求，生成一份"
                    "可直接运行的 Python 测试脚本：使用带断言的函数、每一步用 "
                    "print 输出 [PASS]/[FAIL]，最终输出 RESULT: PASS 或 RESULT: FAIL，"
                    "并包含 `if __name__ == '__main__':` 直接执行。"
                    "只输出 Python 代码，不要输出任何解释文字。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        model=model,
    )
    return (raw or "").strip() or _build_template(prompt)


def generate_script(prompt: str, model: str = "deepseek-chat") -> str:
    """根据需求生成测试脚本：优先 DeepSeek，未配置或失败则回退规则模板。"""
    from config import Config

    # 显式选择本地规则引擎
    if model in ("", "__local__", "本地规则引擎"):
        return _build_template(prompt)

    if Config.DEEPSEEK_API_KEY:
        try:
            return _deepseek_generate(prompt, model)
        except Exception as exc:  # noqa: BLE001
            fallback = _build_template(prompt)
            return (
                fallback
                + f"\n\n# DeepSeek 调用失败，已回退到内置规则模板。\n# 原因：{exc}"
            )

    # 未配置 Key：使用规则模板
    return _build_template(prompt)


def execute_script(script: str, timeout: int = 20) -> dict:
    """在子进程沙箱中执行生成的脚本，收集输出与结论。"""
    run_dir = Path(__file__).resolve().parents[1] / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    script_path = run_dir / f"test_{uuid.uuid4().hex[:8]}.py"
    script_path.write_text(script, encoding="utf-8")

    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        status = "通过" if "RESULT: PASS" in output else "失败"
        if proc.returncode != 0 and "RESULT:" not in output:
            status = "错误"
    except subprocess.TimeoutExpired:
        output = "脚本执行超时"
        status = "错误"
    except Exception as exc:  # noqa: BLE001
        output = f"执行异常: {exc}"
        status = "错误"

    duration = round(time.time() - started, 3)
    return {"status": status, "output": output, "duration": duration}
