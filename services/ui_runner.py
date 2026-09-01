"""调用本地 Codex 智能体，用 playwright-cli 技能执行 UI 自动化测试。

设计：Flask 后端在用户点「一键执行」时，用 `codex exec` 非交互启动一个
Codex 智能体，把测试步骤交给它；Codex 加载 playwright-cli 技能真实驱动
Chrome，最后把 `-o` 写出的最终报告回传给页面。默认不绕过审批（方案 B），
打开浏览器/联网需要用户批准。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]


def _resolve_tool(env_key: str, name: str, mac_default: str) -> str:
    """解析工具可执行文件：优先环境变量，其次 PATH，再次 macOS 默认路径。"""
    value = os.environ.get(env_key)
    if value:
        return value
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "darwin":
        return mac_default
    return name


def _node_bin() -> str:
    """返回 Node 可执行目录：优先环境变量 NODE_BIN / NODE22_BIN，macOS 用默认本地 Node 22。"""
    value = os.environ.get("NODE_BIN") or os.environ.get("NODE22_BIN")
    if value:
        return value
    if sys.platform == "darwin":
        return os.path.expanduser("~/.local/node-v22.23.2-darwin-x64/bin")
    return ""


def _cmd(bin_path: str, *args: str) -> list[str]:
    """返回可执行命令列表；Windows 上若目标为 .cmd/.bat，用 cmd /c 包装。"""
    if os.name == "nt" and str(bin_path).lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", bin_path, *args]
    return [bin_path, *args]


def _chrome_hint() -> str:
    if os.name == "nt":
        return "1. Google Chrome 已安装（如 C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe）"
    return "1. Google Chrome 已安装（/Applications/Google Chrome.app）"


CODEX = _resolve_tool("CODEX_BIN", "codex", "/usr/local/bin/codex")
PLAYWRIGHT = _resolve_tool("PLAYWRIGHT_BIN", "playwright-cli", "/usr/local/bin/playwright-cli")


def _env():
    env = os.environ.copy()
    node_bin = _node_bin()
    if node_bin:
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    env.setdefault("NO_UPDATE_NOTIFIER", "1")
    return env


def build_prompt(url: str, steps: str, headed: bool, session: str) -> str:
    mode = "有头 headed（可见浏览器窗口）" if headed else "无头 headless（不显示窗口）"
    head_flag = " --headed" if headed else ""
    node_bin = _node_bin()
    if os.name == "nt":
        path_hint = (
            f'$env:Path = "{node_bin};$env:Path"' if node_bin
            else "确保 playwright-cli 已在当前系统的 PATH 中"
        )
    else:
        path_hint = (
            f'export PATH="{node_bin}:$PATH"' if node_bin
            else "确保 playwright-cli 已在当前系统的 PATH 中"
        )
    return f"""{steps}

请用本地的 playwright-cli 技能（web-test-runner / playwright-cli）对真实网页执行一次 UI 自动化测试。

目标地址：{url}
显示模式：{mode}
浏览器会话：-s={session}（后续所有 playwright-cli 命令都必须带上 -s={session}）

