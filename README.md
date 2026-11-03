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
├── .streamlit/
│   ├── config.toml        # 主题、上传上限、headless
│   └── secrets.toml.example
├── assets/bg.jpg          # 界面背景（代码生成）
├── docs/报销制度.md        # RAG 用的虚构制度文档
├── .env.example           # 环境变量模板
├── .gitignore
├── README.md
├── requirements.txt       # 云端依赖（不含 torch）
├── requirements-local.txt # 本地额外依赖（语义检索）
├── packages.txt           # 云端 apt 系统包（中文字体、libGL）
├── runtime.txt            # Python 版本
├── demo_similarity.py     # 零依赖：余弦相似度演示
├── hello_ai.py            # 调用 DeepSeek 的最小示例
├── invoice_extractor.py   # 发票文本 -> 结构化 JSON + 规则校验
├── ocr.py                 # 图片 -> 文字（RapidOCR）
├── rag.py                 # 切块 + 向量检索 + 带出处的回答
├── export.py              # 记录 -> Excel / PDF
├── make_sample.py         # 生成一张假发票图片
├── make_background.py     # 生成背景图
└── app.py                 # Streamlit 界面
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

## 项目 3：导出 Excel / PDF

提取过的发票会攒进「📊 汇总导出」清单，一次性导出成表，不用一张张往 Excel 里抄。

```powershell
python export.py   # 用内置示例直接生成 sample_export.xlsx / .pdf
```

两种格式各有用途：

| | Excel | PDF |
|---|---|---|
| 给谁 | 财务 | 自己归档、打印 |
| 特点 | 能改、能加行、能透视 | 排版固定、字体内嵌、不会被误改 |
| 合计 | `=SUM()` 公式，改明细自动更新 | 固定数值 |

实现要点：

- 全用代码生成，不依赖 Office 软件，服务器上没装 Excel 也能跑；
- **Excel**：openpyxl 写单元格样式、数字格式（`#,##0.00`）、冻结表头、横向打印一页宽；
- **PDF**：reportlab 排版，中文字体注册 Windows 自带字体（微软雅黑/黑体/宋体），字体会子集化内嵌，文件只有几十 KB；
- 两个函数都只吃 `list[dict]`、返回 `bytes`，Streamlit 的 `download_button` 直接就能用，不落地临时文件。

PDF 里的「合计」行原本用白色字压在浅色底上，几乎看不见——第一次渲染出来才发现，改成深色就好了。**生成的东西一定要自己打开看一眼**。

![导出的 PDF 示例](assets/export_preview.png)

## 界面

背景图由 `make_background.py` 用代码生成（抽象海洋，无版权问题），再以 base64 注入 CSS，不依赖任何外部图片链接。

```powershell
python make_background.py   # 重新生成 assets/bg.jpg
```

## 部署上线（Streamlit Community Cloud）

免费、和 GitHub 绑定，以后每次 push 会自动重新部署。

**云端和本地有三处不一样，不是 bug：**

| | 本地 | 云端 |
|---|---|---|
| 检索 | bge 语义检索 | TF-IDF 关键词检索 |
| 中文字体 | Windows 自带雅黑 | `packages.txt` 装 wqy-microhei |
| API Key | `.env` 文件 | 后台 Secrets |

云端用 TF-IDF 的原因很实在：免费实例只有 **1GB 内存**，`torch` 一装就是两个多 G，导进来直接把实例撑爆。`rag.py` 会检测到 `sentence-transformers` 没装，自动退回关键词检索，功能照常，只是不懂「住个店能报多少」这种换说法的问法。

**四个配置文件各干各的：**

- `requirements.txt` —— Python 依赖，云端只装这些
- `packages.txt` —— apt 系统包：中文字体（PDF 导出要用）、`libgl1`（不然 `import cv2` 直接报 `libGL.so.1` 找不到）
- `runtime.txt` —— Python 版本
- `.streamlit/config.toml` —— 主题色、上传上限、云端关掉自动开浏览器

**部署步骤**

1. 打开 https://share.streamlit.io ，用 GitHub 账号登录并授权
2. New app → 选 `bobo10127/ai-lab` → branch `main` → Main file path `app.py`
3. Advanced settings → Secrets 里填：
   ```toml
   DEEPSEEK_API_KEY = "sk-你的key"
   ```
   想加访问密码，再加一行 `APP_PASSWORD = "自己定一个"`（不设就是不设防，任何人都能刷你的额度）
4. 点 Deploy，等 3～5 分钟装依赖
5. 拿到 `https://xxx.streamlit.app`，按下面清单验一遍

**上线后自检清单**

- [ ] 文本提取 → 能出金额、类别、日期
- [ ] 制度问答 → 答得出，且带 `[1]` 出处
- [ ] 导出 PDF → **中文不是方块**（字体没配好就长这样，最容易翻车的一步）
- [ ] 上传图片 → OCR 能认出字（`libgl1` 没装会直接崩）
- [ ] 刷新页面，侧边栏剩余次数回到 30

**省钱这件事**

免费实例跑模型是花你自己的 DeepSeek 额度。所以做了两道闸：每次会话最多 30 次调用；可选密码门。上线后头几天去 DeepSeek 后台看一眼用量，不对劲就把 key 换了。

另外免费实例闲置约 12 小时会休眠，别人隔天第一次打开要等十几秒唤醒，这很正常。

## 下一步

- [x] 跑通 `demo_similarity.py`
- [x] 申请 DeepSeek API Key，跑通 `hello_ai.py`
- [x] 做第一个小工具：发票信息提取（v1，文本输入）
- [x] 加 Streamlit 界面
- [x] 发票 v2：接入 OCR，直接读图片
- [x] 做一个 RAG：报销制度问答
- [x] 把检索升级成 embedding（语义检索）
- [x] 支持 PDF / Excel 导出
- [x] 部署上线
