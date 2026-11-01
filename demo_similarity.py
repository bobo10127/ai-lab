"""零依赖小演示：用字符频率计算两句话的余弦相似度。

这是 RAG（检索增强生成）背后最核心的数学：
把文本变成向量，再比较向量有多接近。
"""

import math
from collections import Counter


def vector(text: str) -> Counter:
    """把一句话变成「字符 -> 出现次数」的向量。"""
    return Counter(text)


def cosine(a: Counter, b: Counter) -> float:
    """余弦相似度：值越接近 1，两句话越相似。"""
    common = set(a) & set(b)
    dot = sum(a[ch] * b[ch] for ch in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


pairs = [
    ("我喜欢吃白米饭", "大肥鱼最爱吃白米饭"),
    ("今天天气很好", "明天可能下雨"),
    ("报销单要贴发票", "发票需要贴在报销单上"),
]

for x, y in pairs:
    print(f"{cosine(vector(x), vector(y)):.3f}  {x}  <->  {y}")
