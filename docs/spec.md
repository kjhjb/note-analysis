# 笔记分析工具 — 产品规格说明书 (PRD / Spec)

## Problem Statement

高中学生在日常刷题、整理试卷时，面对大量带有红笔批注、错题标记和圈划重点的卷子，需要一种自动化的方式将物理和数学试卷整理成清晰的电子笔记。现有方案要么需要手动录入（耗时），要么 OCR 对公式和手写红字识别效果差，更无法跨卷分析薄弱环节。

学生需要一个工具：拍试卷 → 自动框选大题 → 识别黑字原题、红字笔记、错题标记和圈划重点 → 处理字迹不清处 → 生成错题修正解答 → 生成手写风格笔记 HTML → 跨卷分析薄弱点（仅统计错题），全流程在本地完成，数据隐私可控。

## Solution

一个 Python CLI 工具（AI Agent 内核 + 传统 CV 辅助），处理流程如下：

```
拍照(单张或多张) → CV框选大题 → Web UI微调 → LLM识别(黑字/红字/错题标记/圈划重点/公式)
  → 不确定区域确认 → 合理性审查 → 错题修正解答生成 → 学霸笔记风格HTML渲染 → 跨卷薄弱点分析(仅统计错题)
```

核心特色：
- **纯本地 + 云端 LLM**：CV 部分本地运行，识别部分调用云端多模态 LLM（Anthropic 兼容协议）
- **AI Agent 编排**：所有 LLM 相关操作由统一 Agent 框架编排，共享上下文
- **学霸笔记风格输出**：参考"学霸笔记"skill 的手写风 HTML 渲染
- **渐进式确认**：低置信度区域统一列出让用户确认，避免误识别
- **错题标记识别**：自动识别试卷中的打叉（×）、画斜线（\）等错误标记，区分对错
- **圈划重点提取**：识别被圆圈、下划线、高亮标注的关键内容
- **AI 生成修正解答**：为错题自动生成详细的正确解答和错误分析
- **跨卷积累**：多份试卷 JSON 本地存储，支持知识点错误频次统计（仅统计被识别的错题）和 LLM 建议

## User Stories

1. 作为学生，我想要把一张或多张试卷照片输入 CLI，以便自动开始整理流程
2. 作为学生，我想要系统自动检测每道大题的边界框，以便不需要手动框选
3. 作为学生，我想要在浏览器中拖拽调整框选位置，以便纠正自动检测的偏差
4. 作为学生，我想要系统自动识别黑色原题文字和红色笔记文字，以便区分题目和我的批注
5. 作为学生，我想要数学和物理公式被识别为 LaTeX，以便在 HTML 中通过 MathJax/KaTeX 正确渲染
6. 作为学生，我想要原题中的图片被保留，以便笔记内容完整
7. 作为学生，我想要字迹不清的区域被标记出来，以便我确认 LLM 的猜测是否正确
8. 作为学生，我想要在一个界面中浏览所有不确定区域批量处理，以便不需要逐个切换
9. 作为学生，我可以接受 LLM 的猜测、手动输入正确内容、或标记忽略，以便灵活处理每处不确定
10. 作为学生，我想要系统审查文本逻辑一致性，以便发现原题和笔记之间的矛盾
11. 作为学生，我想要最终输出一个手写风格的 HTML 笔记页，以便直接用于复习
12. 作为学生，我想要 LaTeX 公式在 HTML 中正确渲染，以便公式清晰可读
13. 作为学生，我想要 JSON 数据嵌入在 HTML 中，以便 AI 后续可以直接读取分析
14. 作为学生，我想要多张卷子的数据累积后能看到薄弱点统计，以便知道哪些知识点掌握不足
15. 作为学生，我想要 LLM 基于薄弱点生成提升建议（使用高中物数专有名词），以便针对性复习
16. 作为学生，我想要文件按 `笔记_YYYYMMDD_HHmm.{json,html}` 自动命名，以便按时间管理
17. 作为学生，我想要整个流程通过一条命令启动，以便操作简单
18. 作为学生，我想要系统自动识别被打了叉号或斜线的错题，以便我知道哪些题做错了
19. 作为学生，我想要系统识别试卷上被圈划或高亮标记的重点内容，以便复习时聚焦关键
20. 作为学生，我想要易错点总结只统计真正做错了的题目，以便分析结果更准确
21. 作为学生，我想要系统为每道错题自动生成正确的解答和错误分析，以便直接对照学习

