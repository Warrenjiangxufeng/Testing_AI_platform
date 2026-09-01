from datetime import datetime

from extensions import db


class TestCase(db.Model):
    __tablename__ = "test_case"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    module = db.Column(db.String(100), default="通用")
    priority = db.Column(db.String(20), default="P1")  # P1/P2/P3/P4
    case_type = db.Column(db.String(30), default="功能")  # 功能/接口/兼容/性能
    precondition = db.Column(db.Text, default="")
    steps = db.Column(db.Text, default="")
    expected_result = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="草稿")  # 草稿/待执行/通过/失败/阻塞
    creator = db.Column(db.String(50), default="管理员")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now
    )


class AITestRun(db.Model):
    __tablename__ = "ai_test_run"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="")
    prompt = db.Column(db.Text, default="")
    model = db.Column(db.String(50), default="GPT-5 助手")
    generated_script = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="未执行")  # 未执行/通过/失败/错误
    output = db.Column(db.Text, default="")
    duration = db.Column(db.Float, default=0.0)
    kind = db.Column(db.String(20), default="script")      # script / ui
    root_url = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)


class AIExecCase(db.Model):
    """上传的 AI 执行用例文件（Excel / XMind / Word）。"""

    __tablename__ = "ai_exec_case"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)          # 原始文件名（展示用）
    stored_name = db.Column(db.String(255), nullable=False)   # 磁盘上的存储文件名
    file_type = db.Column(db.String(30), default="")          # excel / word / xmind
    ext = db.Column(db.String(20), default="")
    size = db.Column(db.Integer, default=0)
    content = db.Column(db.Text, default="")                  # 解析后的文本（测试步骤）
    created_at = db.Column(db.DateTime, default=datetime.now)


class ApiCase(db.Model):
    __tablename__ = "api_case"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(10), default="GET")
    url = db.Column(db.String(500), nullable=False)
    headers = db.Column(db.Text, default="{}")
    body = db.Column(db.Text, default="")
    expected_status = db.Column(db.Integer, default=200)
    last_status = db.Column(db.Integer)
    last_time_ms = db.Column(db.Float)
    last_result = db.Column(db.String(20), default="未执行")  # 通过/失败/未执行
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now
    )


class PerfRun(db.Model):
    __tablename__ = "perf_run"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="")
    url = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), default="GET")
    concurrent = db.Column(db.Integer, default=10)
    total_requests = db.Column(db.Integer, default=100)
    success = db.Column(db.Integer, default=0)
    failed = db.Column(db.Integer, default=0)
    qps = db.Column(db.Float, default=0.0)
    avg_ms = db.Column(db.Float, default=0.0)
    p95_ms = db.Column(db.Float, default=0.0)
    max_ms = db.Column(db.Float, default=0.0)
    error_rate = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="未执行")
    created_at = db.Column(db.DateTime, default=datetime.now)


class Bug(db.Model):
    __tablename__ = "bug"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    module = db.Column(db.String(100), default="通用")
    severity = db.Column(db.String(20), default="一般")  # 致命/严重/一般/轻微/建议
    priority = db.Column(db.String(20), default="P2")
    status = db.Column(db.String(20), default="新建")  # 新建/进行中/已修复/已关闭/已拒绝
    assignee = db.Column(db.String(50), default="")
    description = db.Column(db.Text, default="")
    steps = db.Column(db.Text, default="")
    creator = db.Column(db.String(50), default="管理员")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now
    )
