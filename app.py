"""发票助手 Web 界面（Streamlit）。

运行：
    E:\\ai-lab-venv\\Scripts\\python.exe -m streamlit run app.py

浏览器打开 http://localhost:8501
"""

import base64
import json
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from export import records_to_excel, records_to_pdf
from invoice_extractor import (
    DEMO_TEXTS,
    extract_from_image,
    extract_invoice,
    get_client,
    validate,
)
from rag import answer_question

st.set_page_config(page_title="大肥鱼发票助手", page_icon="🐟", layout="centered")

BG_PATH = Path(__file__).with_name("assets") / "bg.jpg"


def inject_background() -> None:
    """把本地背景图以 base64 方式注入 CSS，避免依赖外部图片链接。"""
    if not BG_PATH.exists():
        return
    b64 = base64.b64encode(BG_PATH.read_bytes()).decode()
    css = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("data:image/jpeg;base64,__B64__");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
[data-testid="stHeader"] {
    background: transparent;
}
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(10px);
}
.block-container {
    background: rgba(255, 255, 255, 0.80);
    backdrop-filter: blur(6px);
    border-radius: 18px;
    padding: 2rem 2.2rem;
    margin-top: 1.5rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
}
</style>
""".replace("__B64__", b64)
    st.markdown(css, unsafe_allow_html=True)


inject_background()


@st.cache_resource
def cached_client():
    """整个会话只创建一个模型客户端。"""
    return get_client()


def add_record(record: dict, source: str) -> int:
    """把提取结果攒进清单，返回累计张数。"""
    records = st.session_state.setdefault("records", [])
    records.append({**record, "_source": source})
    return len(records)


def render_record(record: dict, count: int = 0) -> None:
    """展示提取结果 + 校验结论。"""
    errors = validate(record)
    if errors:
        st.error("校验未通过")
        for e in errors:
            st.write(f"- {e}")
    else:
        st.success("校验通过 ✅")

    c1, c2, c3 = st.columns(3)
    c1.metric("金额（元）", record.get("amount"))
    c2.metric("类别", record.get("category") or "-")
    c3.metric("日期", record.get("date") or "-")

    st.subheader("结构化结果")
    st.json(record)
    with st.expander("复制 JSON"):
        st.code(json.dumps(record, ensure_ascii=False, indent=2), language="json")

    if count:
        st.caption(f"已加入导出清单，当前共 {count} 张 → 去「📊 汇总导出」下载。")


st.title("🐟 大肥鱼发票助手")
st.caption("文本或图片 → 结构化数据 → 本地规则校验")

with st.sidebar:
    st.header("使用说明")
    st.markdown(
        "**文本**：粘贴发票文字直接提取\n\n"
        "**图片**：上传发票照片，先 OCR 再接提取\n\n"
        "**问答**：问报销制度，回答会标注出处\n\n"
        "**导出**：提取过的发票攒成一张表，导 Excel / PDF\n\n"
        "示例数据全部是编的，不涉及真实发票。"
    )
    if st.button("填入一条示例", width="stretch"):
        st.session_state["invoice_text"] = DEMO_TEXTS[0]

tab_text, tab_image, tab_rag, tab_export = st.tabs(
    ["📝 文本输入", "🖼️ 上传图片", "📚 制度问答", "📊 汇总导出"]
)

with tab_text:
    if "invoice_text" not in st.session_state:
        st.session_state["invoice_text"] = ""

    text = st.text_area(
        "发票文字",
        key="invoice_text",
        height=180,
        placeholder="例如：北京云帆科技有限公司，税号 91110108MA01ABCD2X，2026年10月12日，办公用品，价税合计 356.00 元",
    )

    if st.button("提取", type="primary"):
        if not text.strip():
            st.warning("先粘贴一段发票文字。")
        else:
            with st.spinner("正在提取..."):
                try:
                    record = extract_invoice(text, cached_client())
                except Exception as exc:
                    st.error(f"提取失败：{exc}")
                else:
                    count = add_record(record, "文本")
                    render_record(record, count)

with tab_image:
    uploaded = st.file_uploader(
        "上传发票图片", type=["png", "jpg", "jpeg", "bmp", "webp"]
    )
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, width="stretch")

        if st.button("识别并提取", type="primary"):
            suffix = Path(uploaded.name).suffix or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name

            with st.spinner("OCR + 提取中（首次会慢几秒）..."):
                try:
                    record, ocr_text = extract_from_image(tmp_path, cached_client())
                except Exception as exc:
                    st.error(f"处理失败：{exc}")
                else:
                    with st.expander("OCR 识别原文", expanded=False):
                        st.text(ocr_text)
                    count = add_record(record, uploaded.name)
                    render_record(record, count)

with tab_rag:
    st.caption("基于 `docs/报销制度.md` 的本地检索 + 大模型回答，回答会标注出处。")

    question = st.text_input(
        "问一个报销制度问题",
        placeholder="例如：出差住宿标准是多少？",
    )

    if st.button("提问", type="primary"):
        if not question.strip():
            st.warning("先输入一个问题。")
        else:
            with st.spinner("检索并回答中..."):
                try:
                    answer, sources = answer_question(question, cached_client())
                except Exception as exc:
                    st.error(f"回答失败：{exc}")
                else:
                    st.markdown(answer)
                    if sources:
                        with st.expander("查看引用片段"):
                            for i, s in enumerate(sources, 1):
                                st.markdown(f"**[{i}] {s['title']}**")
                                st.caption(s["text"][:300])

with tab_export:
    st.caption("提取过的发票会自动攒在这里，报账时一次性导出，不用一张张往 Excel 里抄。")

    records = st.session_state.setdefault("records", [])

    if not records:
        st.info(
            "清单还是空的。先去「📝 文本输入」或「🖼️ 上传图片」提取几张，再回来导出。"
        )
    else:
        rows = [
            {
                "序号": i,
                "销售方": r.get("vendor") or "-",
                "纳税人识别号": r.get("tax_id") or "-",
                "金额（元）": r.get("amount"),
                "开票日期": r.get("date") or "-",
                "费用类别": r.get("category") or "-",
                "校验": "通过" if not validate(r) else "未通过",
                "来源": r.get("_source", "-"),
            }
            for i, r in enumerate(records, 1)
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

        total = sum(
            a for a in (r.get("amount") for r in records) if isinstance(a, (int, float))
        )
        st.write(f"共 **{len(records)}** 张，合计 **¥{total:,.2f}**")

        stamp = date.today().strftime("%Y%m%d")
        col_xlsx, col_pdf, col_clear = st.columns([1, 1, 0.7])

        with col_xlsx:
            try:
                xlsx_bytes = records_to_excel(records)
            except Exception as exc:
                st.error(f"生成 Excel 失败：{exc}")
            else:
                st.download_button(
                    "⬇️ 下载 Excel",
                    data=xlsx_bytes,
                    file_name=f"发票汇总_{stamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )

        with col_pdf:
            try:
                pdf_bytes = records_to_pdf(records)
            except Exception as exc:
                st.error(f"生成 PDF 失败：{exc}")
            else:
                st.download_button(
                    "⬇️ 下载 PDF",
                    data=pdf_bytes,
                    file_name=f"发票汇总_{stamp}.pdf",
                    mime="application/pdf",
                    width="stretch",
                )

        with col_clear:
            if st.button("清空清单", width="stretch"):
                st.session_state["records"] = []
                st.rerun()

        with st.expander("这两种格式该给谁？"):
            st.markdown(
                "**Excel**：给财务。能改、能继续加行、能透视汇总，"
                "金额列是数字格式、合计是 `=SUM()` 公式，改了明细总额自动跟着变。\n\n"
                "**PDF**：给自己归档或打印。排版固定、字体内嵌，"
                "发给谁打开都一样，不会被误改。\n\n"
                "两个文件都由代码生成，不经过 Office 软件，服务器上没有装 Excel 也能跑。"
            )
