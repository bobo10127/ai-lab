"""图片文字识别（OCR）。

用 RapidOCR（ONNX 版 PP-OCR 模型）：纯本地、免费、不用联网，模型随包安装。
"""

from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

_engine = None


def get_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def image_to_text(image_path: str | Path) -> str:
    """把图片里的文字识别出来，按行拼接。"""
    result, _ = get_engine()(str(image_path))
    if not result:
        return ""
    return "\n".join(item[1] for item in result)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python ocr.py <图片路径>")
        raise SystemExit(1)
    print(image_to_text(sys.argv[1]))
