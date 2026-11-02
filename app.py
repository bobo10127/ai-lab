"""发票助手 Web 界面（Streamlit）。

运行：
    E:\\ai-lab-venv\\Scripts\\python.exe -m streamlit run app.py

浏览器打开 http://localhost:8501
"""

import base64
import json
import tempfile
from pathlib import Path

import streamlit as st

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


def render_record(record: dict) -> None:
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


st.title("🐟 大肥鱼发票助手")
st.caption("文本或图片 → 结构化数据 → 本地规则校验")

with st.sidebar:
    st.header("使用说明")
    st.markdown(
        "**文本**：粘贴发票文字直接提取\n\n"
        "**图片**：上传发票照片，先 OCR 再接提取\n\n"
        "**问答**：问报销制度，回答会标注出处\n\n"
        "示例数据全部是编的，不涉及真实发票。"
    )
    if st.button("填入一条示例", use_container_width=True):
        st.session_state["invoice_text"] = DEMO_TEXTS[0]

tab_text, tab_image, tab_rag = st.tabs(["📝 文本输入", "🖼️ 上传图片", "📚 制度问答"])

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
                    render_record(record)

with tab_image:
    uploaded = st.file_uploader(
        "上传发票图片", type=["png", "jpg", "jpeg", "bmp", "webp"]
    )
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)

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
                    render_record(record)

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
