"""RAG：制度文档问答，支持两种检索方式。

- embedding：语义检索（默认）。用 bge-small-zh 把句子变成向量，能理解“换个说法”。
- tfidf：关键词检索（旧方案）。零依赖、可离线，但只认字面。

切换方式：
    set RAG_INDEX=tfidf     # Windows 命令行
    $env:RAG_INDEX="tfidf"  # PowerShell

流程：切块 -> 建索引 -> 检索 top-k -> 拼进 prompt -> 模型回答并标注出处。
"""

import math
import os
import re
from collections import Counter
from pathlib import Path

# 必须在导入 sentence_transformers 之前设置，模型才会从国内镜像下载。
# HF_HOME 只在 Windows 本地指向 E 盘（C 盘空间紧张）；云端是 Linux，用默认缓存目录。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
if os.name == "nt":
    os.environ.setdefault("HF_HOME", r"E:\hf-cache")

from openai import OpenAI

DOCS_DIR = Path(__file__).with_name("docs")
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

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
        body = part.strip()
        if not body:
            continue
        title = body.splitlines()[0].lstrip("#").strip()
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
    """关键词检索：TF-IDF + 余弦相似度。"""

    name = "tfidf"

    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.counters = [Counter(tokenize(d["title"] + " " + d["text"])) for d in docs]
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


class EmbeddingIndex:
    """语义检索：bge-small-zh 向量 + 余弦相似度。"""

    name = "embedding"

    def __init__(self, docs: list[dict]):
        from sentence_transformers import SentenceTransformer

        self.docs = docs
        self.model = SentenceTransformer(EMBED_MODEL)
        texts = [d["title"] + "\n" + d["text"] for d in docs]
        self.embeddings = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )

    def search(self, query: str, k: int = 3) -> list[tuple[float, dict]]:
        q = self.model.encode(
            [QUERY_PREFIX + query], normalize_embeddings=True, show_progress_bar=False
        )[0]
        scored = [(float(vec @ q), i) for i, vec in enumerate(self.embeddings)]
        scored.sort(reverse=True)
        return [(s, self.docs[i]) for s, i in scored[:k]]


_index = None


def get_index():
    global _index
    if _index is None:
        kind = os.getenv("RAG_INDEX", "embedding").lower()
        docs = load_chunks()
        if kind == "tfidf":
            _index = TfidfIndex(docs)
        else:
            try:
                _index = EmbeddingIndex(docs)
            except Exception as exc:  # 模型下载失败等，自动退回关键词检索
                print(f"[warn] embedding 初始化失败，回退 tfidf: {exc}")
                _index = TfidfIndex(docs)
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
    idx = get_index()
    print(f"检索方式：{idx.name}")
    print("问题：", q)
    ans, sources = answer_question(q, get_client())
    print("回答：", ans)
    print("\n引用：")
    for i, s in enumerate(sources, 1):
        print(f"[{i}] {s['title']}")
