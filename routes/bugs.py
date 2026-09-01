from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Bug

bugs_bp = Blueprint("bugs", __name__)


@bugs_bp.route("/")
def index():
    query = Bug.query
    status = request.args.get("status", "").strip()
    severity = request.args.get("severity", "").strip()
    if status:
        query = query.filter_by(status=status)
    if severity:
        query = query.filter_by(severity=severity)
    bugs = query.order_by(Bug.created_at.desc()).all()
    return render_template(
        "bugs.html", bugs=bugs,
        filters={"status": status, "severity": severity},
    )


@bugs_bp.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        bug = Bug(
            title=request.form.get("title", "").strip(),
            module=request.form.get("module", "通用").strip() or "通用",
            severity=request.form.get("severity", "一般"),
            priority=request.form.get("priority", "P2"),
            status=request.form.get("status", "新建"),
            assignee=request.form.get("assignee", ""),
            description=request.form.get("description", ""),
            steps=request.form.get("steps", ""),
        )
        if not bug.title:
            flash("缺陷标题不能为空", "error")
        else:
            db.session.add(bug)
            db.session.commit()
            flash("缺陷已提交", "success")
            return redirect(url_for("bugs.index"))
    return render_template("bug_form.html", bug=None)


@bugs_bp.route("/<int:bug_id>/edit", methods=["GET", "POST"])
def edit(bug_id):
    bug = Bug.query.get_or_404(bug_id)
    if request.method == "POST":
        bug.title = request.form.get("title", "").strip()
        bug.module = request.form.get("module", "通用").strip() or "通用"
        bug.severity = request.form.get("severity", bug.severity)
        bug.priority = request.form.get("priority", bug.priority)
        bug.status = request.form.get("status", bug.status)
        bug.assignee = request.form.get("assignee", "")
        bug.description = request.form.get("description", "")
        bug.steps = request.form.get("steps", "")
        if not bug.title:
            flash("缺陷标题不能为空", "error")
        else:
            db.session.commit()
            flash("缺陷已更新", "success")
            return redirect(url_for("bugs.index"))
    return render_template("bug_form.html", bug=bug)


@bugs_bp.route("/<int:bug_id>/delete", methods=["POST"])
def delete(bug_id):
    bug = Bug.query.get_or_404(bug_id)
    db.session.delete(bug)
    db.session.commit()
    flash("缺陷已删除", "success")
    return redirect(url_for("bugs.index"))

