"""解析上传的 Excel / XMind / Word 用例文件为可用的测试步骤文本。

设计：全部使用 Python 标准库（zipfile / xml / json），不新增第三方依赖，
方便离线环境直接运行。覆盖：
- .xlsx（现代 Excel，ZIP+XML）
- .xls（传统 Excel，二进制；若安装了 xlrd 则解析，否则给出提示）
- .docx（现代 Word，ZIP+XML）
- .doc（传统 Word，二进制；尝试读取可读文本，失败给出提示）
- .xmind（XMind 思维导图，ZIP，支持 content.json / content.xml 两种格式）
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# OpenXML / XMind 命名空间
_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_XMIND_NS = "{http://www.xmind.net/xmap}"

_UNSUPPORTED = "（该文件格式暂无法解析，请改用 .xlsx / .docx / .xmind 格式上传）"


def _cell_text(cell) -> str:
    """读取 xlsx 单元格 <c> 的文本值（内联字符串 / 普通值）。"""
    t = cell.get("t")
    if t == "inlineStr":
        is_el = cell.find(f"{_XLSX_NS}is")
        if is_el is None:
            return ""
        return "".join(n.text or "" for n in is_el.iter(f"{_XLSX_NS}t"))
    v = cell.find(f"{_XLSX_NS}v")
    if v is None or v.text is None:
        return ""
    return v.text.strip()


def _extract_xlsx(path: Path) -> str:
    """解析 .xlsx：依次读取所有 sheet，每个非空行转成一行文本。"""
    lines: list[str] = []
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root:
                txt = "".join(n.text or "" for n in si.iter(f"{_XLSX_NS}t"))
                shared.append(txt)

        sheet_names = sorted(
            n for n in zf.namelist()
            if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
        )
        if not sheet_names:
            return _UNSUPPORTED

        for sheet_name in sheet_names:
            root = ET.fromstring(zf.read(sheet_name))
            for row in root.iter(f"{_XLSX_NS}row"):
                cells: list[str] = []
                for c in row.iter(f"{_XLSX_NS}c"):
                    text = _cell_text(c)
                    if c.get("t") == "s":
                        v = c.find(f"{_XLSX_NS}v")
                        idx = int(v.text) if v is not None and v.text else -1
                        text = shared[idx] if 0 <= idx < len(shared) else ""
                    cells.append(text)
                line = "\t".join(cells)
                if line.strip("\t "):
                    lines.append(line)
    return "\n".join(lines)


def _extract_xls(path: Path) -> str:
    """解析传统 .xls：优先使用 xlrd；未安装时给出友好提示。"""
    try:
        import xlrd  # type: ignore
    except ImportError:
        return (
            "（无法解析 .xls：当前环境未安装 xlrd。"
            "请在 requirements.txt 添加 xlrd，或改用 .xlsx 上传。）"
        )
    lines: list[str] = []
    book = xlrd.open_workbook(path, on_demand=True)
    for sheet in book.sheets():
        for r in range(sheet.nrows):
            vals = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
            line = "\t".join(vals)
            if line.strip("\t "):
                lines.append(line)
    return "\n".join(lines)


def _extract_docx(path: Path) -> str:
    """解析 .docx：遍历 <w:p> 段落，把段内 <w:t> 文本拼接成一行。"""
    with zipfile.ZipFile(path) as zf:
        if "word/document.xml" not in zf.namelist():
            return _UNSUPPORTED
        root = ET.fromstring(zf.read("word/document.xml"))
    lines: list[str] = []
    for p in root.iter(f"{_WORD_NS}p"):
        texts = [n.text for n in p.iter(f"{_WORD_NS}t") if n.text]
        line = "".join(texts).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _extract_doc(path: Path) -> str:
    """传统 .doc：尝试从二进制中提取可读文本片段。"""
    try:
        raw = path.read_bytes()
    except OSError:
        return _UNSUPPORTED
    text = raw.decode("utf-8", errors="ignore")
    lines = re.findall(
        r"[\u4e00-\u9fa5A-Za-z0-9，。、；：！？（）【】\s\.\,\-\+\*#/]{4,}", text
    )
    cleaned = [ln.strip() for ln in lines if ln.strip()]
    if cleaned:
        return "\n".join(cleaned)
    return "（传统 .doc 文本无法解析，请另存为 .docx 后上传。）"


# ---- XMind ----


def _xmind_walk_json(topic: dict, depth: int, lines: list[str]) -> None:
    title = (topic.get("title") or "").strip()
    if title:
        lines.append("  " * depth + title)
    for child in topic.get("children", {}).get("attached", []) or []:
        _xmind_walk_json(child, depth + 1, lines)


def _xmind_from_json(data) -> str:
    lines: list[str] = []
    for sheet in data or []:
        if isinstance(sheet, dict) and "rootTopic" in sheet:
            _xmind_walk_json(sheet["rootTopic"], 0, lines)
    return "\n".join(lines)


def _xmind_walk_xml(topic, depth: int, lines: list[str], ns: str) -> None:
    title_el = topic.find(f"{ns}title") or topic.find("title")
    title = title_el.text.strip() if title_el is not None and title_el.text else ""
    if title:
        lines.append("  " * depth + title)
    children = topic.find(f"{ns}children") or topic.find("children")
    if children is None:
        return
    topics = children.find(f"{ns}topics") or children.find("topics")
    if topics is None:
        return
    for child in list(topics.findall(f"{ns}topic")) + list(topics.findall("topic")):
        _xmind_walk_xml(child, depth + 1, lines, ns)


def _xmind_from_xml(data: bytes) -> str:
    root = ET.fromstring(data)
    if root.tag.startswith("{"):
        ns = f"{root.tag.split('}')[0].lstrip('{')}"
    else:
        ns = ""
    lines: list[str] = []
    sheets = root.findall(f"{ns}sheet") or root.findall("sheet")
    for sheet in sheets:
        topic = sheet.find(f"{ns}topic") or sheet.find("topic")
        if topic is not None:
            _xmind_walk_xml(topic, 0, lines, ns)
    if not lines:
        for topic in root.iter(f"{ns}topic") or root.iter("topic"):
            title_el = topic.find(f"{ns}title") or topic.find("title")
            if title_el is not None and title_el.text:
                lines.append(title_el.text.strip())
    return "\n".join(lines)


def _extract_xmind(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "content.json" in names:
            try:
                data = json.loads(zf.read("content.json").decode("utf-8"))
                out = _xmind_from_json(data)
                if out.strip():
                    return out
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        if "content.xml" in names:
            raw = zf.read("content.xml")
            try:
                out = _xmind_from_xml(raw)
                if out.strip():
                    return out
            except ET.ParseError:
                pass
    return _UNSUPPORTED


def parse_file(path: Path, ext: str) -> str:
    """根据扩展名解析文件，返回文本字符串（用于作为测试步骤）。"""
    ext = (ext or "").lower().lstrip(".")
    if ext == "xlsx":
        return _extract_xlsx(path)
    if ext == "xls":
        return _extract_xls(path)
    if ext == "docx":
        return _extract_docx(path)
    if ext == "doc":
        return _extract_doc(path)
    if ext == "xmind":
        return _extract_xmind(path)
    return _UNSUPPORTED
