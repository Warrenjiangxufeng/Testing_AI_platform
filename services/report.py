"""把 AI 测试执行输出渲染成自包含的精美 HTML 测试报告。"""

from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPORTS_DIR = BASE / "runs" / "reports"


def _parse_steps(text: str) -> list[tuple[str, str, str]]:
    """从 Codex 的 Markdown 报告里解析「动作|结果|原因」表格行。"""
    steps: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if cells[0] in ("动作", "步骤", "操作") and cells[1] in ("结果", "预期", "状态"):
            continue
        action = cells[0]
        result = cells[1]
        reason = cells[2] if len(cells) > 2 else ""
        steps.append((action, result, reason))
    return steps


def _result_class(result: str) -> str:
    r = result.upper()
    if "PASS" in r:
        return "pass"
    if "FAIL" in r or "错误" in result or "异常" in result:
        return "fail"
    if "跳过" in result or "SKIP" in r:
        return "skip"
    return "other"


def _esc(value: str) -> str:
    return html.escape(value or "").replace("\n", "<br>")


_REPORT_CSS = """
:root{--blue:#0a84ff;--indigo:#5e5ce6;--teal:#30d158;--red:#ff453a;--amber:#ff9f0a;--ink:#1d1d1f;--muted:#6e6e73;}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Microsoft YaHei",sans-serif;background:#f5f5f7;color:var(--ink);line-height:1.6;padding:28px 16px}
.report{max-width:980px;margin:0 auto;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 18px 45px rgba(0,0,0,.10)}
.hero{background:linear-gradient(135deg,#0a84ff 0%,#5e5ce6 55%,#30d158 130%);padding:34px 38px;color:#fff}
.hero h1{font-size:26px;font-weight:800;letter-spacing:.3px}
.hero .sub{opacity:.9;font-size:14px;margin-top:6px}
.hero .meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;font-size:12px}
.badge{padding:4px 12px;border-radius:999px;background:rgba(255,255,255,.22);backdrop-filter:blur(4px);font-weight:700}
.verdict{display:inline-flex;align-items:center;gap:8px;padding:8px 18px;border-radius:999px;font-weight:800;font-size:16px;background:#fff;color:var(--ink);margin-top:18px;box-shadow:0 4px 14px rgba(0,0,0,.18)}
.dot{width:12px;height:12px;border-radius:50%}
.dot.pass{background:var(--teal)}.dot.fail{background:var(--red)}.dot.stop{background:var(--amber)}.dot.other{background:var(--muted)}
.body{padding:28px 38px 36px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:26px}
.metric{background:#f5f5f7;border-radius:16px;padding:16px 18px;border:1px solid #e8e8ed}
.metric .k{font-size:12px;color:var(--muted);font-weight:600}
.metric .v{font-size:22px;font-weight:800;margin-top:4px}
.metric .v.small{font-size:15px}
.section{margin-top:26px}
.section h2{font-size:18px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.section h2::before{content:"";width:4px;height:16px;border-radius:4px;background:linear-gradient(var(--blue),var(--indigo));display:inline-block}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;background:#f5f5f7;color:var(--muted);font-weight:600;padding:10px 14px;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
td{padding:12px 14px;border-bottom:1px solid #ececf0;vertical-align:top}
td.action{font-weight:600}
.pill-r{display:inline-block;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:800}
.pill-r.pass{background:#d8f5d8;color:#248a3d}
.pill-r.fail{background:#ffe0dd;color:#c0392b}
.pill-r.skip{background:#fff1dc;color:#b06a00}
.pill-r.other{background:#ececf1;color:#6e6e73}
.kv{display:grid;grid-template-columns:120px 1fr;gap:8px 14px;font-size:14px}
.kv dt{color:var(--muted);padding:2px 0}
.kv dd{padding:2px 0;word-break:break-all}
details{margin-top:16px;border:1px solid #e8e8ed;border-radius:12px;padding:0;overflow:hidden}
details summary{padding:12px 16px;font-weight:600;font-size:13px;cursor:pointer;background:#fafafa;user-select:none}
details pre{margin:0;padding:16px;background:#1d1d1f;color:#e8e8f0;font-family:"SF Mono",Menlo,Consolas,monospace;font-size:12px;overflow:auto;white-space:pre-wrap;word-break:break-word}
footer{padding:18px 38px;text-align:center;font-size:12px;color:var(--muted);border-top:1px solid #ececf0}
.empty{padding:24px;text-align:center;color:var(--muted);background:#fafafa;border-radius:12px}
@media print{body{background:#fff;padding:0}.report{box-shadow:none;border-radius:0}}
"""


