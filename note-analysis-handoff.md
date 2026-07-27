# Handoff: 笔记分析工具 — 进入实现阶段

## 项目摘要

一个 Python CLI + AI Agent 工具，帮助高中学生整理理科试卷：
拍照(单/多张) → CV框选大题 → Web UI微调 → LLM识别(黑字原题/红字笔记/公式)
→ 不确定区域确认 → 合理性审查 → 学霸笔记风格HTML渲染 → 跨卷薄弱点分析

数据全本地存储（JSON），LLM 调用使用 Anthropic 兼容协议。

## 已完成的工作

| 阶段 | 产物 | 位置 |
|------|------|------|
| Domain Modeling | CONTEXT.md — 领域术语表 | `F:\note_analysis\CONTEXT.md` |
| Grilling | 完整的决策树（8 轮对话已确认全部决策） | 见当前会话历史 |
| To Spec | spec.md — 完整的产品规格说明书 | `.scratch\note-analysis\spec.md` |
| To Tickets | 8 张 tracer-bullet ticket | `.scratch\note-analysis\issues\01-*.md` ～ `08-*.md` |

## 关键决策摘要

- **语言**：Python 3.11+
- **CLI 框架**：click
- **LLM 协议**：Anthropic Messages API 兼容（`/v1/messages`）
- **LLM 调用**：统一由 Agent Core 编排（Ticket 01 构建此框架）
- **CV 框选**：纯 OpenCV，不使用 LLM（Ticket 02）
- **Web UI**：FastAPI + 原生 HTML/JS（Ticket 03）
- **渲染**：调用学霸笔记 skill 的 SKILL.md 工作流（Ticket 07）
- **数据模型**：Pydantic（Exam → QuestionBox → UncertainRegion → WeakPoint）
- **文件命名**：`笔记_YYYYMMDD_HHmm.{json,html}`
- **颜色**：仅红/黑（红色大类，非纯色）
- **用户体系**：无登录，纯本地

## 下一个工作 — Ticket 01：项目骨架与核心数据模型

**文件**：`.scratch\note-analysis\issues\01-项目骨架与核心数据模型.md`

**交付物**：
- pyproject.toml / requirements.txt
- Pydantic 数据模型（Exam, QuestionBox, UncertainRegion, WeakPoint, BBox）
- JSON 序列化/反序列化（时间戳命名）
- AI Agent 编排层（LLM 调用管理器 + Anthropic 兼容客户端 + Skill 加载能力）
- CLI 入口（click 子命令：init, box, serve, recognize, review, render, analyze）
- `init` 子命令（扫描目录生成初始 JSON 骨架）
- 测试基础结构（pytest, tmp_path fixtures）

**依赖**：无（可立即开始）

### 测试 seam 参考

来自 spec.md 的测试分层：
- **单元**：`tests/test_models.py` — Pydantic 构建、JSON 序列化
- **契约**：`tests/test_agent_prompt.py` — mock Anthropic 客户端验证 Prompt 构造
- E2E 等其他测试在后续 tickets 中添加

## 建议启动命令

```powershell
# 在项目根目录执行
cd F:\note_analysis
pip install -r requirements.txt
python -m pytest tests/  # 验证骨架
```

## 建议 Skills

- `/implement` — 执行 Ticket 01 的标准实现流程，内部驱动 TDD
- `/tdd` — 测试驱动开发，先写测试再实现（适合数据模型和 Agent 框架）
- `/codebase-design` — 设计 Agent 编排层的模块接口（deep module 原则）
- `/code-review` — Ticket 01 完成后做 Standards + Spec 双轴审查

## 项目目录结构

```
F:\note_analysis/
├── CONTEXT.md                         ← 领域术语表（已锁定）
├── .scratch/note-analysis/
│   ├── spec.md                        ← 完整 PRD
│   └── issues/
│       ├── 01-项目骨架与核心数据模型.md   ← 下一个
│       ├── 02-框选引擎.md
│       ├── 03-Web-UI框选微调.md
│       ├── 04-识别引擎.md
│       ├── 05-不确定区域处理.md
│       ├── 06-合理性审查.md
│       ├── 07-HTML渲染引擎.md
│       └── 08-多试卷累积与薄弱点分析.md
├── note-skill-temp/note-skill-main/   ← 学霸笔记 skill 模板引擎
└── docs/adr/                          ← ADR 目录（空）
```
