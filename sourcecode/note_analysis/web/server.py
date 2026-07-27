from __future__ import annotations

import json
import socket
import sys
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from note_analysis.models.models import Exam, QuestionBox
from note_analysis.models.serializer import Serializer


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _build_html(exam: Exam) -> str:
    photos_json = json.dumps(exam.photos, ensure_ascii=False)
    boxes_json = json.dumps([b.model_dump() for b in exam.boxes], ensure_ascii=False)
    photo_count = len(exam.photos)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>框选微调 - 笔记分析工具</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f5f5; color:#333; }}
#app {{ max-width:1200px; margin:0 auto; padding:16px; }}
h1 {{ font-size:20px; margin-bottom:12px; }}
#toolbar {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }}
#toolbar button {{ padding:6px 14px; border:1px solid #ccc; border-radius:4px; background:#fff; }}
#toolbar button {{ font-size:14px; cursor:pointer; }}
#toolbar button:hover {{ background:#e8e8e8; }}
#toolbar button.primary {{ background:#1890ff; color:#fff; border-color:#1890ff; }}
#toolbar button.primary:hover {{ background:#40a9ff; }}
#toolbar button.danger {{ color:#ff4d4f; border-color:#ff4d4f; }}
#toolbar button.danger:hover {{ background:#fff2f0; }}
#photoInfo {{ font-size:14px; color:#666; margin:0 8px; }}
#canvasContainer {{ position:relative; border:1px solid #ddd; background:#fff; overflow:hidden; cursor:default; }}
#canvas {{ display:block; }}
#info {{ margin-top:8px; font-size:13px; color:#888; text-align:center; }}
</style>
</head>
<body>
<div id="app">
<h1>框选微调</h1>
<div id="toolbar">
<button id="prevBtn">&#9664; 上一张</button>
<span id="photoInfo">1 / {photo_count}</span>
<button id="nextBtn">下一张 &#9654;</button>
<span style="flex:1"></span>
<button id="addBtn">+ 添加框</button>
<button id="delBtn" class="danger">- 删除框</button>
<button id="doneBtn" class="primary">&#10003; 确认并保存</button>
</div>
<div id="canvasContainer">
<canvas id="canvas"></canvas>
</div>
<div id="info">拖拽框移动 · 拖拽角调整大小 · 点击选中 · Delete 键删除</div>
</div>
<script>
(function() {{
const PHOTOS = {photos_json};
const ALL_BOXES = {boxes_json};

const state = {{
  photos: PHOTOS,
  allBoxes: ALL_BOXES,
  currentPhotoIndex: 0,
  selectedBoxId: null,
  isDragging: false,
  isResizing: false,
  dragStartX: 0,
  dragStartY: 0,
  dragOrigBox: null,
  resizeCorner: null,
  image: null,
  scale: 1,
  nextId: (ALL_BOXES.length > 0 ? Math.max(...ALL_BOXES.map(b=>b.id)) : 0) + 1,
}};

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('canvasContainer');
const photoInfo = document.getElementById('photoInfo');

function getCurrentBoxes() {{
  return state.allBoxes.filter(b => b.photoIndex === state.currentPhotoIndex);
}}

function getImageSrc(index) {{
  return `/api/photo/${{index}}`;
}}

function loadPhoto(index) {{
  if (index < 0 || index >= state.photos.length) return;
  state.currentPhotoIndex = index;
  const img = new Image();
  img.onload = function() {{
    state.image = img;
    fitAndRender();
  }};
  img.src = getImageSrc(index);
  photoInfo.textContent = `${{index + 1}} / ${{state.photos.length}}`;
  state.selectedBoxId = null;
}}

function fitAndRender() {{
  const cw = container.clientWidth - 4;
  const ch = Math.min(window.innerHeight * 0.7, 800);
  container.style.height = ch + 'px';
  const sx = (cw - 10) / state.image.width;
  const sy = (ch - 10) / state.image.height;
  state.scale = Math.min(sx, sy, 1);
  canvas.width = Math.round(state.image.width * state.scale);
  canvas.height = Math.round(state.image.height * state.scale);
  render();
}}

function render() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(state.image, 0, 0, canvas.width, canvas.height);
  const boxes = getCurrentBoxes();
  for (const box of boxes) {{
    const x = box.bbox.x * state.scale;
    const y = box.bbox.y * state.scale;
    const w = box.bbox.w * state.scale;
    const h = box.bbox.h * state.scale;
    const sel = box.id === state.selectedBoxId;
    ctx.strokeStyle = sel ? '#ff4d4f' : '#1890ff';
    ctx.lineWidth = sel ? 3 : 2;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = sel ? 'rgba(255,77,79,0.1)' : 'rgba(24,144,255,0.08)';
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = sel ? '#ff4d4f' : '#1890ff';
    ctx.font = '12px sans-serif';
    ctx.fillText('#' + box.id, x + 4, y + 14);
    if (sel) {{
      const hs = 8;
      ctx.fillStyle = '#ff4d4f';
      const corners = [[x,y],[x+w,y],[x,y+h],[x+w,y+h]];
      for (const [cx,cy] of corners) {{
        ctx.fillRect(cx-hs/2, cy-hs/2, hs, hs);
      }}
    }}
  }}
}}

function screenToImg(sx, sy) {{
  return {{ x: sx / state.scale, y: sy / state.scale }};
}}

function hitTest(sx, sy) {{
  const boxes = getCurrentBoxes();
  for (const box of boxes) {{
    const bx = box.bbox.x * state.scale;
    const by = box.bbox.y * state.scale;
    const bw = box.bbox.w * state.scale;
    const bh = box.bbox.h * state.scale;
    if (sx >= bx && sx <= bx+bw && sy >= by && sy <= by+bh) {{
      return box;
    }}
  }}
  return null;
}}

function cornerHit(sx, sy) {{
  if (state.selectedBoxId === null) return null;
  const box = state.allBoxes.find(b => b.id === state.selectedBoxId);
  if (!box) return null;
  const hs = 10;
  const bx = box.bbox.x * state.scale;
  const by = box.bbox.y * state.scale;
  const bw = box.bbox.w * state.scale;
  const bh = box.bbox.h * state.scale;
  const corners = [['nw',bx,by],['ne',bx+bw,by],['sw',bx,by+bh],['se',bx+bw,by+bh]];
  for (const [name, cx, cy] of corners) {{
    if (Math.abs(sx-cx) < hs && Math.abs(sy-cy) < hs) return name;
  }}
  return null;
}}

canvas.addEventListener('mousedown', function(e) {{
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left;
  const sy = e.clientY - rect.top;
  const corner = cornerHit(sx, sy);
  if (corner) {{
    state.isResizing = true;
    state.resizeCorner = corner;
    state.dragStartX = sx;
    state.dragStartY = sy;
    const box = state.allBoxes.find(b => b.id === state.selectedBoxId);
    state.dragOrigBox = {{ ...box.bbox }};
    return;
  }}
  const hit = hitTest(sx, sy);
  if (hit) {{
    state.selectedBoxId = hit.id;
    state.isDragging = true;
    state.dragStartX = sx;
    state.dragStartY = sy;
    state.dragOrigBox = {{ ...hit.bbox }};
    render();
  }} else {{
    state.selectedBoxId = null;
    render();
  }}
}});

canvas.addEventListener('mousemove', function(e) {{
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left;
  const sy = e.clientY - rect.top;
  if (state.isDragging && state.selectedBoxId !== null) {{
    const box = state.allBoxes.find(b => b.id === state.selectedBoxId);
    if (!box) return;
    const dx = (sx - state.dragStartX) / state.scale;
    const dy = (sy - state.dragStartY) / state.scale;
    box.bbox.x = state.dragOrigBox.x + dx;
    box.bbox.y = state.dragOrigBox.y + dy;
    render();
  }} else if (state.isResizing && state.selectedBoxId !== null) {{
    const box = state.allBoxes.find(b => b.id === state.selectedBoxId);
    if (!box) return;
    const dx = (sx - state.dragStartX) / state.scale;
    const dy = (sy - state.dragStartY) / state.scale;
    let {{ x, y, w, h }} = state.dragOrigBox;
    if (state.resizeCorner.includes('e')) {{ w = Math.max(20, w + dx); }}
    if (state.resizeCorner.includes('w')) {{ x = x + dx; w = Math.max(20, w - dx); }}
    if (state.resizeCorner.includes('s')) {{ h = Math.max(20, h + dy); }}
    if (state.resizeCorner.includes('n')) {{ y = y + dy; h = Math.max(20, h - dy); }}
    if (w < 20) w = 20;
    if (h < 20) h = 20;
    box.bbox.x = x;
    box.bbox.y = y;
    box.bbox.w = w;
    box.bbox.h = h;
    state.dragStartX = sx;
    state.dragStartY = sy;
    state.dragOrigBox = {{ ...box.bbox }};
    render();
  }}
}});

window.addEventListener('mouseup', function() {{
  state.isDragging = false;
  state.isResizing = false;
}});

document.getElementById('prevBtn').addEventListener('click', function() {{
  if (state.currentPhotoIndex > 0) loadPhoto(state.currentPhotoIndex - 1);
}});

document.getElementById('nextBtn').addEventListener('click', function() {{
  if (state.currentPhotoIndex < state.photos.length - 1) loadPhoto(state.currentPhotoIndex + 1);
}});

document.getElementById('addBtn').addEventListener('click', function() {{
  if (!state.image) return;
  const iw = state.image.width;
  const ih = state.image.height;
  const bw = Math.min(200, iw * 0.5);
  const bh = Math.min(80, ih * 0.2);
  const newBox = {{
    id: state.nextId++,
    bbox: {{ x: (iw-bw)/2, y: (ih-bh)/2, w: bw, h: bh }},
    photoIndex: state.currentPhotoIndex,
    questionText: '',
    annotations: '',
    images: [],
    uncertainRegions: [],
    reviewStatus: 'pending',
    reviewNotes: '',
  }};
  state.allBoxes.push(newBox);
  state.selectedBoxId = newBox.id;
  render();
}});

document.getElementById('delBtn').addEventListener('click', function() {{
  if (state.selectedBoxId === null) return;
  state.allBoxes = state.allBoxes.filter(b => b.id !== state.selectedBoxId);
  state.selectedBoxId = null;
  render();
}});

document.addEventListener('keydown', function(e) {{
  if (e.key === 'Delete' || e.key === 'Backspace') {{
    if (state.selectedBoxId !== null) {{
      e.preventDefault();
      state.allBoxes = state.allBoxes.filter(b => b.id !== state.selectedBoxId);
      state.selectedBoxId = null;
      render();
    }}
  }}
}});

document.getElementById('doneBtn').addEventListener('click', async function() {{
  const doneBtn = document.getElementById('doneBtn');
  doneBtn.disabled = true;
  doneBtn.textContent = '保存中...';
  try {{
    const res = await fetch('/api/exam/boxes', {{
      method: 'PUT',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ boxes: state.allBoxes }}),
    }});
    if (!res.ok) throw new Error('保存失败');
    await fetch('/api/exam/done', {{ method: 'POST' }});
    doneBtn.textContent = '已保存，关闭页面...';
  }} catch (err) {{
    doneBtn.textContent = '保存失败，请重试';
    doneBtn.disabled = false;
  }}
}});

