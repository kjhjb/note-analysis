# Handoff: 笔记分析工具 — 准备开始 Ticket 05

## 当前状态

**最近提交**: `9b90b31` — feat: 识别引擎 LLM 多模态识别 (Ticket 04)
**分支**: `master`
**工作目录**: `F:\note_analysis\sourcecode\`
**测试**: 75/75 通过, mypy/ruff 全 clean

## 本会话（Ticket 04）完成内容

实现了多模态 LLM 识别引擎，见提交 `9b90b31`。

### 新增文件
- `note_analysis/agent/recognizer.py` — `Recognizer` 类，编排识别全流程
- `tests/test_recognizer.py` — 20 个测试（裁剪、编码、Prompt 构造、响应解析、全流程 mock）

### 修改文件
- `agent/core.py` — `_messages` 类型放宽为 `list[dict[str, Any]]`，新增 `add_message_blocks()` 公有 API 支持多模态 content
- `agent/__init__.py` — 导出 `Recognizer`
- `cli.py` — `recognize` 子命令实现，支持 `--threshold` 参数

### 识别流程
```
Recognizer.recognize()
  → Serializer.find_exam_files() + load()
  → _prepare_boxes_data(): 根据 photoIndex + bbox 裁剪各框选区图片，base64 编码
  → _build_multimodal_content(): 构建一次 LLM 调用的 content 数组（全部框选区的图片+位置描述）
  → _call_llm(): 通过 agent.add_message_blocks() 发送多模态请求
  → _parse_response(): 正则提取 JSON，处理 markdown 包裹
  → _update_exam(): 回填 questionText / annotations / images(base64) / uncertainRegions
  → Serializer.save() 写回 JSON
