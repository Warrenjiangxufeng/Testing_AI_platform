from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import PerfRun
from services.perf_runner import run as run_load

perf_bp = Blueprint("perf", __name__)


@perf_bp.route("/")
def index():
    runs = PerfRun.query.order_by(PerfRun.created_at.desc()).all()
    return render_template("perf_test.html", runs=runs)


@perf_bp.route("/run", methods=["POST"])
def run():
    url = request.form.get("url", "").strip()
    if not url:
        flash("请填写压测目标 URL", "error")
        return redirect(url_for("perf.index"))
    name = request.form.get("name", "").strip() or url[:40]
    method = request.form.get("method", "GET")
    concurrent = int(request.form.get("concurrent", 10) or 10)
    total = int(request.form.get("total", 100) or 100)
    headers = request.form.get("headers", "{}")
    body = request.form.get("body", "")

    result = run_load(url, method, concurrent, total, headers, body)
    perf = PerfRun(
        name=name,
        url=url,
        method=method,
        concurrent=concurrent,
        total_requests=total,
        success=result["success"],
        failed=result["failed"],
        qps=result["qps"],
        avg_ms=result["avg_ms"],
        p95_ms=result["p95_ms"],
        max_ms=result["max_ms"],
        error_rate=result["error_rate"],
        status="完成" if result["failed"] == 0 else "存在失败",
    )
    db.session.add(perf)
    db.session.commit()
    flash("压测完成", "success")
    return redirect(url_for("perf.index"))


@perf_bp.route("/<int:run_id>/delete", methods=["POST"])
def delete(run_id):
    perf = PerfRun.query.get_or_404(run_id)
    db.session.delete(perf)
    db.session.commit()
    flash("压测记录已删除", "success")
    return redirect(url_for("perf.index"))

