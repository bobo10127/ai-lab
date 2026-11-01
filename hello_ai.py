"""第一个 AI 程序：调用 DeepSeek 聊天接口。

用法：
1. 复制 .env.example 为 .env
2. 在 .env 里填入 DEEPSEEK_API_KEY=sk-...
3. 运行：python hello_ai.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

if not api_key:
    print("还没有配置 API Key。")
    print("1) 复制 .env.example 为 .env")
    print("2) 把 DEEPSEEK_API_KEY 填进去")
    print("3) 重新运行 python hello_ai.py")
    raise SystemExit(0)

from openai import OpenAI

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一只叫大肥鱼的助手，回答简短、友好。"},
        {"role": "user", "content": "用一句话介绍你自己。"},
    ],
)
print(resp.choices[0].message.content)