```

### Prompt 核心要求（`SYSTEM_PROMPT` 常量）
- 区分黑色印刷文字（questionText）与红色手写笔记（annotations）
- 公式用 LaTeX 标记（`$...$` 行内，`$$...$$` 独立）
- 每区域输出置信度评分（0~1）
- 置信度低于 0.8 的区域标记为 `uncertainRegions`
- `uncertainRegions` bbox 坐标相对于裁剪图片

### 代码审查修复项
- **threshold 传递 bug**: `_update_exam` 原是 `@staticmethod`，调用时未传 `self.threshold`，导致 `--threshold` CLI 参数无效。已改为实例方法，直接使用 `self.threshold`
- **封装违规**: `_call_llm` 原直接访问 `agent._messages`，已改为通过新公有 API `agent.add_message_blocks()` 操作
- **类型简化**: `boxes_data` 参数移除 `| None`（始终传真实 list）

### 未修复的审查意见（可改进项）
- Prompt 中框选区位置描述仅包含原始像素坐标，未包含相对关系描述（如"第2题在第1题下方"）
- `_prepare_boxes_data` 对 `Exam` 数据的访问边界可进一步收紧（Feature Envy 轻微气味）

## 已引用但无需重复的内容

以下文件记录了完整的产品规格、架构决策和需求，handoff 不再复述：

| 内容 | 位置 |
|------|------|
| 产品规格 (PRD) | `docs/spec.md` |
| Ticket 01 — 项目骨架 | `docs/issues/01-项目骨架.md` |
| Ticket 02 — CV 框选 | `docs/issues/02-CV框选引擎.md` |
| Ticket 03 — Web UI 微调 | `docs/issues/03-Web-UI框选微调.md` |
| Ticket 04 — 识别引擎 | `docs/issues/04-识别引擎.md` |
| Ticket 05 — 不确定区域处理 | `docs/issues/05-不确定区域处理.md` |
| Ticket 06 — 合理性审查 | `docs/issues/06-合理性审查.md`（如存在） |
| Ticket 07 — HTML 渲染 | `docs/issues/07-HTML渲染.md`（如存在） |
| Ticket 08 — 跨卷分析 | `docs/issues/08-跨卷薄弱点分析.md`（如存在） |
| Ticket 03 Handoff | `docs/handoff/note-analysis-ticket04-handoff.md` |
| 数据模型定义 | `note_analysis/models/models.py` |
| Agent Core | `note_analysis/agent/core.py` |
| 识别引擎实现 | `note_analysis/agent/recognizer.py` |
| 提交 diff | `git show 9b90b31` |

## 架构决策（本会话新增）

1. **多模态 content 构造方式** — Recognizer 直接构造 Anthropic API 的 `content` 数组（`text` + `image` 块），通过 `agent.add_message_blocks("user", content)` 发送，而非逐个调用 `add_message()`。调用后 `pop()` 消息保持 Agent 上下文干净。
2. **框选区图片存储** — 每个 `QuestionBox.images` 存储的是该框选区裁剪图的 base64 JPEG 编码，而非原题中独立图片的提取。渲染时可直接嵌入 `<img>` 标签。
3. **不确定区域坐标系** — `UncertainRegion.bbox` 坐标相对于裁剪后的框选区图片（而非原始试卷照片），与 Web UI 中显示缩略图时的坐标系统一致。
4. **模块依赖** — `Recognizer` 直接依赖 `cv2` 做图片裁剪和编码，无中间抽象层。如需换用 PIL 或其他库需改 `crop_bbox_from_image` 和 `image_to_base64` 两个独立函数。

## 待办 Ticket 顺序

| # | Ticket | 文件 | 阻塞 |
|---|--------|------|------|
| **05** | **不确定区域处理** | `note_analysis/agent/` + `web/` | **← 下一步** |
| 06 | 合理性审查 | `note_analysis/agent/` | 05 完成 |
| 07 | HTML 渲染 | `note_analysis/renderer/` | 06 完成 |
| 08 | 跨卷薄弱点分析 | `note_analysis/analyzer/` | 07 完成 |

## 下一步（Ticket 05 — 不确定区域处理）

从 `sourcecode/` 开始，工作内容：

1. **Agent 调用 LLM** 对每个 `UncertainRegion` 的裁剪区域生成更精确的文本猜测（可复用 `crop_bbox_from_image` 对原始照片裁剪不确定区域子图）
2. **扩展 Web UI**：在现有 `web/server.py` 中添加新页面/端点，展示所有不确定区域：
   - 裁剪缩略图
   - LLM 原始猜测文本
   - 三个操作按钮："接受猜测" / "输入正确文本" / "忽略"
3. **更新 JSON**：用户确认后填充 `UncertainRegion.userConfirmed` 字段
4. **全确认后解锁**：所有不确定区域确认后方可进入 Ticket 06

需要注意的点：
- `UncertainRegion.bbox` 坐标相对于框选区裁剪图片（Ticket 04 的约定），在原始照片上裁剪子图时需要转换为原始照片坐标：`orig_x = box.bbox.x + ur.bbox.x`，`orig_y = box.bbox.y + ur.bbox.y`
- 已有 `UncertainRegion` 模型包含 `llmGuess`（LLM 原始猜测）和 `userConfirmed`（用户确认后填充），无需修改模型
- `web/server.py` 中的 `_build_html` 函数已约 300 行，建议新增页面而不是继续膨胀

## Suggested Skills

下次会话应加载以下 skills：

- **test-driven-development** — 为不确定区域处理编写测试，先写测试后实现。特别是 LLM 猜测调用、Web UI 新端点、用户交互逻辑。
- **claude-api** — 参考 Anthropic Messages API 的 content 块格式，确保对不确定区域裁剪图片的多模态调用正确。
- **frontend-design** — 如果需要在 Web UI 中添加新的不确定区域确认页面，参考此 skill 进行视觉设计，保持与现有框选微调页面风格一致。
- **systematic-debugging** — Ticket 05 涉及 Web UI + Agent + 图片裁剪多层交互，出现问题时使用此 skill 进行系统化调试。
- **requesting-code-review** — 完成后请求代码审查。
