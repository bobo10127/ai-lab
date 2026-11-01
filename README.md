# ai-lab

大肥鱼的第一个 AI 项目仓库。

## 环境

- Python 3.12（虚拟环境在 `.venv/`）
- VS Code + Python 扩展

## 快速开始

```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 跑第一个演示（不需要任何 API Key）
python demo_similarity.py

# 跑模型调用（需要 API Key）
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
python hello_ai.py
```

## 目录

```text
ai-lab/
├── .venv/               # 虚拟环境（不提交）
├── .env.example         # 环境变量模板
├── .gitignore
├── README.md
├── requirements.txt
├── demo_similarity.py   # 零依赖：余弦相似度演示
└── hello_ai.py          # 调用 DeepSeek 的最小示例
```

## 下一步

- [ ] 跑通 `demo_similarity.py`
- [ ] 申请 DeepSeek API Key，跑通 `hello_ai.py`
- [ ] 做第一个小工具：发票信息提取
- [ ] 加规则校验 + Streamlit 界面
- [ ] 做一个 RAG：报销制度问答
