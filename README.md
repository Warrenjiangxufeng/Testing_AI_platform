# AI 测试平台

一个基于 **Python + Flask** 的测试管理平台，UI 采用苹果 macOS/iOS 设计风格：
毛玻璃顶部导航、圆角卡片、系统字体（SF Pro / PingFang SC）与清晰的蓝灰配色。

## 功能菜单

- **总览**：统计卡片 + 各阶段执行概览 + 缺陷状态分布
- **功能用例**：
  - **AI 执行用例上传**：上传 Excel（.xlsx/.xls）、Word（.docx/.doc）、XMind（.xmind）
    用例文件，自动解析为测试步骤，按文件名管理并支持预览 / 下载 / 删除；
  - **功能用例管理**：用例的新增 / 编辑 / 删除 / 筛选 / 搜索
- **AI 自动化测试**：
  - **一键 UI 自动化**：输入测试步骤 + 目标 URL，调用本地 **Codex 智能体**，
    使用 **playwright-cli** 技能驱动真实 Chrome 执行，并返回逐条 PASS/FAIL 报告；
    支持勾选上传的 AI 执行用例，勾选后自动用文件解析内容作为测试步骤并锁定输入框，
    未勾选则使用手动输入步骤；
- **接口测试**：维护接口用例，一键发送 HTTP 请求并校验状态码与响应耗时
- **性能测试**：设置并发数与请求量，多线程压测并统计 QPS、平均/P95/最大响应时间、错误率
- **缺陷管理**：缺陷的提交 / 编辑 / 删除 / 按状态与严重程度筛选

## 环境要求

- Python 3.10+

## 配置 DeepSeek 大模型

默认对接 DeepSeek 的 OpenAI 兼容接口 `https://api.deepseek.com`。在项目根目录
新建 `.env` 文件（参考 `.env.example`）：

```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com   # 本地部署时改成 http://127.0.0.1:11434/v1 等
DEEPSEEK_MODEL=deepseek-chat                 # 或 deepseek-reasoner
DEEPSEEK_TIMEOUT=60
```

未配置 `DEEPSEEK_API_KEY`、离线或调用失败时，AI 会自动退回内置规则模板，功能仍可用。

## 前置要求：playwright-cli 与 Codex

一键 UI 自动化依赖本机以下工具：

- `codex` CLI（`codex exec` 非交互调用，需已完成登录/授权）
- `playwright-cli`（`/usr/local/bin/playwright-cli`）与 Node 22
- 系统 Google Chrome

首次执行时，Codex 打开浏览器或联网会弹出授权提示，**需在授权窗口点「允许」**（方案 B）。
若页面报告超时/授权，可复制结果中给出的命令，在终端手动运行并在授权窗口允许。
后续如有需要，可关闭审批以改为纯一键模式。

## 快速开始

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

首次启动会自动创建 SQLite 数据库并写入一批演示数据。数据库文件为同目录下的
`data.db`，如需重置，删除后重启即可。

## 桌面一键启动图标

桌面已生成一个 **AI测试平台** 应用图标，双击即可：

1. 若服务未启动，自动在后台启动（日志写入 `server.log`）；
2. 自动打开默认浏览器进入 http://127.0.0.1:5000 ；
3. 再次点击图标，仅打开浏览器，不会重复启动服务。

停止后台服务：

```bash
cd testing-platform
./stop.sh
```

> 提示：若桌面图标未显示自定义图片，可右键点击图标后重新打开，或在“访达”
> 中刷新一次（首次创建后 Finder 可能需刷新图标缓存）。

## 项目结构

```
testing-platform/
├── app.py              # 应用工厂
├── config.py           # 配置
├── extensions.py       # db 扩展
├── models.py           # 数据模型
├── seed.py             # 演示数据
├── run.py              # 启动入口
├── requirements.txt
├── routes/             # 各菜单的蓝图
├── services/           # AI 生成/接口请求/性能压测 业务逻辑
├── static/             # css / js
└── templates/          # Jinja2 模板
```

## 说明

- 接口测试与性能测试会真实发起 HTTP 请求，请确保目标地址可达（或在内网环境使用）。
- 一键 UI 自动化由本地 Codex + playwright-cli 驱动，执行前请确认本机 Chrome 可用。
- 若遇端口占用，可修改 `run.py` 中的 `port`。