## Implementation Decisions

### 系统架构

- **语言**：Python 3.11+
- **CLI 框架**：click（参数简洁、子命令支持好）
- **包管理**：pip + requirements.txt（轻量，无需 poetry）

### 模块划分

1. **Agent Core** (`agent/`) — AI Agent 编排层
   - LLM 调用管理器（Anthropic Messages API 兼容，`/v1/messages` 端点）
   - 上下文窗口管理（整卷上下文传递给 LLM）
   - Skill 加载器（读取 SKILL.md 并按工作流执行）
   - 所有 LLM 相关的 ticket（04, 05, 06, 07, 08, 09）共用此模块

2. **Data Models** (`models/`) — Pydantic 数据模型
   - `Exam`：试卷（exam_id, 照片路径列表, 框选区列表, 生成时间）
   - `QuestionBox`：框选区（id, bbox[x,y,w,h], questionText, annotations, isError, errorMarks, circledKeyPoints, circledRegions, uncertainRegions, review, correction）
   - `UncertainRegion`：不确定区域（bbox, llmGuess, userConfirmed）
   - `WeakPoint`：薄弱点（knowledgePoint, errorCount, llmAdvice）
   - `BBox`：边界框
   - JSON 序列化/反序列化，文件命名为 `笔记_YYYYMMDD_HHmm.json`

3. **CV Engine** (`cv/`) — 传统计算机视觉（纯 OpenCV，不涉及 LLM）
   - 图像预处理：灰度化、二值化、去噪、倾斜校正
   - 自然段检测：投影法/轮廓分析检测大题边界
   - 生成 bbox 预览图

4. **Web UI** (`web/`) — 临时 Web 服务
   - FastAPI + 原生 HTML/JS（无额外前端框架）
   - 框选微调页面（Canvas 拖拽矩形）
   - 不确定区域确认页面（缩略图 + 选择/输入框）

5. **Renderer** (`renderer/`) — HTML 渲染
   - 加载"学霸笔记"SKILL.md 并按工作流执行
   - 使用 Style A（学霸笔记本）模板
   - MathJax/KaTeX 渲染 LaTeX
   - base64 内嵌原题图片
   - JSON 嵌入 HTML `<script>` 标签

6. **Analyzer** (`analyzer/`) — 跨卷分析
   - 本地知识点评错频次统计
   - LLM 生成提升建议 Prompt

### API 协议

- 所有 LLM 调用使用 **Anthropic Messages API 格式**（`/v1/messages`）
- 兼容 Anthropic Claude、或任何提供 Anthropic 兼容接口的服务
- API Key 通过环境变量或配置文件传入
- 模型支持：Claude Sonnet 4 / GPT-4o 等（通过兼容层切换）

### 数据结构 (Pydantic Schema)

```python
# 核心数据模型原型（来自 grilling 阶段确定）
class BBox(BaseModel):
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)

class UncertainRegion(BaseModel):
    bbox: BBox
    llmGuess: str          # LLM 原始猜测文本
    llmConfidence: float = Field(ge=0, le=1)  # 置信度 0~1
    userConfirmed: str | None = None  # 用户确认后填充

class QuestionBox(BaseModel):
    id: int
    bbox: BBox
    photoIndex: int = 0
    questionText: str = ""       # 黑色原题文字（含 LaTeX 标记）
    annotations: str = ""        # 红色笔记文字（含 LaTeX 标记）
    images: list[str] = []       # base64 或图片引用
    uncertainRegions: list[UncertainRegion] = []
    reviewStatus: str = "pending"  # pending / consistent / inconsistent / uncertain
    reviewNotes: str = ""
    isError: bool = False                    # 是否有打叉/斜线等错误标记
    errorMarks: list[str] = []               # 错误标记类型列表 ["cross", "backslash"]
    circledKeyPoints: str = ""               # 圈划/高亮标注的重点内容文字
    circledRegions: list[BBox] = []          # 圈划区域的位置坐标
    correction: str = ""                     # 错题修正解答（含正确解答和错误分析）

class Exam(BaseModel):
    examId: str                  # 自动生成
    photos: list[str]            # 原始照片路径
    boxes: list[QuestionBox] = []
    createdAt: str               # YYYYMMDD_HHmm
    weakPoints: list[WeakPoint] = []  # 仅跨卷分析时填充

class WeakPoint(BaseModel):
    knowledgePoint: str
    errorCount: int = Field(ge=0)
    llmAdvice: str
```

