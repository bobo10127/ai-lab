"""最小可用的 RAG：制度文档问答。

流程：
    切块 -> 建索引（TF-IDF + 中文字符二元组）-> 检索 top-k -> 拼进 prompt -> 模型回答并标注出处

不依赖向量数据库、embedding API 或任何模型下载，纯本地、可离线运行。
以后想升级成真正的向量检索，只需要替换 TfidfIndex 的 search 部分。
"""

import math
import re
from collections import Counter
from pathlib import Path

from openai import OpenAI

DOCS_DIR = Path(__file__).with_name("docs")

SYSTEM_PROMPT = """你是公司报销制度助手。请严格根据下面提供的制度片段回答问题。

规则：
1. 只能使用片段里的信息，不要编造、不要补充片段外的常识。
2. 如果片段里没有答案，直接回答「制度中没有相关规定，建议咨询财务」。
3. 回答要简洁，并在句末用 [1] [2] 标注引用的片段编号。
4. 涉及金额、天数、时限时，必须引用片段中的原文数字。

制度片段：
{context}
"""


def split_markdown(text: str, source: str) -> list[dict]:
    """按二级标题切块；过长的块再按空行拆小。"""
    parts = re.split(r"\n(?=## )", text)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part or part.startswith("# "):
            # 跳过纯一级标题（文档开头）
            body = part
        else:
            body = part
        if not body:
            continue
        title = body.splitlines()[0].lstrip("#").strip()
        # 太长的段落再拆
        if len(body) <= 500:
            chunks.append({"source": source, "title": title, "text": body})
        else:
            for sub in re.split(r"\n\n+", body):
                sub = sub.strip()
                if sub:
                    chunks.append({"source": source, "title": title, "text": sub})
    return chunks


def load_chunks() -> list[dict]:
    chunks = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chunks.extend(split_markdown(text, path.name))
    return chunks


def tokenize(text: str) -> list[str]:
    """英文/数字按词，中文按字符二元组。"""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    han = re.findall(r"[\u4e00-\u9fff]", text)
    tokens += ["".join(han[i : i + 2]) for i in range(len(han) - 1)]
    return tokens


class TfidfIndex:
    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.counters = [
            Counter(tokenize(d["title"] + " " + d["text"])) for d in docs
        ]
        df = Counter()
        for c in self.counters:
            df.update(set(c))
        n = max(len(docs), 1)
        self.idf = {t: math.log((n + 1) / (f + 1)) + 1 for t, f in df.items()}
        self.vectors = [self._vector(c) for c in self.counters]

    def _vector(self, counter: Counter) -> dict:
        vec = {t: c * self.idf.get(t, 0.0) for t, c in counter.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[float, dict]]:
        q = self._vector(Counter(tokenize(query)))
        scored = []
        for idx, vec in enumerate(self.vectors):
            score = sum(q.get(t, 0.0) * w for t, w in vec.items())
            scored.append((score, idx))
        scored.sort(reverse=True)
        return [(s, self.docs[i]) for s, i in scored[:k] if s > 0]


_index = None


def get_index() -> TfidfIndex:
    global _index
    if _index is None:
        _index = TfidfIndex(load_chunks())
    return _index


def answer_question(question: str, client: OpenAI, k: int = 3) -> tuple[str, list[dict]]:
    """检索 + 生成，返回 (回答, 引用片段列表)。"""
    hits = get_index().search(question, k)
    if not hits:
        return "没有检索到相关制度，建议换个问法，或直接咨询财务。", []

    context = "\n\n".join(
        f"[{i + 1}] {doc['title']}\n{doc['text']}"
        for i, (_, doc) in enumerate(hits)
    )

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content or "", [doc for _, doc in hits]


if __name__ == "__main__":
    import sys

    from invoice_extractor import get_client

    q = " ".join(sys.argv[1:]) or "出差住宿标准是多少？"
    ans, sources = answer_question(q, get_client())
    print("问题：", q)
    print("回答：", ans)
    print("\n引用：")
    for i, s in enumerate(sources, 1):
        print(f"[{i}] {s['title']}")
