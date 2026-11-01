"""生成一张假的发票图片，用于本地测试 OCR。

不涉及任何真实发票，所有内容都是编的。
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\msyh.ttc"  # 微软雅黑
OUT = Path(__file__).with_name("sample_invoice.png")

lines = [
    ("增值税电子普通发票", 34),
    ("", 10),
    ("购买方：湖南科技大学", 24),
    ("销售方：北京云帆科技有限公司", 24),
    ("纳税人识别号：91110108MA01ABCD2X", 24),
    ("开票日期：2026年10月12日", 24),
    ("货物名称：办公用品", 24),
    ("价税合计（大写）：叁佰伍拾陆元整", 24),
    ("¥356.00", 30),
]

img = Image.new("RGB", (1000, 620), "white")
draw = ImageDraw.Draw(img)

y = 30
for text, size in lines:
    if text:
        font = ImageFont.truetype(FONT, size)
        draw.text((50, y), text, fill="black", font=font)
    y += size + 18

draw.rectangle([20, 20, 980, 600], outline="gray", width=2)
img.save(OUT)
print(f"saved: {OUT}")
