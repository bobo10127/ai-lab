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

## 项目 1：发票信息提取（v1）

把一段发票文字变成结构化数据，并用本地规则校验。

```powershell
python invoice_extractor.py                  # 内置示例
python invoice_extractor.py "发票文本..."     # 指定文本
python invoice_extractor.py --file a.txt     # 从文件读取
```

输出示例：

```json
{
  "vendor": "北京云帆科技有限公司",
  "tax_id": "91110108MA01ABCD2X",
  "amount": 356.0,
  "date": "2026-10-12",
  "category": "办公"
}
```

设计要点：模型只负责抽取，校验交给本地代码；示例数据全部是编的，不涉及真实发票。

## 项目 1.5：Web 界面（Streamlit）

把命令行工具变成网页。

```powershell
streamlit run app.py
```

浏览器打开 http://localhost:8501 ，粘贴发票文字、点「提取」，就能看到金额、类别、日期和 JSON 结果。侧边栏有「填入一条示例」按钮，方便快速试用。

## 下一步

- [x] 跑通 `demo_similarity.py`
- [x] 申请 DeepSeek API Key，跑通 `hello_ai.py`
- [x] 做第一个小工具：发票信息提取（v1，文本输入）
- [x] 加 Streamlit 界面
- [ ] 发票 v2：接入 OCR，直接读图片
- [ ] 做一个 RAG：报销制度问答
