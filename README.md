# AI 测试平台

一个基于 **Python + Flask** 的本地测试管理平台，UI 采用苹果 macOS / iOS 设计风格：
毛玻璃面板、圆角卡片、系统字体（SF Pro / PingFang SC）与清晰的蓝灰配色。

它把「功能用例 / AI 自动化 / 接口 / 性能 / 缺陷」几个模块串起来，核心亮点是
**用本地 Codex 智能体 + playwright-cli 驱动真实 Chrome 做一键 UI 自动化**。

---

## 一、网站核心流程

平台左侧导航对应六个模块，各自的核心流程如下：

> 启动顺序：`app.py`（应用工厂）→ 注册蓝图 → `db.create_all()` 建表 → `seed_if_empty()` 写入演示数据。

### 总览（Dashboard）
- 统计卡片：功能用例数、AI 自动化次数、接口用例数、性能压测数、未关闭缺陷数。
- 图表：各阶段执行概览（通过数）+ 缺陷状态分布。
- 快捷操作：一键跳到各模块的「新建/开始」入口。

### 功能用例
进入「功能用例」是一个 **Tab 页**，默认展示第一个 Tab（AI 执行用例上传），两个 Tab 可切换：

**Tab 1：AI 执行用例上传**
- 上传 **Excel（.xlsx/.xls）、Word（.docx/.doc）、XMind（.xmind）** 用例文件。
- 后端用标准库解析文件内容（`services/file_parser.py`），把解析出的文本保存到 `AIExecCase.content`，作为「AI 执行用例」。
- 上传后按**文件名**列表展示，操作列提供：**预览 / 下载 / 删除**。
  - 预览：跳转到独立页面渲染解析后的内容（iframe 弹窗）。
  - 下载：返回原始文件。
  - 删除：清理磁盘文件 + 数据库记录。

**Tab 2：功能用例管理**
- 用例的 新增 / 编辑 / 删除 / 筛选（模块、状态）/ 搜索（名称）。
- 「新建/编辑」为独立表单页（`testcase_form.html`），保存成功后回到该 Tab。

### AI 自动化测试
详见下文「二、AI 自动化功能的实现逻辑」。

### 接口测试
- 维护接口用例（名称、方法、URL、请求头、请求体、预期状态码）。
- 一键发送 HTTP 请求，实时展示响应状态码、耗时、响应体，并校验是否命中预期。

### 性能测试
- 设置目标 URL、请求方法、并发数、总请求量。
- 多线程压测，统计 QPS、平均 / P95 / 最大响应时间、错误率，并落库为一次压测记录。

### 缺陷管理
- 缺陷的提交 / 编辑 / 删除 / 按状态与严重程度筛选。
- 状态流转：新建 → 进行中 → 已修复 / 已关闭 / 已拒绝。

---

## 二、AI 自动化功能的实现逻辑

这一块是平台的核心，整体链路：**上传用例文件 → 前端选择用例/手输步骤 → 后端调用
本地 Codex + playwright-cli 驱动 Chrome → 边执行边看门狗检测 → 生成测试报告**。

### 1. 用例准备：上传并解析
- `routes/testcases.py` 的 `upload_ai_exec()`：
  1. 校验扩展名（仅允许 xlsx/xls/docx/doc/xmind）。
  2. 存到 `uploads/ai_exec/<uuid>.<ext>`。
  3. 调 `services/file_parser.py::parse_file(path, ext)` 解析为文本（标准库 `zipfile + xml/json`，无第三方依赖）。
  4. 写入 `AIExecCase`（含 `name` 文件名、`stored_name`、`file_type`、`ext`、`size`、`content` 解析文本）。
- 解析不了的格式（如传统 .xls 未装 xlrd、.doc 二进制）会在 `content` 里以 `（...）` 开头提示，前端会将其置为「不可选/解析异常」。

### 2. 前端交互（`templates/ai_test.html`）
- 表单字段：`url`（目标 URL）、`steps`（测试步骤）、`headed`（是否有头）、`exec_case_id`（所选 AI 执行用例 ID）。
- 「选择 AI 执行用例」是一个**下拉框**（`select name="exec_case_id"`）：
  - 选中某个用例 → JS 把该用例 `content` 写入 `steps` 输入框，并将其置为 `readonly`（不可编辑），同时显示锁定提示。
  - 选回「不选择」→ 恢复为手动输入的步骤，输入框可编辑。
- 提交后按钮进入加载态（`data-loading="执行中…"`），直到后端返回并跳转详情页。
- 下方「测试报告」表格展示历史运行记录；标题、测试步骤列做了**截断**（`report-title`/`truncate` + 悬停 `title` 全文）。

