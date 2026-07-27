# Handoff: 笔记分析工具 — 准备开始 Ticket 07

## 当前状态

**最近提交**: `95cc8fd` — feat: 合理性审查 (Ticket 06)
**分支**: `master`
**工作目录**: `F:\note_analysis\sourcecode\`
**测试**: 138/138 通过, mypy/ruff 全 clean

## 本会话（Ticket 06）完成内容

实现了合理性审查全流程，详见提交 `95cc8fd`。

### 新增文件
- `note_analysis/agent/review.py` — `Reviewer` 类（~100 行），编排审查全流程
- `tests/test_review.py` — 27 个测试（~300 行）

### 修改文件
- `note_analysis/cli.py` — `review` 子命令从 stub 替换为实际逻辑，增加 `ValueError` 捕获
- `note_analysis/agent/__init__.py` — 导出 `Reviewer`
- `note_analysis/models/models.py` — `reviewStatus` Literal 增加 `"uncertain"`（修复代码审查发现的数据损坏 bug）
- `tests/test_cli.py` — 新增 2 个 CLI review 测试

### 审查流程

```
Reviewer.review()
  → _load_exam(): 加载 JSON
  → _build_prompt(): 构造含原题/笔记/不确定区域的审查 prompt
  → _call_llm(): 调用 LLM 判断逻辑一致性
  → _parse_response(): 解析返回的 reviews JSON
  → _update_exam(): 更新 reviewStatus/reviewNotes
  → Serializer.save(): 写回 JSON
