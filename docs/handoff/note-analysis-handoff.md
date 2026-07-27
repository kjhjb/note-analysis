# Handoff: 笔记分析工具

## 当前状态

**最近提交**: `0a22e91` feat: CV 框选引擎与 box CLI 子命令 (Ticket 02)
**分支**: `master`
**工作目录**: `F:\note_analysis\sourcecode\`

Ticket 02 已完成。CV 框选引擎和 `box` 子命令已实现并提交。

## 已引用但无需重复的内容

- **产品规格**: `docs/spec.md`
- **Ticket 清单**: `docs/issues/02-框选引擎.md` 到 `docs/issues/08-*.md`
- **Ticket 01 实现**: 提交 `9669e84` — 项目骨架、Pydantic 模型、Agent 核心、CLI 入口
- **Ticket 02 实现**: 提交 `0a22e91` — 含完整 diff
- **测试结果**: 42/42 通过，ruff/mypy 全 clean

## Ticket 02 完成总结

**新增文件:**
- `note_analysis/cv/engine.py` — `CVEngine` 类
  - `preprocess()`: 灰度化 → 高斯模糊去噪 → OTSU 二值化 → 形态学开运算 → 基于 minAreaRect 的倾斜校正
  - `detect_boxes()`: 水平投影法 + 形态学闭运算 (3x15) 合并文字行，检测大题边界
  - `draw_preview()`: 在原图绘制红色 bbox 矩形框，保存 `*_bbox_preview.jpg`
  - `process_exam()`: 类方法，加载 JSON → 逐照片框选 → 更新 JSON → 生成预览图
- `tests/test_cv_engine.py` — 10 个测试（预处理、去噪、倾斜校正、多场景检测、预览）

**修改文件:**
- `cli.py`: `box` 子命令调用 `CVEngine.process_exam`，捕获 `FileNotFoundError`
- `tests/test_cli.py`: 4 个 box CLI 测试（无 JSON 报错、空白图、合成试卷、预览图生成）
- `pyproject.toml`: mypy/ruff 版本同步到 `py312`

**代码审查发现已修复:**
- 添加了倾斜校正步骤（`_deskew` 基于 minAreaRect）
- 无法读取的图片现在输出警告而非静默跳过
- pyproject.toml ruff target-version 与 mypy 一致

## 待办 Ticket 顺序

| # | Ticket | 文件 | 阻塞 |
|---|--------|------|------|
| **03** | **Web UI 框选微调** | `note_analysis/web/` | **02 已完成 → 可开始** |
| 04 | 识别引擎 (LLM) | `note_analysis/agent/` | 03 完成 |
| 05 | 不确定区域处理 | `note_analysis/agent/` + `web/` | 04 完成 |
| 06 | 合理性审查 | `note_analysis/agent/` | 05 完成 |
| 07 | HTML 渲染 | `note_analysis/renderer/` | 06 完成 |
| 08 | 跨卷薄弱点分析 | `note_analysis/analyzer/` | 07 完成 |

## 需注意的架构决策

1. **所有 LLM 调用走 Agent Core** — `agent/core.py` 的 `Agent` 类封装了 Anthropic `/v1/messages` 兼容协议的调用，集成时只需配置 `LLM_API_KEY` 和 `LLM_API_URL` 环境变量
2. **Skill 加载机制** — `Agent.load_skill()`/`execute_skill()` 从本地路径读取 SKILL.md 并按工作流执行（为 Ticket 07 使用`学霸笔记`skill 做准备）
3. **数据持久化** — 所有 JSON 文件按 `笔记_YYYYMMDD_HHmm.json` 统一命名，前缀常量 `NOTE_PREFIX` 在 `models/models.py` 中
4. **测试策略** — LLM 调用全部 mock（`unittest.mock.patch`），CV 模块用合成 numpy 图像测试，文件操作用 `tmp_path` fixture
5. **CV 模块测试图片** — `test_cv_engine.py` 用 `_make_synthetic_exam()` 和 `_make_synthetic_exam_no_gaps()` 动态生成测试图像，无需外部 fixture 文件
6. **cv/engine.py 导入策略** — `process_exam` 内部延迟导入 `QuestionBox` 和 `Serializer` 以避免循环依赖；`cli.py` 内延迟导入 `CVEngine` 保持 CLI 启动速度

## 下一步（Ticket 03 — Web UI 框选微调）

从 `sourcecode/` 目录开始，实现 `web/` 模块：

- FastAPI 临时 Web 服务器，随机端口绑定，自动打开浏览器
- 前端页面：加载试卷图片 + 已检测的 bbox，Canvas 或 Fabric.js 展示可拖拽矩形框
- 操作支持：拖动、调整大小、新增、删除框选区
- 确认按钮：保存 bbox 坐标到 JSON，关闭服务器
- `cli.py` 中 `serve` 子命令已预留接口

### Web 模块开发要点

- `web/` 模块目前仅有空 `__init__.py`，需新建 `web/server.py` 等文件
- 前端为原生 HTML/JS（无额外前端框架），Canvas 交互
- FastAPI + Jinja2 模板或直接返回 HTML
- 框选结果通过 API 回写到 JSON，复用 `Serializer` 和 `Exam`/`QuestionBox` 模型
- 测试用 `httpx.AsyncClient`（FastAPI TestClient）

## Suggested Skills

下次会话应加载以下 skills：

- **test-driven-development** — 为 Web UI 模块编写测试，先写测试后实现
- **brainstorming** — 在开始编码前讨论前端框架选择（Canvas vs Fabric.js）、API 设计、交互流程
- **requesting-code-review** — 完成后请求代码审查