### CLI 子命令

```
main.py init <exam-dir>          # 扫描照片生成初始 JSON
main.py box <exam-dir>           # CV 框选大题
main.py serve <exam-dir>         # 启动 Web UI（框选微调 + 不确定确认）
main.py recognize <exam-dir>     # Agent 调用 LLM 识别（含错题标记和圈划重点）
main.py uncertain <exam-dir>     # Agent 调用 LLM 精化不确定区域
main.py review <exam-dir>        # Agent 调用 LLM 合理性审查
main.py correct <exam-dir>       # Agent 调用 LLM 为错题生成修正解答
main.py render <exam-dir>        # Agent 调用学霸笔记 skill 渲染 HTML
main.py analyze <exams-dir>      # Agent 跨卷薄弱点分析（仅统计 isError=true 的错题）
main.py pipeline <exam-dir>      # 一键流水线: init→box→recognize→uncertain→review→correct→render
```

## Testing Decisions

### 测试原则

- 只测外部行为，不测实现细节
- 所有依赖外部 API（LLM）的操作通过 mock 进行
- 使用 pytest 作为测试框架

### 测试层级

| 层级 | 范围 | 工具 | 关键测试内容 |
|------|------|------|------------|
| **E2E** | 从图片 → HTML 全流程 | pytest + mock(LLM) + real images | 验证一个完整的试卷输入能正确输出 HTML |
| **模块 — CV** | `cv/` 模块 | pytest + 真实扫描图片 | 框选准确率、预处理效果、预览图生成 |
| **单元 — Models** | `models/` 模块 | pytest | 模型构建、JSON 序列化、时间戳命名 |
| **契约 — Agent** | `agent/` LLM 调用 | pytest + mock(anthropic) | Prompt 构造、上下文传递、响应解析 |
| **UI — Web** | `web/` 模块 | pytest + httpx TestClient | 框选微调 API、不确定确认 API、页面加载 |
| **输出 — Renderer** | `renderer/` 输出 | pytest + 验证 HTML 结构 | LaTeX 嵌入、JSON 内嵌、模板填充 |

### Mock 策略

- 所有 LLM 调用通过 `unittest.mock.patch` 注入固定响应
- CV 模块不 mock（纯本地计算，用真实图片测试）
- 文件读写不 mock（用 `tmp_path` fixture 隔离）

### 测试文件结构

```
tests/
├── test_models.py          # 数据模型 + JSON 序列化
├── test_cv_engine.py       # CV 框选（需要测试图片 fixture）
├── test_agent.py           # Agent Core 基础功能
├── test_recognizer.py      # 多模态识别（含错题标记和圈划重点）
├── test_uncertainty.py     # 不确定区域精化
├── test_review.py          # 一致性审查
├── test_correction.py      # 错题修正解答生成
├── test_analyzer.py        # 跨卷薄弱点分析
├── test_web_ui.py          # Web UI API 端点
├── test_renderer.py        # HTML 渲染输出验证
├── test_cli.py             # CLI 子命令集成测试
└── test_e2e.py             # 端到端流程（mock LLM）
```

## Out of Scope

- **移动端 App**：当前为 CLI + Web UI，不开发 iOS / Android 客户端
- **在线多人协作**：无用户系统、无云端同步、无团队功能
- **自动批改评分**：识别错题标记（打叉/斜线）但不自主判断答案对错
- **视频/手写输入**：仅支持静态图片输入
- **非理科科目**：目前专注数学和物理，不扩展到语文/英语等文科
- **自动化知识点图谱**：不做知识图谱可视化，仅做列表和文本建议
- **公式手写识别**：不将手写公式转为 LaTeX（仅识别印刷公式）
- **直接 PDF 输入**：仅支持图片输入，不直接从 PDF 提取

## Further Notes

- 本工具的核心是 AI Agent，所有智力操作由 Agent 编排完成
- CV 部分是唯一不使用 LLM 的模块，保持纯传统算法
- "学霸笔记"skill 以 SKILL.md 工作流的形式被 Agent 调用执行，而非手动编码模板逻辑
- 所有 LLM API 调用统一走 Anthropic 兼容协议，便于切换不同模型提供商
- 数据完全本地存储，无外部数据库依赖
- 文件命名中的时间戳确保每个产物可追溯、可排序
