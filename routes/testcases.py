import uuid
from pathlib import Path

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from config import Config
from extensions import db
from models import AIExecCase, TestCase
from services.file_parser import parse_file

testcases_bp = Blueprint("testcases", __name__)

MODULES = []

# 允许上传的扩展名 -> 类型
ALLOWED_EXT = {
    "xlsx": "excel",
    "xls": "excel",
    "docx": "word",
    "doc": "word",
    "xmind": "xmind",
}


def _ai_exec_dir() -> Path:
    """返回 AI 执行用例的上传目录，确保存在。"""
    d = Config.UPLOADS_DIR / "ai_exec"
    d.mkdir(parents=True, exist_ok=True)
    return d


@testcases_bp.route("/")
def list_cases():
    query = TestCase.query
    keyword = request.args.get("q", "").strip()
    module = request.args.get("module", "").strip()
    status = request.args.get("status", "").strip()
    if keyword:
        query = query.filter(TestCase.name.like(f"%{keyword}%"))
    if module:
        query = query.filter_by(module=module)
    if status:
        query = query.filter_by(status=status)
    cases = query.order_by(TestCase.created_at.desc()).all()
    modules = [
        m[0]
        for m in db.session.query(TestCase.module).distinct().all()
        if m[0]
    ]
    ai_exec_cases = AIExecCase.query.order_by(AIExecCase.created_at.desc()).all()
    return render_template(
        "testcases.html", cases=cases, modules=modules,
        ai_exec_cases=ai_exec_cases,
        filters={"q": keyword, "module": module, "status": status},
    )


@testcases_bp.route("/ai-exec/upload", methods=["POST"])
def upload_ai_exec():
    """上传 AI 执行用例文件（Excel / XMind / Word），解析内容后入库。"""
    file = request.files.get("file")
    if not file or not file.filename:
        flash("请选择要上传的用例文件", "error")
        return redirect(url_for("testcases.list_cases", _anchor="ai-exec-upload"))

    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        flash(
            f"不支持的文件类型：{ext or '未知'}（支持 .xlsx / .xls / .docx / .doc / .xmind）",
            "error",
        )
        return redirect(url_for("testcases.list_cases", _anchor="ai-exec-upload"))

    stored_name = f"{uuid.uuid4().hex[:12]}.{ext}"
    save_path = _ai_exec_dir() / stored_name
    try:
        file.save(save_path)
    except Exception as exc:  # noqa: BLE001
        flash(f"文件保存失败：{exc}", "error")
        return redirect(url_for("testcases.list_cases", _anchor="ai-exec-upload"))

    content = parse_file(save_path, ext)
    record = AIExecCase(
        name=filename,
        stored_name=stored_name,
        file_type=ALLOWED_EXT[ext],
        ext=ext,
        size=save_path.stat().st_size,
        content=content,
    )
    db.session.add(record)
    db.session.commit()
    flash(f"已上传并解析：{filename}", "success")
    return redirect(url_for("testcases.list_cases", _anchor="ai-exec-upload"))


@testcases_bp.route("/ai-exec/<int:case_id>/download")
def download_ai_exec(case_id):
    """下载原始文件。"""
    record = AIExecCase.query.get_or_404(case_id)
    path = _ai_exec_dir() / record.stored_name
    if not path.exists():
        flash("文件已丢失，无法下载", "error")
        return redirect(url_for("testcases.list_cases", _anchor="ai-exec-upload"))
    return send_file(path, as_attachment=True, download_name=record.name)


@testcases_bp.route("/ai-exec/<int:case_id>/preview")
def preview_ai_exec(case_id):
    """预览解析后的内容（独立页面，供 iframe 弹窗加载）。"""
    record = AIExecCase.query.get_or_404(case_id)
    return render_template("ai_exec_preview.html", record=record)


@testcases_bp.route("/ai-exec/<int:case_id>/delete", methods=["POST"])
def delete_ai_exec(case_id):
    """删除用例文件（磁盘 + 数据库）。"""
    record = AIExecCase.query.get_or_404(case_id)
    path = _ai_exec_dir() / record.stored_name
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    db.session.delete(record)
    db.session.commit()
    flash("已删除该用例文件", "success")
    return redirect(url_for("testcases.list_cases", _anchor="ai-exec-upload"))


@testcases_bp.route("/create", methods=["GET", "POST"])
def create_case():
    if request.method == "POST":
        case = TestCase(
            name=request.form.get("name", "").strip(),
            module=request.form.get("module", "通用").strip() or "通用",
            priority=request.form.get("priority", "P2"),
            case_type=request.form.get("case_type", "功能"),
            precondition=request.form.get("precondition", ""),
            steps=request.form.get("steps", ""),
            expected_result=request.form.get("expected_result", ""),
            status=request.form.get("status", "草稿"),
            creator=request.form.get("creator", "管理员"),
        )
        if not case.name:
            flash("用例名称不能为空", "error")
        else:
            db.session.add(case)
            db.session.commit()
            flash("用例已创建", "success")
            return redirect(url_for("testcases.list_cases", _anchor="functional-cases"))
    return render_template("testcase_form.html", case=None)


@testcases_bp.route("/<int:case_id>/edit", methods=["GET", "POST"])
def edit_case(case_id):
    case = TestCase.query.get_or_404(case_id)
    if request.method == "POST":
        case.name = request.form.get("name", "").strip()
        case.module = request.form.get("module", "通用").strip() or "通用"
        case.priority = request.form.get("priority", case.priority)
        case.case_type = request.form.get("case_type", case.case_type)
        case.precondition = request.form.get("precondition", "")
        case.steps = request.form.get("steps", "")
        case.expected_result = request.form.get("expected_result", "")
        case.status = request.form.get("status", case.status)
        if not case.name:
            flash("用例名称不能为空", "error")
        else:
            db.session.commit()
            flash("用例已更新", "success")
            return redirect(url_for("testcases.list_cases", _anchor="functional-cases"))
    return render_template("testcase_form.html", case=case)


@testcases_bp.route("/<int:case_id>/delete", methods=["POST"])
def delete_case(case_id):
    case = TestCase.query.get_or_404(case_id)
    db.session.delete(case)
    db.session.commit()
    flash("用例已删除", "success")
    return redirect(url_for("testcases.list_cases", _anchor="functional-cases"))