loadPhoto(0);
window.addEventListener('resize', function() {{ if (state.image) fitAndRender(); }});
}})();
</script>
</body>
</html>"""


def _create_app(exam: Exam, exam_dir: Path) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _build_html(exam)

    @app.get("/api/exam")
    async def get_exam() -> dict[str, Any]:
        return exam.model_dump()

    @app.get("/api/photo/{index}")
    async def get_photo(index: int) -> FileResponse:
        if 0 <= index < len(exam.photos):
            return FileResponse(exam.photos[index])
        raise HTTPException(status_code=404, detail="Photo not found")

    @app.put("/api/exam/boxes")
    async def update_boxes(data: dict[str, Any]) -> dict[str, str]:
        boxes_data = data.get("boxes", [])
        exam.boxes = []
        for b in boxes_data:
            if "bbox" not in b:
                raise HTTPException(status_code=422, detail="Each box must have a bbox field")
            exam.boxes.append(QuestionBox(**b))
        Serializer.save(exam, exam_dir)
        return {"status": "ok"}

    @app.post("/api/exam/done")
    async def done(request: Request) -> dict[str, str]:
        Serializer.save(exam, exam_dir)
        server = getattr(request.app.state, "_server", None)
        if server is not None:
            server.should_exit = True
        return {"status": "ok"}

    return app


def run_server(exam_dir: str | Path) -> None:
    exam_dir = Path(exam_dir)
    json_files = Serializer.find_exam_files(exam_dir)
    if not json_files:
        print(f"错误: 未找到 JSON 文件: {exam_dir}", file=sys.stderr)
        sys.exit(1)

    exam = Serializer.load(json_files[0])
    app = _create_app(exam, exam_dir)
    port = _find_free_port()

    print(f"启动 Web UI: http://127.0.0.1:{port}")
    webbrowser.open(f"http://127.0.0.1:{port}")

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    app.state._server = server

    print("调整完成后点击「确认并保存」")
    server.run()