### 3. 标题规则（`routes/ai_test.py::ui_run`）
- 若表单带了有效的 `exec_case_id` → 标题 = 该上传文件的**文件名**。
- 否则 → 标题 = 手动输入测试步骤的**第一行**（自动跳过空白行）。
- 两者都不满足时兜底为「UI 自动化」；超过 200 字截断（数据库 `title` 为 String(200)）。

### 4. 执行引擎（`services/ui_runner.py`）
`ui_run()` 收到 `url / steps / headed` 后调用 `run_ui(url, steps, headed)`：

**① 生成独立会话与提示词**
```python
session = "ui_" + uuid.uuid4().hex[:8]
prompt = build_prompt(url, steps, headed, session)
```
- `build_prompt()` 拼出一段 Markdown：目标 URL、显示模式、**浏览器会话 `-s=<session>`**、
  执行要求（先 `open` → `snapshot` 读元素 → 按步骤执行、每步标 PASS/FAIL）、
  **停止条件**（浏览器被关闭 / `TargetClosedError` 等必须立即停止）、结尾输出「总体结论：PASS/FAIL」。

**② 浏览器连通性探测**
```python
ok_browser, msg = _probe_browser(probe_timeout)
```
- 先用一个临时会话 `probe_xxx` 打开再关闭 Chrome，验证 playwright 能启动浏览器。
- 失败（超时/无法启动）则**直接停止、不调用 Codex**，返回 status=错误 + 排查建议。

**③ 启动 Codex 智能体**
```python
cmd = [CODEX, "exec", "--ephemeral", "--skip-git-repo-check",
       "--sandbox", CODEX_SANDBOX, "-C", PROJ, "-o", tmp, prompt]
proc = subprocess.Popen(cmd, ...)
```
- `CODEX = /usr/local/bin/codex`，`-o tmp` 让 Codex 把最终报告写入临时 `.md`。
- `CODEX_SANDBOX` 默认 `danger-full-access`（可用环境变量覆盖）。

**④ 执行期看门狗（重点）**
```python
watched_sessions = {session, "default"}
opened = set(); closed_since = {}
while True:
    if proc.poll() is not None: break                    # Codex 自己结束 → 正常收尾
    if time.time() - started > timeout: ...              # 总超时 → 停止
    alive = {s: _browser_alive(s) for s in watched}      # 轮询 playwright-cli list
    for s, ok in alive.items():
        if ok is True: opened.add(s)                     # 会话开着
        elif s in opened and ok is False and s not in closed_since:
            closed_since[s] = now                        # 首次“从开转关”开始计宽限
    if any(now - t > close_grace for s, t in closed_since.items() if s in opened):
        stop_reason = "closed"; proc.kill(); break       # 判定用户关闭了浏览器
    time.sleep(1.2)
```
- `_browser_alive()` 用 `playwright-cli list` 的输出匹配 `- <session>:` 判断会话是否仍在。
- **关键点**：每个会话独立记关闭时间；一旦某会话「曾打开→变关闭」，就开始记宽限
  （`UI_CLOSE_GRACE` 默认 3s），**即使 Codex 随后又把浏览器重开也不取消**，
  从而避免「agent 重开浏览器绕过停止逻辑、导致一直执行中」的问题。
- 判定为关闭 → `proc.kill()`，走 `stop_reason="closed"`。

**⑤ 停止/超时收尾与清理**
- 无论是 `closed`、`timeout`，还是 Codex 正常结束但浏览器仍开着，都会补一次
  `_close_browser_session()`（`playwright-cli -s=<session> close`），避免残留 daemon/Chrome。
- `timeout` 时返回「等待授权」文案（很可能 Codex 卡在打开浏览器/联网的授权弹窗）。
- `closed` 时返回「⏹️ 检测到浏览器窗口已被关闭，执行已停止」。

**⑥ 结果的存取**
- `run_ui` 返回 `{status, output, duration, prompt, cmd}`。
- `ui_run()` 将其写入 `AITestRun`：
  - `kind='ui'`、`root_url=url`、`generated_script=prompt`（交给 Codex 的指令）、
    `output=result.output`（Codex 报告）、`status`、`duration`。

### 5. 报告生成（`services/report.py`）
- `ensure_report(run)` 生成自包含 HTML 报告到 `runs/reports/report_<id>.html`。
- `build_report_html(run)` 从 `run.output`（Codex 的 Markdown）解析出结构化步骤
  `(动作 / 结果 / 说明)`，渲染成表格 + 汇总指标 + 原始报告折叠区。
- 路由 `/ai-test/<id>/report`（内联预览）与 `/ai-test/<id>/download`（下载 HTML）共用它。

### 6. 状态判定
- 报告含「总体结论：PASS/FAIL」→ 通过 / 失败。
- 含 `error/exception/404/401/...` → 错误。
- `FAIL` 且无 `PASS` → 失败；否则 → 未知；无输出 → 错误。

