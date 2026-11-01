"""发票信息提取 v1：一段文本 -> 结构化 JSON -> 规则校验。

用法：
    python invoice_extractor.py                # 跑内置示例
    python invoice_extractor.py "发票文本..."   # 提取指定文本
    python invoice_extractor.py --file a.txt   # 从文件读取

设计思路：
1. 让模型只做「抽取」，不做判断——输出严格 JSON；
2. 规则校验放在本地代码里，模型说错也拦得住；
3. 不依赖公司真实数据，示例全部是编的。
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).with_name(".env"))

ALLOWED_CATEGORIES = ["差旅", "餐饮", "办公", "交通", "住宿", "其他"]

SYSTEM_PROMPT = """你是一个发票信息提取器。请从用户给的文字中提取字段，只输出 JSON，不要解释。
JSON 字段：
- vendor: 销售方名称，字符串
- tax_id: 销售方纳税人识别号，字符串（去掉空格）
- amount: 价税合计金额，数字，单位元
- date: 开票日期，格式 YYYY-MM-DD
- category: 费用类别，只能从 ["差旅","餐饮","办公","交通","住宿","其他"] 里选一个
无法确定的字段填 null。"""

DEMO_TEXTS = [
    "北京云帆科技有限公司，纳税人识别号 91110108MA01ABCD2X，2026年10月12日，办公用品一批，价税合计 356.00 元。",
    "上海锦江之星宾馆 税号 91310115MA1K3XYZ7Q 住宿费 2026-09-28 金额 480 元",
    "滴滴出行 电子发票 2026年10月3日 交通费 42.50元 税号 91110108MA00123456",
]


def get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("缺少 DEEPSEEK_API_KEY，请先配置 .env")
        raise SystemExit(1)
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def extract_invoice(text: str, client: OpenAI) -> dict:
    """调用模型，把一段文字抽成结构化字段。"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)


def validate(record: dict) -> list[str]:
    """本地规则校验，返回错误列表；空列表表示通过。"""
    errors = []

    vendor = record.get("vendor")
    if not vendor or not str(vendor).strip():
        errors.append("销售方名称为空")

    tax_id = str(record.get("tax_id") or "").replace(" ", "").upper()
    if not tax_id:
        errors.append("缺少纳税人识别号")
    elif not re.fullmatch(r"[0-9A-Z]{15,20}", tax_id):
        errors.append(f"纳税人识别号格式可疑：{tax_id}")
    elif len(tax_id) not in (15, 18, 20):
        errors.append(f"纳税人识别号长度异常：{len(tax_id)} 位")

    amount = record.get("amount")
    if not isinstance(amount, (int, float)):
        errors.append("金额不是数字")
    elif amount <= 0:
        errors.append("金额必须大于 0")
    elif amount > 1_000_000:
        errors.append(f"金额异常偏大：{amount}")

    raw_date = record.get("date")
    try:
        d = date.fromisoformat(str(raw_date))
        if d > date.today():
            errors.append(f"开票日期在未来：{d}")
        elif d.year < 2020:
            errors.append(f"开票日期过早：{d}")
    except (ValueError, TypeError):
        errors.append(f"日期格式不对：{raw_date}")

    category = record.get("category")
    if category not in ALLOWED_CATEGORIES:
        errors.append(f"费用类别不在允许范围：{category}")

    return errors


def show(text: str, client: OpenAI) -> None:
    print("=" * 60)
    print(f"原文：{text}")
    try:
        record = extract_invoice(text, client)
    except Exception as exc:  # 网络、额度、JSON 解析等
        print(f"[提取失败] {exc}")
        return

    print("提取结果：")
    print(json.dumps(record, ensure_ascii=False, indent=2))

    errors = validate(record)
    if errors:
        print("校验未通过：")
        for e in errors:
            print(f"  - {e}")
    else:
        print("校验通过 ✅")


def main() -> None:
    client = get_client()

    if len(sys.argv) > 1 and sys.argv[1] == "--file":
        text = Path(sys.argv[2]).read_text(encoding="utf-8")
        show(text, client)
    elif len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]), client)
    else:
        for t in DEMO_TEXTS:
            show(t, client)
            print()


if __name__ == "__main__":
    main()
