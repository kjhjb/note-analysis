from __future__ import annotations

import html
import json
import os
import sys
import webbrowser
from pathlib import Path

from note_analysis.models.models import Exam, QuestionBox
from note_analysis.models.serializer import Serializer

_DEFAULT_SKILL_ROOT = Path("C:/Users/liang/.config/opencode/skills/note-skill-main")


def _get_skill_root() -> Path:
    env_root = os.environ.get("NOTE_SKILL_ROOT")
    if env_root:
        return Path(env_root)
    return _DEFAULT_SKILL_ROOT


class NoteRenderer:
    def __init__(
        self,
        exam_dir: str | Path,
        skill_root: str | Path | None = None,
    ):
        self.exam_dir = Path(exam_dir)
        self.skill_root = Path(skill_root) if skill_root else _get_skill_root()

    def _load_exam(self) -> Exam:
        files = Serializer.find_exam_files(self.exam_dir)
        if not files:
            msg = f"未找到 JSON 文件: {self.exam_dir}"
            raise FileNotFoundError(msg)
        return Serializer.load(files[0])

    def load_template(self) -> str:
        template_path = self.skill_root / "assets" / "template.html"
        if not template_path.exists():
            msg = f"模板文件不存在: {template_path}"
            raise FileNotFoundError(msg)
        return template_path.read_text(encoding="utf-8")

    @staticmethod
    def _escape(text: str) -> str:
        return html.escape(text, quote=False)

    def _build_question_section(self, box: QuestionBox, base_delay: float) -> str:
        parts: list[str] = []
        parts.append('<div class="section">')

        delay = base_delay
        parts.append(
            f'<div class="section-title write-in" style="animation-delay:{delay:.1f}s">'
            f'<i class="lucide-pencil"></i> 题目 #{box.id}'
            f'<div class="marker-underline"></div></div>'
        )

        delay += 0.1
        qt = self._escape(box.questionText) if box.questionText else ""
        parts.append(
            f'<div class="content write-in" style="animation-delay:{delay:.1f}s">'
            f'{qt}</div>'
        )

        if box.annotations:
            delay += 0.1
            ann = self._escape(box.annotations)
            parts.append(
                f'<div class="content write-in red-text" style="animation-delay:{delay:.1f}s">'
                f'<span class="badge orange">笔记</span> {ann}</div>'
            )

        for img_b64 in box.images:
            delay += 0.1
            parts.append(
                f'<div class="content write-in" style="animation-delay:{delay:.1f}s">'
                f'<img src="data:image/jpeg;base64,{img_b64}" '
                f'style="max-width:100%;border-radius:4px;margin:0.5rem 0;"></div>'
            )

        if box.uncertainRegions:
            for ur in box.uncertainRegions:
                delay += 0.1
                text = self._escape(ur.userConfirmed if ur.userConfirmed else ur.llmGuess)
                parts.append(
                    f'<div class="side-note write-in" style="animation-delay:{delay:.1f}s">'
                    f'<b>不确定区域:</b> {text}</div>'
                )

        if box.reviewNotes:
            delay += 0.1
            icon = "&#10003;" if box.reviewStatus == "consistent" else "&#9888;"
            cls = "check-mark" if box.reviewStatus == "consistent" else "cross-mark"
            rn = self._escape(box.reviewNotes)
            parts.append(
                f'<div class="content write-in" style="animation-delay:{delay:.1f}s">'
                f'<span class="{cls}">{icon}</span> {rn}</div>'
            )

        parts.append("</div>")
        return "\n".join(parts)

    def _self_check(self, html_content: str) -> list[str]:
        issues: list[str] = []
        if "[必填]" in html_content or "[笔记标题]" in html_content:
            issues.append("标题占位符未替换")
        if "[小节标题]" in html_content:
            issues.append("小节占位符未替换")
        if "mathjax" not in html_content.lower():
            issues.append("MathJax 未嵌入")
        if "application/json" not in html_content:
            issues.append("JSON 数据未嵌入")
        return issues

    def render(self, open_browser: bool = False) -> str:
        exam = self._load_exam()
        template = self.load_template()

        html_content = template

        html_content = html_content.replace(
            "[必填] 替换为笔记标题",
            f"笔记_{exam.createdAt}",
        )
        html_content = html_content.replace(
            "[笔记标题]",
            f"试卷笔记 - {exam.createdAt[:4]}-{exam.createdAt[4:6]}-{exam.createdAt[6:8]}",
        )
        html_content = html_content.replace(
            "[副标题或日期信息]",
            f"{exam.createdAt[:4]}-{exam.createdAt[4:6]}-{exam.createdAt[6:8]} "
            f"{exam.createdAt[9:11]}:{exam.createdAt[11:13]}  |  共 {len(exam.boxes)} 题",
        )

        if exam.boxes:
            sections: list[str] = []
            delay = 0.5
            for box in exam.boxes:
                section_html = self._build_question_section(box, delay)
                sections.append(section_html)
                delay += 0.4
            generated_content = "\n".join(sections)
        else:
            generated_content = (
                '<div class="section">'
                '<div class="content write-in" style="animation-delay:0.5s">'
                "暂无题目内容</div></div>"
            )

        start_marker = "<!-- ===== 内容段落示例 ===== -->"
        end_marker = "<!-- ===== 流程图示例 ===== -->"
        start_idx = html_content.find(start_marker)
        end_idx = html_content.find(end_marker)
        if start_idx != -1 and end_idx != -1:
            html_content = html_content[:start_idx] + generated_content + html_content[end_idx:]
        else:
            print("警告: 模板中未找到内容占位符标记，内容将追加到末尾", file=sys.stderr)
            html_content = html_content + generated_content

        mathjax_script = (
            '<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js">'
            "</script>"
        )

        exam_json = json.dumps(exam.model_dump(), ensure_ascii=False, indent=2)
        json_script = (
            f'<script id="exam-data" type="application/json">\n{exam_json}\n</script>'
        )

        body_end = html_content.rfind("</body>")
        if body_end != -1:
            html_content = (
                html_content[:body_end]
                + mathjax_script
                + "\n"
                + json_script
                + "\n"
                + html_content[body_end:]
            )

        issues = self._self_check(html_content)
        for issue in issues:
            print(f"  自检: {issue}", file=sys.stderr)

        if open_browser:
            output_path = self.exam_dir / exam.html_filename
            webbrowser.open(str(output_path.resolve()))

        return html_content

    def save(self, open_browser: bool = False) -> Path:
        html_content = self.render(open_browser=open_browser)
        exam = self._load_exam()
        output_path = self.exam_dir / exam.html_filename
        output_path.write_text(html_content, encoding="utf-8")
        return output_path