def build_report_html(run) -> str:
    """根据 AITestRun 生成一份独立 HTML 报告字符串。"""
    title = run.title or "AI 自动化测试报告"
    status = run.status or "未知"
    duration = run.duration or 0.0
    created = run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else ""
    model = run.model or "-"
    url = run.root_url or "-"
    prompt = run.prompt or ""
    output = run.output or ""
    kind = run.kind or "script"

    steps = _parse_steps(output)
    verdict = status
    dot_class = "other"
    if "通过" in status:
        dot_class = "pass"
    elif "失败" in status or "错误" in status:
        dot_class = "fail"
    elif "已停止" in status or "停止" in status or "等待授权" in status:
        dot_class = "stop"

    pass_n = sum(1 for _, r, _ in steps if _result_class(r) == "pass")
    fail_n = sum(1 for _, r, _ in steps if _result_class(r) == "fail")
    total = len(steps)

    rows_html = "".join(
        (
            f"<tr><td class=\"action\">{_esc(action)}</td>"
            f"<td><span class=\"pill-r {cls}\">{_esc(result)}</span></td>"
            f"<td>{_esc(reason) or '—'}</td></tr>"
        )
        for action, result, reason in steps
        for cls in [_result_class(result)]
    ) or f"<tr><td colspan=\"3\" class=\"empty\">未解析到结构化的步骤记录，请查看下方原始报告。</td></tr>"

    verdict_label = {
        "通过": "测试通过",
        "失败": "测试失败",
        "错误": "执行错误",
        "已停止": "已手动停止",
        "等待授权": "等待授权",
    }.get(status, status)

    body = f"""
<div class="hero">
  <h1>{_esc(title)}</h1>
  <div class="sub">AI 自动化测试报告 · {kind.upper()}</div>
  <div class="meta">
    <span class="badge">模型：{_esc(model)}</span>
    <span class="badge">耗时：{duration:.2f}s</span>
    <span class="badge">时间：{_esc(created) or '—'}</span>
  </div>
  <div class="verdict"><span class="dot {dot_class}"></span>{_esc(verdict_label)}</div>
</div>
<div class="body">
  <div class="metrics">
    <div class="metric"><div class="k">总体结论</div><div class="v">{_esc(verdict)}</div></div>
    <div class="metric"><div class="k">执行耗时</div><div class="v">{duration:.2f}s</div></div>
    <div class="metric"><div class="k">执行步骤</div><div class="v">{total}</div></div>
    <div class="metric"><div class="k">通过 / 失败</div><div class="v small">{pass_n} / {fail_n}</div></div>
  </div>

  <div class="section">
    <h2>任务详情</h2>
    <dl class="kv">
      <dt>测试标题</dt><dd>{_esc(title)}</dd>
      <dt>测试对象</dt><dd>{_esc(url)}</dd>
      <dt>需求描述</dt><dd>{_esc(prompt) or '—'}</dd>
      <dt>执行时间</dt><dd>{_esc(created) or '—'}</dd>
    </dl>
  </div>

  <div class="section">
    <h2>执行结果</h2>
    <table>
      <thead><tr><th>动作</th><th>结果</th><th>说明</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <div class="section">
    <details>
      <summary>查看原始报告（Markdown）</summary>
      <pre>{_esc(output) or '（无输出）'}</pre>
    </details>
  </div>
</div>
<footer>由 AI 测试平台生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</footer>
"""
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_esc('测试报告 · ' + title)}</title>"
        f"<style>{_REPORT_CSS}</style></head><body><div class=\"report\">{body}</div></body></html>"
    )


def report_path(run) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"report_{run.id}.html"


def ensure_report(run) -> Path:
    """若报告文件不存在则生成，返回文件路径。"""
    path = report_path(run)
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(build_report_html(run), encoding="utf-8")
    return path
