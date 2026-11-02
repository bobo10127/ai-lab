# ai-lab

大肥鱼的第一个 AI 项目仓库。

## 环境

- Python 3.12
- 虚拟环境在 `E:\ai-lab-venv`（C 盘空间紧张，依赖都放 E 盘）
- Embedding 模型缓存：`E:\hf-cache`
- VS Code + Python 扩展

激活虚拟环境：

```powershell
E:\ai-lab-venv\Scripts\Activate.ps1
```

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

## 项目 1.6：图片识别（OCR）

上传发票图片，先本地 OCR，再交给模型提取。

```powershell
streamlit run app.py   # 用「上传图片」标签页
```

OCR 引擎是 **RapidOCR**（ONNX 版 PP-OCR 模型）：纯本地、免费、不用联网，模型随包安装，不需要额外下载几十 GB。

命令行也能单独测试：

```powershell
python make_sample.py               # 生成一张编造的发票图片
python ocr.py sample_invoice.png    # 看看 OCR 认出了什么
```

## 项目 2：制度问答（RAG）

把 `docs/报销制度.md` 切成块，检索最相关的几段，再让模型「看着材料回答」，并标注出处。

```powershell
streamlit run app.py   # 用「制度问答」标签页
```

原理：

- **切块**：按标题、段落把长文档拆成小段，方便精准检索；
- **检索**：把问题和每段都变成词频向量，用余弦相似度找 top-3；
- **生成**：把检索到的片段塞进 prompt，要求模型只依据片段回答，并标注 `[1] [2]`。

默认用 **embedding 语义检索**：`BAAI/bge-small-zh-v1.5` 把问题和每个片段编码成向量，用余弦相似度找最相关的 3 段。它能理解「住店能报多少钱」和「住宿标准」说的是同一件事。

模型首次运行会从 hf-mirror 下载（约 95MB），缓存在 `E:\hf-cache`。想对比关键词检索，可以切回 TF-IDF：

```powershell
$env:RAG_INDEX="tfidf"
streamlit run app.py
```

实测「住店能报多少钱？」这个问题：TF-IDF 一条都检索不到（字面没有重合），embedding 能准确命中「差旅费」——这就是语义检索的价值。

## 界面

背景图由 `make_background.py` 用代码生成（抽象海洋，无版权问题），再以 base64 注入 CSS，不依赖任何外部图片链接。

```powershell
python make_background.py   # 重新生成 assets/bg.jpg
```

## 下一步

- [x] 跑通 `demo_similarity.py`
- [x] 申请 DeepSeek API Key，跑通 `hello_ai.py`
- [x] 做第一个小工具：发票信息提取（v1，文本输入）
- [x] 加 Streamlit 界面
- [x] 发票 v2：接入 OCR，直接读图片
- [x] 做一个 RAG：报销制度问答
- [x] 把检索升级成 embedding（语义检索）
- [ ] 支持 PDF / Excel 导出
- [ ] 部署上线
