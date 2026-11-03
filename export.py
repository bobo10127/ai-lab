"""导出：结构化发票记录 -> Excel / PDF。

两种格式各有用途：
- Excel：交给财务，能改、能加公式、能透视；
- PDF：打印归档，排版固定，不会被改坏。

两个函数都只吃 `list[dict]`、吐 `bytes`，
Streamlit 的 download_button 可以直接用，不需要落地临时文件。

单独跑（生成两张示例导出到桌面）：
    python export.py
"""

from __future__ import annotations

import io
from datetime import date, datetime
from pathlib import Path

# 导出的列：表头 + 列宽（Excel 用）
COLUMNS = [
    ("序号", 6),
    ("销售方", 34),
    ("纳税人识别号", 22),
    ("金额（元）", 12),
    ("开票日期", 13),
    ("费用类别", 10),
    ("校验", 9),
]

# 字体候选：(文件路径, TTC 子字体序号)，按顺序找第一个存在的。
# Windows 用系统自带字体；Linux（Streamlit Cloud）靠 packages.txt 装 fonts-wqy-microhei。
# 注意：NotoSansCJK 是 CFF 轮廓的 OTF，reportlab 读不了，别往这里加。
FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyh.ttc", 0),
    (r"C:\Windows\Fonts\simhei.ttf", 0),
    (r"C:\Windows\Fonts\simsun.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/truetype/arphic/uming.ttc", 0),
]
FONT_BOLD_CANDIDATES = [
    (r"C:\Windows\Fonts\msyhbd.ttc", 0),
    (r"C:\Windows\Fonts\msyh.ttc", 0),
]

_FONTS: tuple[str, str] | None = None


def _find_font(candidates: list[tuple[str, int]]) -> tuple[str, int] | None:
    """返回第一个存在的字体 (路径, 序号)。"""
    for path, index in candidates:
        if Path(path).exists():
            return path, index
    return None


def _register_fonts() -> tuple[str, str]:
    """注册中文字体，返回 (常规字体名, 粗体字体名)。

    只注册一次：reportlab 内部就是全局字体表。
    """
    global _FONTS
    if _FONTS is not None:
        return _FONTS

    import os

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # 调试用：设 PDF_FONT=/path/to/font.ttf 可以强制指定字体
    override = os.getenv("PDF_FONT", "").strip()
    normal = (
        (override, 0)
        if override and Path(override).exists()
        else _find_font(FONT_CANDIDATES)
    )
    if normal is None:
        raise RuntimeError(
            "没找到中文字体，PDF 会变成方块。Windows 需要微软雅黑/黑体/宋体；"
            "Linux 上装 fonts-wqy-microhei（Streamlit Cloud 写进 packages.txt）。"
        )
    bold = _find_font(FONT_BOLD_CANDIDATES) or normal

    # 同一个文件不能重复注册同名，这里用两个不同的字体名
    try:
        pdfmetrics.registerFont(TTFont("CJK", normal[0], subfontIndex=normal[1]))
        pdfmetrics.registerFont(TTFont("CJK-Bold", bold[0], subfontIndex=bold[1]))
    except Exception as exc:
        raise RuntimeError(f"中文字体注册失败（{normal[0]}）：{exc}") from exc
    pdfmetrics.registerFontFamily("CJK", normal="CJK", bold="CJK-Bold")

    _FONTS = ("CJK", "CJK-Bold")
    return _FONTS


