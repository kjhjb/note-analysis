# 笔记分析工具

将高中数理试卷照片自动整理为手写风格 HTML 电子笔记，支持错题标记识别、圈划重点提取、AI 修正解答生成和跨卷薄弱点分析。

## 功能流程

```
拍照 → CV框选大题 → Web UI微调 → LLM识别(黑字/红字/错题标记/圈划重点/公式)
  → 不确定区域确认 → 合理性审查 → 错题修正解答 → 手写风格HTML渲染 → 跨卷薄弱点分析(仅统计错题)
```

## 核心特色

- **多模态 LLM 识别** — 区分黑色印刷原题、红色手写笔记，识别错题标记（×、╱）和圈划重点
- **AI 修正解答** — 为标记为错误的题目自动生成正确的解答过程和错误分析
- **学霸笔记风格输出** — 手写风 HTML，KaTeX/MathJax 渲染 LaTeX 公式
- **渐进式确认** — 低置信度区域列出让用户确认，避免误识别
- **跨卷薄弱点分析** — 仅统计被识别的错题，生成针对性的提升建议
- **纯本地 + 云端 LLM** — CV 本地运行，LLM 调用 Anthropic 兼容协议，数据本地存储

## 快速开始

### 安装

```bash
cd sourcecode
pip install -r requirements.txt
```

### 配置

支持三种配置方式（优先级：构造参数 > `.env` 文件 > 环境变量）：

#### 方式 1：`.env` 文件（推荐）

在项目目录创建 `.env` 文件：

```
LLM_API_KEY=sk-ant-xxx
LLM_API_URL=https://api.anthropic.com
```

然后 CLI 全局 `--env-file` 选项加载：

```bash
python main.py --env-file .env pipeline ./my-exam
```

#### 方式 2：环境变量

```bash
set LLM_API_KEY=your-api-key
set LLM_API_URL=https://api.anthropic.com
```

### 一键流水线

```bash
python main.py pipeline <试卷照片目录>
```

自动执行：扫描照片 → CV 框选 → LLM 识别 → 不确定区域处理 → 合理性审查 → 错题修正 → HTML 渲染

### 分步执行

| 步骤 | 命令 | 说明 |
|------|------|------|
| 1 | `python main.py init <dir>` | 扫描照片，生成 JSON 骨架 |
| 2 | `python main.py box <dir>` | OpenCV 框选大题，输出预览图 |
| 3 | `python main.py recognize <dir>` | LLM 多模态识别文字、错题标记、圈划重点 |
| 4 | `python main.py uncertain <dir>` | LLM 精化低置信区域 |
| 5 | `python main.py serve <dir>` | 启动 Web UI（框选微调 + 不确定区域确认） |
| 6 | `python main.py review <dir>` | LLM 审查原题与笔记逻辑一致性 |
| 7 | `python main.py correct <dir>` | LLM 为错题生成修正解答 |
| 8 | `python main.py render <dir>` | 渲染手写风格 HTML 笔记 |
| 9 | `python main.py analyze <dir>` | 跨卷薄弱点统计分析 |

## 数据模型

| 模型 | 关键字段 | 说明 |
|------|---------|------|
| `Exam` | examId, photos, boxes, weakPoints | 一份试卷 |
| `QuestionBox` | id, bbox, questionText, annotations | 一道大题 |
| — | `isError, errorMarks` | 错题标记识别结果 |
| — | `circledKeyPoints, circledRegions` | 圈划重点识别结果 |
| — | `correction` | AI 生成的修正解答 |
| `UncertainRegion` | bbox, llmGuess, llmConfidence, userConfirmed | 不确定区域 |
| `WeakPoint` | knowledgePoint, errorCount, llmAdvice | 薄弱点 |

## 输出文件

- `笔记_YYYYMMDD_HHmm.json` — 结构化试卷数据（含识别和修正结果）
- `笔记_YYYYMMDD_HHmm.html` — 手写风格笔记（JSON 内嵌）
- `*_bbox_preview.jpg` — 框选预览图

## 测试

```bash
cd sourcecode
python -m pytest tests/ -v
```

LLM 调用已 mock，无需 API Key。

## 技术栈

- **语言**: Python 3.11+
- **LLM 协议**: Anthropic Messages API（兼容 Claude / GPT-4o 等）
- **计算机视觉**: OpenCV
- **CLI**: click
- **数据模型**: Pydantic
- **Web UI**: FastAPI + 原生 HTML/JS
- **公式渲染**: KaTeX + MathJax
