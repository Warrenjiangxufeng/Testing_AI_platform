from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from extensions import db
from models import ApiCase
from services.request_runner import send

api_bp = Blueprint("api", __name__)


@api_bp.route("/")
def index():
    cases = ApiCase.query.order_by(ApiCase.updated_at.desc()).all()
    return render_template("api_test.html", cases=cases)


@api_bp.route("/request", methods=["POST"])
def quick_request():
    """实时接口请求：接收 JSON，调用 request_runner 并返回结果。"""
    payload = request.get_json(silent=True) or request.form
    method = (payload.get("method") or "GET").upper()
    url = (payload.get("url") or "").strip()
    headers = payload.get("headers", "{}")
    body = payload.get("body", "")
    if not url:
        return jsonify({"ok": False, "error": "请填写请求 URL"}), 400
    result = send(method, url, headers, body)
    result["method"] = method
    return jsonify(result)


@api_bp.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        case = ApiCase(
            name=request.form.get("name", "").strip(),
            method=request.form.get("method", "GET").upper(),
            url=request.form.get("url", "").strip(),
            headers=request.form.get("headers", "{}"),
            body=request.form.get("body", ""),
            expected_status=int(request.form.get("expected_status", 200) or 200),
        )
        if not case.name or not case.url:
            flash("名称和 URL 不能为空", "error")
        else:
            db.session.add(case)
            db.session.commit()
            flash("接口用例已创建", "success")
            return redirect(url_for("api.index"))
    return render_template("api_form.html", case=None)


@api_bp.route("/<int:case_id>/edit", methods=["GET", "POST"])
def edit(case_id):
    case = ApiCase.query.get_or_404(case_id)
    if request.method == "POST":
        case.name = request.form.get("name", "").strip()
        case.method = request.form.get("method", "GET").upper()
        case.url = request.form.get("url", "").strip()
        case.headers = request.form.get("headers", "{}")
        case.body = request.form.get("body", "")
        case.expected_status = int(request.form.get("expected_status", 200) or 200)
        if not case.name or not case.url:
            flash("名称和 URL 不能为空", "error")
        else:
            db.session.commit()
            flash("接口用例已更新", "success")
            return redirect(url_for("api.index"))
    return render_template("api_form.html", case=case)


@api_bp.route("/<int:case_id>/send", methods=["POST"])
def send_once(case_id):
    case = ApiCase.query.get_or_404(case_id)
    result = send(case.method, case.url, case.headers, case.body)
    if result["ok"]:
        case.last_status = result["status_code"]
        case.last_result = (
            "通过" if result["status_code"] == case.expected_status else "失败"
        )
    else:
        case.last_status = None
        case.last_result = "失败"
    case.last_time_ms = result["time_ms"]
    db.session.commit()
    flash(
        f"请求完成：状态 {result['status_code'] or '—'} / "
        f"{result['time_ms']}ms / {case.last_result}",
        "success" if result["ok"] else "error",
    )
    return redirect(url_for("api.index"))


@api_bp.route("/<int:case_id>/delete", methods=["POST"])
def delete(case_id):
    case = ApiCase.query.get_or_404(case_id)
    db.session.delete(case)
    db.session.commit()
    flash("接口用例已删除", "success")
    return redirect(url_for("api.index"))
