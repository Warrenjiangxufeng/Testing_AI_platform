from flask import Blueprint, render_template
from sqlalchemy import func

from models import AITestRun, ApiCase, Bug, PerfRun, TestCase

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    total_cases = TestCase.query.count()
    ai_runs = AITestRun.query.count()
    api_cases = ApiCase.query.count()
    perf_runs = PerfRun.query.count()
    open_bugs = Bug.query.filter(Bug.status.notin_(["已关闭", "已拒绝"])).count()

    # 各测试步骤的成功率概览（供首页小图表使用）
    case_pass = TestCase.query.filter_by(status="通过").count()
    case_fail = TestCase.query.filter_by(status="失败").count()
    ai_pass = AITestRun.query.filter_by(status="通过").count()
    api_pass = ApiCase.query.filter_by(last_result="通过").count()
    perf_pass = PerfRun.query.filter(
        PerfRun.error_rate < 1.0
    ).count()

    bug_status = dict(
        Bug.query.with_entities(Bug.status, func.count(Bug.id))
        .group_by(Bug.status)
        .all()
    )

    stats = {
        "total_cases": total_cases,
        "ai_runs": ai_runs,
        "api_cases": api_cases,
        "perf_runs": perf_runs,
        "open_bugs": open_bugs,
        "case_pass": case_pass,
        "case_fail": case_fail,
        "ai_pass": ai_pass,
        "api_pass": api_pass,
        "perf_pass": perf_pass,
        "bug_status": bug_status,
    }
    return render_template("dashboard.html", stats=stats)

