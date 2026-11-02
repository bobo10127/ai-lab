"""生成一张抽象海洋背景图，供 Streamlit 界面使用。

不需要联网、不涉及版权素材，纯代码画出来的。
"""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H = 1400, 800
OUT = Path(__file__).with_name("assets") / "bg.jpg"
OUT.parent.mkdir(exist_ok=True)

# 1. 垂直渐变：浅蓝 -> 海蓝
img = Image.new("RGB", (W, H))
draw = ImageDraw.Draw(img)
top = (238, 248, 255)
bottom = (166, 205, 235)
for y in range(H):
    t = y / H
    color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    draw.line([(0, y), (W, y)], fill=color)

# 2. 柔和的白色光斑
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)
random.seed(7)
for _ in range(16):
    x = random.randint(-100, W + 100)
    y = random.randint(-100, H + 100)
    r = random.randint(90, 280)
    od.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, random.randint(18, 50)))
overlay = overlay.filter(ImageFilter.GaussianBlur(70))
img = Image.alpha_composite(img.convert("RGBA"), overlay)

# 3. 几条淡淡的水波线
wave = ImageDraw.Draw(img)
for k in range(5):
    amp = 10 + k * 4
    offset = k * 46
    points = []
    for x in range(0, W, 8):
        y = H * 0.6 + offset + amp * math.sin(x / 170 + k)
        points.append((x, y))
    wave.line(points, fill=(255, 255, 255, 55), width=3)

img = img.filter(ImageFilter.GaussianBlur(2))
img.convert("RGB").save(OUT, quality=82)
print(f"saved: {OUT} ({OUT.stat().st_size // 1024} KB)")