### 7. 相关环境变量（`ui_runner.py` 里读取）
| 变量 | 默认 | 作用 |
| --- | --- | --- |
| `UI_RUN_TIMEOUT` | `180` | 单次 UI 自动化总超时（秒） |
| `UI_CLOSE_GRACE` | `3` | 浏览器被关后的停止宽限（秒） |
| `UI_BROWSER_TIMEOUT` | `15` | 启动前浏览器探测超时（秒） |
| `CODEX_SANDBOX` | `danger-full-access` | `codex exec` 的沙箱模式 |
| `CODEX_BIN` | 自动探测 | `codex` 可执行文件路径（Windows 可指向 `.exe`/`.cmd`） |
| `PLAYWRIGHT_BIN` | 自动探测 | `playwright-cli` 可执行文件路径 |
| `NODE_BIN` / `NODE22_BIN` | macOS 默认 Node 22 | Node 可执行目录（Windows 建议指向 Node 的 bin 目录） |

---

## 三、环境要求

- Python 3.10+
- 一键 UI 自动化依赖本机：`codex` CLI、`playwright-cli`、Node 22、系统 **Google Chrome**。
- **平台自适应（macOS / Windows）**：工具路径优先读环境变量 `CODEX_BIN` / `PLAYWRIGHT_BIN` / `NODE_BIN`，
  其次从 `PATH` 自动解析，macOS 另有默认路径兜底。在 Windows 上安装好上述工具后即可运行
  （`.cmd` 会自动用 `cmd /c` 调用；提示词会按平台生成 `export PATH=...` 或 `$env:Path=...`）。

首次执行时，Codex 打开浏览器或联网会弹出授权提示，**需在授权窗口点「允许」**（方案 B）。
若页面报告超时/授权，可复制结果中给出的命令，在终端手动运行并在授权窗口允许。

---

## 四、快速开始

```bash
cd testing-platform

# 1. 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python run.py
```

浏览器打开：<http://127.0.0.1:5000>

首次启动会自动创建 SQLite 数据库（`data.db`）并写入一批演示数据；如需重置，删除后重启即可。

---

## 五、项目结构

```
testing-platform/
├── app.py              # 应用工厂（建表 + 种子数据 + 注册蓝图）
├── config.py           # 配置（数据库、上传目录、各类超时等）
├── extensions.py       # Flask-SQLAlchemy 扩展
├── models.py           # 数据模型（TestCase/AITestRun/AIExecCase/ApiCase/PerfRun/Bug）
├── seed.py             # 演示数据
├── run.py              # 启动入口（127.0.0.1:5000, debug）
├── requirements.txt
├── routes/             # 各模块蓝图
│   ├── dashboard.py    # 总览
│   ├── testcases.py    # 功能用例 Tab + AI 执行用例上传/预览/下载/删除
│   ├── ai_test.py      # AI 自动化：ui_run、报告预览/下载、删除、ai-exec-cases
│   ├── api_test.py     # 接口测试
│   ├── perf_test.py    # 性能测试
│   └── bugs.py         # 缺陷管理
├── services/           # 业务逻辑
│   ├── ui_runner.py    # UI 自动化执行引擎（Codex + playwright-cli + 看门狗）
│   ├── file_parser.py  # Excel/XMind/Word 解析（标准库）
│   ├── report.py       # 测试报告 HTML 生成
│   ├── ai_engine.py    # 遗留脚本生成/执行（当前 UI 已下线 DeepSeek 生成）
│   └── deepseek.py     # DeepSeek 调用（仅被 ai_engine 的遗留逻辑使用）
├── static/             # css / js
└── templates/          # Jinja2 模板
```

## 六、说明 / 常见问题

- **关掉浏览器后应多久停止？** 正常几秒内。看门狗按「会话曾打开 → 变关闭 → 宽限 3s」停止，
  且重开浏览器不取消计时；最多等 `UI_CLOSE_GRACE` + 一次轮询（默认约 3–5s）。
- **为什么一直「执行中…」？** 多数是看门狗没停 + Codex 重开浏览器，或卡在授权弹窗。
  可调小 `UI_RUN_TIMEOUT` / 检查授权窗口；结果页若显示「等待授权」，可复制它给出的命令到终端运行。
- **DeepSeek 脚本生成已下线**：`services/ai_engine.py` 与 `deepseek.py` 仍保留但不再接入 UI，
  `config.py` 里的 `DEEPSEEK_*` 可忽略。
- **接口 / 性能测试**会真实发起 HTTP 请求，请确保目标可达（或在内网使用）。
- 若端口被占用，修改 `run.py` 的 `port`。
