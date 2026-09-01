from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for

from extensions import db
from models import AIExecCase, AITestRun
from services.ai_engine import execute_script
from services.report import ensure_report
from services.ui_runner import run_ui

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/")
def index():
    runs = AITestRun.query.order_by(AITestRun.created_at.desc()).all()
    ai_exec_cases = AIExecCase.query.order_by(AIExecCase.created_at.desc()).all()
    exec_cases_data = [
        {"id": c.id, "name": c.name, "file_type": c.file_type, "content": c.content}
        for c in ai_exec_cases
    ]
    return render_template(
        "ai_test.html",
        runs=runs,
        ai_exec_cases=ai_exec_cases,
        exec_cases_data=exec_cases_data,
    )


@ai_bp.route("/ai-exec-cases")
def ai_exec_cases():
    """供前端按需获取上传的 AI 执行用例（含解析内容）。"""
    cases = AIExecCase.query.order_by(AIExecCase.created_at.desc()).all()
    return jsonify(
        {
            "cases": [
                {
                    "id": c.id,
                    "name": c.name,
                    "file_type": c.file_type,
                    "size": c.size,
                    "content": c.content,
                }
                for c in cases
            ]
        }
    )


@ai_bp.route("/<int:run_id>")
def detail(run_id):
    run = AITestRun.query.get_or_404(run_id)
    return render_template("ai_test_detail.html", run=run)


@ai_bp.route("/<int:run_id>/report")
def report(run_id):
    """预览测试报告（inline HTML）。"""
    run = AITestRun.query.get_or_404(run_id)
    path = ensure_report(run)
    return send_file(path, mimetype="text/html")


@ai_bp.route("/<int:run_id>/download")
def download(run_id):
    """下载测试报告为 .html 文件。"""
    run = AITestRun.query.get_or_404(run_id)
    path = ensure_report(run)
    return send_file(
        path,
        as_attachment=True,
        download_name=f"ai-test-report-{run.id}.html",
    )


@ai_bp.route("/<int:run_id>/execute", methods=["POST"])
def execute(run_id):
    run = AITestRun.query.get_or_404(run_id)
    result = execute_script(run.generated_script)
    run.status = result["status"]
    run.output = result["output"]
    run.duration = result["duration"]
    db.session.commit()
    ensure_report(run)
    flash(f"执行完成：{result['status']}", "success")
    return redirect(url_for("ai.detail", run_id=run.id))


@ai_bp.route("/<int:run_id>/delete", methods=["POST"])
def delete(run_id):
    run = AITestRun.query.get_or_404(run_id)
    db.session.delete(run)
    db.session.commit()
    flash("已删除该次 AI 测试", "success")
    return redirect(url_for("ai.index"))


@ai_bp.route("/ui-run", methods=["POST"])
def ui_run():
    url = request.form.get("url", "").strip()
    steps = request.form.get("steps", "").strip()
    headed = request.form.get("headed") == "1"
    exec_case_id = request.form.get("exec_case_id", "").strip()
    if not url or not steps:
        flash("请填写目标 URL 和测试步骤", "error")
        return redirect(url_for("ai.index"))

    # 标题：若是从上传文件带出的，用文件名；否则取手动输入步骤的第一行
    title = ""
    if exec_case_id:
        try:
            case = db.session.get(AIExecCase, int(exec_case_id))
        except (ValueError, TypeError):
            case = None
        if case and case.name:
            title = case.name
    if not title:
        title = next(
            (ln.strip() for ln in steps.splitlines() if ln.strip()),
            steps.strip(),
        )
    title = (title or "UI 自动化").strip()
    if len(title) > 200:
        title = title[:200] + "…"

    res = run_ui(url, steps, headed)
    run = AITestRun(
        title=title,
        prompt=steps,
        model="Codex + playwright-cli",
        kind="ui",
        root_url=url,
        generated_script=res["prompt"],   # 交给 Codex 的指令
        output=res["output"],             # Codex 返回的报告 / 授权提示
        status=res["status"],
        duration=res["duration"],
    )
    db.session.add(run)
    db.session.commit()
    ensure_report(run)
    flash(f"UI 自动化执行完成，结果：{run.status}", "success")
    return redirect(url_for("ai.detail", run_id=run.id))
