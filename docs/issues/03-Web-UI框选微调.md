# 03 — Web UI 框选微调

**What to build:** 启动一个本地临时 Web 服务，在浏览器中展示试卷扫描图，用户可拖拽/调整/增删每个大题 bbox。确认后保存回 JSON。用户跑 `python main.py serve <exam-dir>` 后自动打开浏览器，交互完成后关闭服务继续后续流程。

**Blocked by:** 02 — 框选引擎

**Status:** ready-for-agent

- [ ] FastAPI 临时 Web 服务器，随机端口绑定，自动打开浏览器
- [ ] 前端页面：加载试卷图片 + 已检测的 bbox，使用 Canvas 或交互式框选库（如 Fabric.js 或纯 Canvas）展示可拖拽调整的矩形框
- [ ] 操作支持：拖动已有 bbox、调整大小、新增框选区、删除框选区
- [ ] 确认按钮：点击后保存 bbox 坐标到 JSON，关闭服务器
- [ ] `serve` 子命令：接收试卷目录路径，启动 Web 服务

**Blocking:** 04 识别引擎