要求：
1. 如需运行 playwright-cli，先执行：{path_hint}
2. 用 -s={session} open --browser chrome{head_flag} 打开浏览器；open 之后先 snapshot 读取页面元素，再按用户给出的步骤执行。
3. 每执行完一步，标记该步 PASS 或 FAIL；若元素找不到、步骤无法完成，记录 FAIL 并说明原因。
4. **停止条件**：若浏览器窗口被手动关闭，或命令报错提示浏览器未打开 / 连接已断开（如 "browser is not open" / "TargetClosedError" / "Browser has been closed"），必须**立即停止执行**，不要再执行任何后续步骤，也不要在已断开的浏览器上反复重试。
5. 结束时用 -s={session} close 关闭浏览器。
6. 只输出一份 Markdown 报告：若因浏览器被关闭而停止，第一行写明「已停止：浏览器已被关闭」；否则逐条列出(动作 / 结果 / 原因)。最后一行恒定输出「总体结论：PASS」或「总体结论：FAIL」。不要在浏览器被关闭后继续输出新的步骤结果。
"""


def _probe_browser(timeout: float = 15.0) -> tuple:
    """在调用 Codex 前，尝试启动一次浏览器做连通性探测。

    返回 (是否成功, 说明)。超过 timeout（默认 15 秒）或启动失败则返回 False，
    由调用方停止执行并提示，避免白等一次完整的 Codex 运行。
    """
    env = _env()
    session = f"probe_{uuid.uuid4().hex[:8]}"
    cmd = _cmd(PLAYWRIGHT, f"-s={session}", "open", "--browser", "chrome")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        cost = round(time.time() - t0, 1)
        if proc.returncode == 0:
            subprocess.run(
                _cmd(PLAYWRIGHT, f"-s={session}", "close"),
                capture_output=True,
                env=env,
                timeout=8,
            )
            return True, f"浏览器启动正常（{cost}s）"
        msg = (proc.stderr or proc.stdout or "").strip()[:300]
        return False, f"浏览器启动失败：{msg}"
    except subprocess.TimeoutExpired:
        subprocess.run(_cmd(PLAYWRIGHT, "kill-all"), capture_output=True, env=env, timeout=8)
        return False, f"浏览器启动超过 {int(timeout)} 秒仍未成功，已停止执行。"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _browser_alive(session: str, env: dict) -> bool | None:
    """检测某个浏览器会话是否仍开着。

    返回 True=会话在；False=会话已关闭/未开；None=无法判断（失败时不触发停止）。
    """
    try:
        rs = subprocess.run(
            _cmd(PLAYWRIGHT, "list"),
            capture_output=True, text=True, timeout=6, env=env,
        )
        out = rs.stdout or ""
        return re.search(rf"-\s*{re.escape(session)}\s*:", out) is not None
    except Exception:  # noqa: BLE001
        return None


def _close_browser_session(env: dict, session: str) -> None:
    """尝试关闭指定浏览器会话，忽略错误（用于清理残留 daemon / Chrome 窗口）。"""
    try:
        subprocess.run(
            _cmd(PLAYWRIGHT, f"-s={session}", "close"),
            capture_output=True,
            timeout=8,
            env=env,
        )
    except Exception:  # noqa: BLE001
        pass


def run_ui(url: str, steps: str, headed: bool, timeout: int | None = None) -> dict:
    if timeout is None:
        timeout = int(os.environ.get("UI_RUN_TIMEOUT", "180"))

    session = "ui_" + uuid.uuid4().hex[:8]
    prompt = build_prompt(url, steps, headed, session)
    probe_timeout = float(os.environ.get("UI_BROWSER_TIMEOUT", "15"))

    # 浏览器启动探测：超过 15 秒或失败则直接停止，不再调用 Codex
    ok_browser, probe_msg = _probe_browser(probe_timeout)
    if not ok_browser:
        return {
            "status": "错误",
            "output": (
                "⏱️ 浏览器启动检测未通过，已停止执行，未调用 Codex。\n\n"
                f"原因：{probe_msg}\n\n"
                f"请确认：\n{_chrome_hint()}\n"
                "2. playwright-cli 可用（已在 PATH，或用环境变量指定）\n"
                "3. 若本机首次运行，可在「显示浏览器窗口」勾选有头模式后重试。"
            ),
            "duration": 0,
            "prompt": prompt,
            "cmd": "",
        }

    tmp = tempfile.mktemp(prefix="codex_out_", suffix=".md")
    sandbox = os.environ.get("CODEX_SANDBOX", "danger-full-access")
    cmd = _cmd(
        CODEX, "exec", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", sandbox,
        "-C", str(PROJ), "-o", tmp, prompt,
    )
    cmd_str = " ".join(cmd)
    started = time.time()

    out_path = tempfile.mktemp(prefix="codex_stdout_", suffix=".txt")
    err_path = tempfile.mktemp(prefix="codex_stderr_", suffix=".txt")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=open(out_path, "w"),
            stderr=open(err_path, "w"),
            stdin=subprocess.DEVNULL,
            text=True,
            env=_env(),
        )
    except FileNotFoundError:
        return {
            "status": "错误",
            "output": "未找到 codex 命令，请确认本机已安装 Codex CLI，或用环境变量 CODEX_BIN 指定可执行路径。",
            "duration": 0,
            "prompt": prompt,
            "cmd": cmd_str,
        }

    # 等待期间轮询：既处理总超时，也检测“浏览器被关闭 -> 立即停止执行”。
    # 同时监控本次会话与 default（agent 可能沿用技能里的默认会话）。
    watched_sessions = {session, "default"}
    opened: set[str] = set()
    # 每个会话独立的“首次检测到关闭”时间：一旦某会话曾打开而后变关闭，
    # 就开始记录宽限时间；即使 agent 随后又重新打开浏览器也**不取消**，
    # 避免“重开浏览器”把停止逻辑绕过去。
    closed_since: dict[str, float] = {}
    stop_reason: str | None = None  # None | "timeout" | "closed"
    close_grace = float(os.environ.get("UI_CLOSE_GRACE", "3"))
    while True:
        if proc.poll() is not None:
            break
        if time.time() - started > timeout:
            stop_reason = "timeout"
            proc.kill()
            break
        alive_map = {s: _browser_alive(s, _env()) for s in watched_sessions}
        now = time.time()
        for s, alive in alive_map.items():
            if alive is True:
                opened.add(s)
            elif s in opened and alive is False and s not in closed_since:
                closed_since[s] = now  # 首次发现该会话“从开转关”，开始计宽限
        # 任一曾打开的会话，已在关闭状态持续超过宽限 -> 判定用户关闭了浏览器。
        if any(now - t > close_grace for s, t in closed_since.items() if s in opened):
            stop_reason = "closed"
            proc.kill()
            break
        time.sleep(1.2)

    proc.wait()
    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        out = f.read()
    with open(err_path, "r", encoding="utf-8", errors="replace") as f:
        err = f.read()
    for path in (out_path, err_path):
        if os.path.exists(path):
            os.unlink(path)

    duration = round(time.time() - started, 1)

    # 收尾：若浏览器会话仍开着（例如强制停止或 Agent 未正常关闭浏览器），补一个 close
    if stop_reason in ("closed", "timeout") or _browser_alive(session, _env()):
        _close_browser_session(_env(), session)

    if stop_reason == "closed":
        report = (
            "⏹️ 检测到浏览器窗口已被关闭，执行已停止。\n\n"
            "若需继续，请重新打开浏览器后再次执行。\n\n"
            "```bash\n" + cmd_str + "\n```\n"
        )
        return {
            "status": "已停止",
            "output": report,
            "duration": duration,
            "prompt": prompt,
            "cmd": cmd_str,
        }
    if stop_reason == "timeout":
        report = (
            "⏳ 执行超时。Codex 很可能正在等待授权（打开浏览器或联网时需要你批准）。\n\n"
            "可打开终端，手动复制下面这条命令运行，在授权弹窗里点「允许」后即可完成：\n\n"
            "```bash\n" + cmd_str + "\n```\n"
        )
        return {
            "status": "等待授权",
            "output": report,
            "duration": duration,
            "prompt": prompt,
            "cmd": cmd_str,
        }

    report = ""
    if os.path.exists(tmp):
        with open(tmp, "r", encoding="utf-8", errors="replace") as f:
            report = f.read().strip()
    if not report:
        report = ((out or "") + ("\n" + (err or "") if err else "")).strip()

    verdict = re.search(r"总体结论[:：]\s*(PASS|FAIL)", report)
    if verdict:
        status = "通过" if verdict.group(1).upper() == "PASS" else "失败"
    elif re.search(
        r"error:|exception|failed to|not permitted|operation not permitted|"
        r"app-server|no such|command not found|unauthorized|401|403|404|timeout", report,
        re.I,
    ):
        status = "错误"
    elif "FAIL" in report.upper() and "PASS" not in report.upper():
        status = "失败"
    else:
        status = "未知"
    if status == "错误":
        report = (report or "").strip() + (
            "\n\n---\n该结果可能是环境或授权问题。可复制下面命令在终端手动运行，以便在授权窗口点「允许」：\n"
            "```bash\n" + cmd_str + "\n```\n"
        )
    if not report:
        status = "错误"
        report = "Codex 未返回有效结果，请检查是否已登录/授权 Codex CLI。\n\n命令：\n```bash\n" + cmd_str + "\n```"

    return {
        "status": status,
        "output": report,
        "duration": duration,
        "prompt": prompt,
        "cmd": cmd_str,
    }