def _amount(record: dict) -> float | None:
    value = record.get("amount")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _total(records: list[dict]) -> float:
    return sum(a for a in (_amount(r) for r in records) if a is not None)


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _check_status(record: dict) -> str:
    """复用主流程的校验规则，导出表里能看到哪张有问题。"""
    from invoice_extractor import validate

    return "通过" if not validate(record) else "未通过"


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------
def records_to_excel(records: list[dict]) -> bytes:
    """生成 xlsx 文件字节。"""
    if not records:
        raise ValueError("没有可导出的记录")

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.properties import PageSetupProperties

    wb = Workbook()
    ws = wb.active
    ws.title = "发票汇总"

    last_col = len(COLUMNS)
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="1F6F8B")
    total_fill = PatternFill("solid", fgColor="EAF3F5")

    # 标题
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    cell = ws.cell(row=1, column=1, value="报销发票汇总表")
    cell.font = Font(name="微软雅黑", size=16, bold=True, color="1F4E5A")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # 副标题
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    cell = ws.cell(
        row=2,
        column=1,
        value=f"导出时间：{datetime.now():%Y-%m-%d %H:%M}　共 {len(records)} 张",
    )
    cell.font = Font(name="微软雅黑", size=9, color="808080")
    cell.alignment = Alignment(horizontal="right", vertical="center")

    # 表头
    header_row = 4
    for idx, (title, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=idx, value=title)
        cell.font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.row_dimensions[header_row].height = 22

    # 数据
    for i, record in enumerate(records, start=1):
        row = header_row + i
        amount = _amount(record)
        d = _parse_date(record.get("date"))
        status = _check_status(record)

        values = [
            i,
            record.get("vendor") or "-",
            record.get("tax_id") or "-",
            amount if amount is not None else (record.get("amount") or "-"),
            d if d is not None else (record.get("date") or "-"),
            record.get("category") or "-",
            status,
        ]
        for idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=idx, value=value)
            cell.font = Font(name="微软雅黑", size=10)
            cell.border = border
            cell.alignment = Alignment(
                horizontal="left" if idx in (2, 3) else "center",
                vertical="center",
            )
        if amount is not None:
            cell = ws.cell(row=row, column=4)
            cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="right", vertical="center")
        if d is not None:
            ws.cell(row=row, column=5).number_format = "yyyy-mm-dd"
        if status == "未通过":
            ws.cell(row=row, column=7).font = Font(
                name="微软雅黑", size=10, color="C00000", bold=True
            )

    # 合计：写成公式，财务改数字后总额会自动更新
    total_row = header_row + len(records) + 1
    ws.merge_cells(
        start_row=total_row, start_column=1, end_row=total_row, end_column=3
    )
    cell = ws.cell(row=total_row, column=1, value="合计")
    cell.font = Font(name="微软雅黑", size=10, bold=True)
    cell.alignment = Alignment(horizontal="right", vertical="center")

    first_data = header_row + 1
    last_data = header_row + len(records)
    cell = ws.cell(
        row=total_row,
        column=4,
        value=f"=SUM(D{first_data}:D{last_data})",
    )
    cell.font = Font(name="微软雅黑", size=10, bold=True, color="C00000")
    cell.number_format = "#,##0.00"
    cell.alignment = Alignment(horizontal="right", vertical="center")

    for idx in range(1, last_col + 1):
        c = ws.cell(row=total_row, column=idx)
        c.fill = total_fill
        c.border = border
    ws.row_dimensions[total_row].height = 22

    # 冻结表头，滚动时列名不跑
    ws.freeze_panes = f"A{header_row + 1}"
    ws.sheet_view.showGridLines = False

    # 打印：横向、压到一页宽、每页重复表头
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.print_title_rows = f"{header_row}:{header_row}"

    # 公式没有缓存值，让 Excel / WPS 打开时强制重算一次
    wb.calculation.fullCalcOnLoad = True

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def records_to_pdf(records: list[dict], title: str = "报销发票汇总") -> bytes:
    """生成 PDF 文件字节（A4 竖版，带页码）。"""
    if not records:
        raise ValueError("没有可导出的记录")

    normal_font, bold_font = _register_fonts()

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="大肥鱼发票助手",
    )

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont(normal_font, 8)
        canvas.setFillColor(colors.HexColor("#7F8C8D"))
        canvas.drawString(15 * mm, 10 * mm, "大肥鱼发票助手 · 自动生成")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"第 {doc_.page} 页")
        canvas.restoreState()

    title_style = ParagraphStyle(
        "title",
        fontName=bold_font,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1F4E5A"),
    )
    sub_style = ParagraphStyle(
        "sub",
        fontName=normal_font,
        fontSize=9,
        leading=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#7F8C8D"),
    )
    cell_style = ParagraphStyle(
        "cell", fontName=normal_font, fontSize=9, leading=12
    )
    cell_center = ParagraphStyle(
        "cellc", parent=cell_style, alignment=TA_CENTER
    )
    head_center = ParagraphStyle(
        "headc",
        fontName=bold_font,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.white,
    )
    total_label = ParagraphStyle(
        "totlabel",
        fontName=bold_font,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1F4E5A"),
    )

    total = _total(records)
    story = [
        Paragraph(title, title_style),
        Spacer(1, 4 * mm),
        Paragraph(
            f"导出时间：{datetime.now():%Y-%m-%d %H:%M}　共 {len(records)} 张　"
            f"合计 ¥{total:,.2f}",
            sub_style,
        ),
        Spacer(1, 4 * mm),
    ]

    table_data = [
        [
            Paragraph("序号", head_center),
            Paragraph("销售方", head_center),
            Paragraph("纳税人识别号", head_center),
            Paragraph("金额（元）", head_center),
            Paragraph("开票日期", head_center),
            Paragraph("类别", head_center),
        ]
    ]
    for i, record in enumerate(records, start=1):
        amount = _amount(record)
        table_data.append(
            [
                Paragraph(str(i), cell_center),
                Paragraph(str(record.get("vendor") or "-"), cell_style),
                Paragraph(str(record.get("tax_id") or "-"), cell_style),
                Paragraph("-" if amount is None else f"{amount:,.2f}", cell_center),
                Paragraph(str(record.get("date") or "-"), cell_center),
                Paragraph(str(record.get("category") or "-"), cell_center),
            ]
        )
    table_data.append(
        [
            Paragraph("合计", total_label),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph(f"{total:,.2f}", ParagraphStyle(
                "tot", fontName=bold_font, fontSize=9, leading=12,
                alignment=TA_CENTER, textColor=colors.HexColor("#C0392B"),
            )),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
        ]
    )

    table = Table(
        table_data,
        colWidths=[12 * mm, 62 * mm, 44 * mm, 24 * mm, 24 * mm, 14 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F6F8B")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAF3F5")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCD9DD")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7FBFC")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "说明：金额单位元，数据由模型自动提取，请与原始发票核对后使用。",
            ParagraphStyle(
                "note",
                fontName=normal_font,
                fontSize=8,
                leading=12,
                textColor=colors.HexColor("#7F8C8D"),
            ),
        )
    )

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


if __name__ == "__main__":
    samples = [
        {
            "vendor": "北京云帆科技有限公司",
            "tax_id": "91110108MA01ABCD2X",
            "amount": 356.0,
            "date": "2026-10-12",
            "category": "办公",
        },
        {
            "vendor": "上海锦江之星宾馆",
            "tax_id": "91310115MA1K3XYZ7Q",
            "amount": 480,
            "date": "2026-09-28",
            "category": "住宿",
        },
        {
            "vendor": "滴滴出行",
            "tax_id": "91110108MA00123456",
            "amount": 42.5,
            "date": "2026-10-03",
            "category": "交通",
        },
    ]
    out = Path(__file__).with_name("sample_export.xlsx")
    out.write_bytes(records_to_excel(samples))
    print(f"已生成 {out}（{out.stat().st_size} 字节）")

    out_pdf = Path(__file__).with_name("sample_export.pdf")
    out_pdf.write_bytes(records_to_pdf(samples))
    print(f"已生成 {out_pdf}（{out_pdf.stat().st_size} 字节）")