```

### 代码审查修复项
- **`reviewStatus` Literal 缺 `"uncertain"`**: 模型定义只有 `"pending"`/`"consistent"`/`"inconsistent"`，但 LLM 被要求返回 `"uncertain"`，写 JSON 可保存，读 JSON 时 Pydantic `model_validate` 会抛 `ValidationError`。已加 `"uncertain"` 修复。
- **CLI 缺少 `ValueError` 捕获**: `review` 命令的 `try` 只捕获 `FileNotFoundError`，LLM 解析失败会裸奔 traceback。已加 `except ValueError`。
- **冗余 import**: `cli.py` 中 `Serializer` 已在顶层 import，函数体内又重复 import。已移除。

### 未修复的审查意见（可改进项）
- CLI `review` 命令双重加载 JSON（先检查 `all_confirmed()`，`Reviewer` 又加载一次）
- `_update_exam` 中的 `for box in exam.boxes: if box.id != box_id: continue` 循环模式在 `UncertaintyResolver` 中重复出现 3 处，可提取 `_find_box()` 辅助函数
- `(box_id, ur_index)` 数据对在 5 处出现但未封装为独立类型

## 已引用但无需重复的内容

| 内容 | 位置 |
|------|------|
| 产品规格 (PRD) | `docs/spec.md` |
| Ticket 06 — 合理性审查 | `docs/issues/06-合理性审查.md` |
| Ticket 07 — HTML 渲染 | `docs/issues/07-HTML渲染引擎.md` |
| Ticket 08 — 跨卷分析 | `docs/issues/08-多试卷累积与薄弱点分析.md` |
| Ticket 05 Handoff | `docs/handoff/note-analysis-ticket05-handoff.md` |
| Ticket 06 提交 diff | `git show 95cc8fd` |
| 数据模型定义 | `note_analysis/models/models.py` |
| Agent Core | `note_analysis/agent/core.py` |
| 审查引擎实现 | `note_analysis/agent/review.py` |
| 学霸笔记 SKILL.md | `C:\Users\liang\.config\opencode\skills\note-skill-main\SKILL.md` |
| 学霸笔记模板 | `C:\Users\liang\.config\opencode\skills\note-skill-main\assets\template.html` |
| 学霸笔记布局参考 | `C:\Users\liang\.config\opencode\skills\note-skill-main\references\layouts.md` |
| 学霸笔记组件参考 | `C:\Users\liang\.config\opencode\skills\note-skill-main\references\components.md` |
| 学霸笔记检查清单 | `C:\Users\liang\.config\opencode\skills\note-skill-main\references\checklist.md` |

## 架构决策（本会话新增）

1. **审查不需要多模态调用** — `Reviewer` 区别于 `Recognizer` 和 `UncertaintyResolver`，无需传入图片。仅发送文本 prompt（原题文字 + 笔记文字 + 不确定区域信息），减少 token 消耗并简化实现。
2. **`uncertain` 状态合法性** — `reviewStatus` 的四个有效值 `pending`/`consistent`/`inconsistent`/`uncertain` 均在模型 `Literal` 中声明，确保 JSON 序列化/反序列化安全。LLM 被要求优先返回 `consistent` 或 `inconsistent`，仅在完全无法判断时使用 `uncertain`。
3. **Reviewer 复用 Agent 模式** — 与 `Recognizer`、`UncertaintyResolver` 保持一致的构造模式：接收 `exam_dir` + 可选 `agent`，调用后 `pop_message()` 保持上下文干净。

## 待办 Ticket 顺序

| # | Ticket | 文件 | 阻塞 |
|---|--------|------|------|
| 06 | 合理性审查 | `note_analysis/agent/` | ✅ 完成 |
| **07** | **HTML 渲染** | `note_analysis/renderer/` | **← 下一步** |
| 08 | 跨卷薄弱点分析 | `note_analysis/analyzer/` | 07 完成 |

## 下一步（Ticket 07 — HTML 渲染引擎）

从 `sourcecode/` 开始，工作内容：

1. **Agent 加载学霸笔记 SKILL.md** — 通过 `agent.load_skill()` 或 `execute_skill()` 读取并执行 skill 工作流
2. **需求澄清阶段** — 根据 JSON 数据自动判断内容类型（数学/物理笔记），选择 Style A（学霸笔记本风格）
3. **拷贝模板阶段** — 读取 `C:\Users\liang\.config\opencode\skills\note-skill-main\assets\template.html` 作为基底
4. **填充内容阶段** — 参考 `references/layouts.md` 的 18 种布局，将 JSON 中的 `questionText`（黑字原题）、`annotations`（红字笔记）映射到合适布局组件
5. **公式渲染** — LaTeX 公式用 MathJax/KaTeX 渲染，原题图片（`box.images` 中 base64）内嵌 `<img>`
6. **数据嵌入** — 在 HTML `<script>` 标签中嵌入完整试卷 JSON（供后续分析）
7. **自检阶段** — 按 `references/checklist.md` 逐项自查
8. **输出** — 按 `笔记_YYYYMMDD_HHmm.html` 格式写出

需要注意的点：
- `renderer/` 目录目前仅有空 `__init__.py`，需要新建渲染模块
- Agent 的 `execute_skill()` 方法（`agent/core.py:100-109`）可一次性执行整个 skill 工作流，也可分步调用的 `load_skill()` 分段执行
- `Exam.html_filename` 属性（`models/models.py:55-56`）已定义好输出文件名格式
- 模板路径引用建议用绝对路径或配置化的 skill 路径，避免工作目录敏感
- 渲染完成后可自动在浏览器中打开预览（参考 `serve` 命令的 `webbrowser.open` 模式）

## Suggested Skills

下次会话应加载以下 skills：

- **学霸笔记** — Ticket 07 的核心 skill。加载 SKILL.md 后严格按工作流执行：需求澄清 → 拷贝模板 → 填充内容 → 自检 → 预览 → 迭代。Agent 应遵循 skill 指令而非手动编码模板逻辑。
- **test-driven-development** — 为渲染引擎编写测试，先写测试后实现。重点测试：模板填充、LaTeX 嵌入、JSON 内嵌、文件命名。
- **claude-api** — 在构建渲染 prompt 和调用 `execute_skill()` 时参考 Anthropic Messages API 格式，尤其是 system prompt 和 tool use 的交互方式。
- **frontend-design** — 参考此 skill 进行渲染输出的视觉设计指导，特别是手写笔记本风格的美学方向。
- **verification-before-completion** — HTML 渲染涉及文件输出，在声称完成前必须验证输出文件存在、内容正确、格式有效。
- **requesting-code-review** — 完成后请求代码审查。