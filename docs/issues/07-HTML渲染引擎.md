# 07 — HTML 渲染引擎

**What to build:** AI Agent 加载"学霸笔记"skill（`note-skill-main/SKILL.md`），按 skill 定义的完整工作流执行渲染：Agent 读取 SKILL.md 理解需求 → 读取 template.html 和 layouts.md 选择布局 → 将经审查的最终数据填入模板 → 按 checklists.md 自检 → 输出 `笔记_YYYYMMDD_HHmm.html`。渲染时嵌入 MathJax/KaTeX 渲染 LaTeX 公式，原题图片 base64 内嵌，完整 JSON 数据嵌入 HTML 供后续分析。用户跑 `python main.py render <exam-dir>` 触发 Agent 执行整个 skill 工作流。

**Blocked by:** 06 — 合理性审查

**Status:** ready-for-agent

- [ ] Agent 加载 SKILL.md：读取工作流定义（需求澄清 → 拷贝模板 → 填充内容 → 自检 → 预览 → 迭代），按 step-by-step 执行
- [ ] 需求澄清阶段：Agent 根据已有 JSON 数据自动判断内容类型（数学/物理笔记），选择 Style A（学霸笔记本风格）
- [ ] 拷贝模板阶段：Agent 读取 `assets/template.html` 作为基底
- [ ] 填充内容阶段：Agent 参考 `references/layouts.md` 中的 18 种布局，将 JSON 中的 `questionText`（黑字原题）、`annotations`（红字笔记）映射到合适的布局组件（标准段落、对比框、便签旁注等）
- [ ] 公式图片处理：LaTeX 公式用 MathJax/KaTeX 渲染，原题图片转 base64 嵌入 `<img>`
- [ ] 数据嵌入：在 HTML `<script>` 标签中嵌入完整试卷 JSON（供累积分析）
- [ ] 自检阶段：Agent 按 `references/checklist.md` 逐项自查（P0：title 标签、禁止 emoji、内容完整等）
- [ ] 输出文件：按 `笔记_YYYYMMDD_HHmm.html` 格式写出，Agent 确认生成成功

**Blocking:** 08 多试卷累积与薄弱点分析
