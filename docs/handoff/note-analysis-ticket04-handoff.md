# Handoff: 笔记分析工具 — Ticket 04 识别引擎

## 当前状态

**最近提交**: `66d92d2` — feat: Web UI 框选微调 (Ticket 03)
**分支**: `master`
**工作目录**: `F:\note_analysis\sourcecode\`

Ticket 03 已完成并提交。Web UI 框选微调模块已实现，55/55 测试通过，mypy/ruff 全 clean。

## 已引用但无需重复的内容

- **产品规格**: `docs/spec.md` — 完整 PRD
- **Ticket 03**: `docs/issues/03-Web-UI框选微调.md` — 需求清单
- **Ticket 04**: `docs/issues/04-识别引擎.md` — 下一步任务
- **Ticket 03 实现**: 提交 `66d92d2` — 含完整 diff
- **测试结果**: 55/55 通过，mypy/ruff 全 clean

## Ticket 03 完成总结

**新增文件:**
- `note_analysis/web/server.py` — FastAPI 临时 Web 服务器
  - `_find_free_port()`: 随机端口绑定
  - `_build_html(exam)`: 生成 Canvas 交互 HTML（嵌入 exam 数据）
  - `_create_app(exam, exam_dir)`: 创建 FastAPI 应用（4 个端点）
  - `run_server(exam_dir)`: 启动 uvicorn 服务 + 自动打开浏览器
  - 端点: `GET /`(HTML), `GET /api/exam`, `GET /api/photo/{index}`, `PUT /api/exam/boxes`, `POST /api/exam/done`
- `tests/test_web_ui.py` — 13 个测试（HTML 渲染、API、CLI 集成）

**修改文件:**
- `models/models.py`: `QuestionBox` 新增 `photoIndex: int = 0` 字段
- `cv/engine.py`: `process_exam` 设置 `photoIndex` 追踪框选区所属照片
- `cli.py`: `serve` 子命令调用 `run_server`

**代码审查发现（待修复，非阻塞）:**
- `tests/test_web_ui.py` 缺少 `from __future__ import annotations`（习惯问题）
- 关闭机制(`server.should_exit`)无测试覆盖
- `webbrowser.open()` 行为无测试覆盖
- `_build_html` 函数 ~300 行偏长，但作为嵌入式 HTML 模板的可接受取舍

## 待办 Ticket 顺序

| # | Ticket | 文件 | 阻塞 |
|---|--------|------|------|
| **04** | **识别引擎 (LLM)** | `note_analysis/agent/` | **03 已完成 → 可开始** |
| 05 | 不确定区域处理 | `note_analysis/agent/` + `web/` | 04 完成 |
| 06 | 合理性审查 | `note_analysis/agent/` | 05 完成 |
| 07 | HTML 渲染 | `note_analysis/renderer/` | 06 完成 |
| 08 | 跨卷薄弱点分析 | `note_analysis/analyzer/` | 07 完成 |

## 需注意的架构决策

1. **所有 LLM 调用走 Agent Core** — `agent/core.py` 的 `Agent` 类封装了 Anthropic `/v1/messages` 兼容协议的调用，集成时只需配置 `LLM_API_KEY` 和 `LLM_API_URL` 环境变量
2. **Skill 加载机制** — `Agent.load_skill()`/`execute_skill()` 从本地路径读取 SKILL.md 并按工作流执行（为 Ticket 07 使用`学霸笔记`skill 做准备）
3. **数据持久化** — 所有 JSON 文件按 `笔记_YYYYMMDD_HHmm.json` 统一命名，前缀常量 `NOTE_PREFIX` 在 `models/models.py` 中
4. **测试策略** — LLM 调用全部 mock（`unittest.mock.patch`），CV 模块用合成 numpy 图像测试，文件操作用 `tmp_path` fixture
5. **Web UI 的 `photoIndex`** — `QuestionBox.photoIndex` 标记框选区所属照片在 `exam.photos` 中的索引，Web UI 和 CV 引擎均已设置此字段
6. **关闭机制** — `POST /api/exam/done` 设置 `server.should_exit = True` 通知 uvicorn 关闭，但未经集成测试验证
7. **`cv/engine.py` 导入策略** — `process_exam` 内部延迟导入 `QuestionBox` 和 `Serializer` 以避免循环依赖；`cli.py` 内延迟导入 `CVEngine`/`run_server` 保持 CLI 启动速度

## 下一步（Ticket 04 — 识别引擎）

从 `sourcecode/` 目录开始，实现 LLM 识别引擎：

- 读取已框选的 JSON 文件
- 对每个 `QuestionBox` 区域，将照片裁剪子图 + bbox 传递给多模态 LLM
- LLM 需识别：黑色原题文字(含 LaTeX 公式)、红色笔记文字(含 LaTeX 公式)、原题中的图片
- 低置信度区域标记为 `UncertainRegion`
- 结果回填到 `QuestionBox.questionText`, `QuestionBox.annotations`, `QuestionBox.images`, `QuestionBox.uncertainRegions`
- 更新 JSON 文件

**API 协议细节**：Agent Core 使用 Anthropic Messages API (`/v1/messages`)，多模态调用需在 `content` 数组中包含 `image` 块（base64 编码），参考 `agent/core.py` 的 `call()` 和 `call_with_tool()` 方法。

**Prompt 设计要点**：
- 需区分黑字（原题）和红字（笔记）
- 数学/物理公式用 LaTeX 标记（`$...$` 或 `$$...$$`）
- 原题图片需标记位置并 base64 编码嵌入
- 置信度低于阈值的区域标记为不确定

**Mock 策略**：使用 `unittest.mock.patch('httpx.Client.post')` 模拟 LLM 响应，测试 prompt 构造和响应解析逻辑。

## Suggested Skills

下次会话（Ticket 04）应加载以下 skills：

- **test-driven-development** — 为识别引擎模块编写测试，先写测试后实现。特别是 prompt 构造、响应解析、图片裁剪逻辑。
- **claude-api** — 参考 Anthropic Messages API 的 `content` 块格式（特别是 `image` 类型块）、`max_tokens` 限制、视觉能力说明，确保多模态调用正确。
- **requesting-code-review** — 完成后请求代码审查。
