import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import click

from note_analysis.models.exam import Exam


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def _now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def _scan_images(directory: str) -> list[str]:
    path = Path(directory)
    if not path.is_dir():
        raise click.BadParameter(f"目录不存在: {directory}")
    images = []
    for f in sorted(path.iterdir()):
        if f.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(str(f.absolute()))
    return images


def _save_exam(exam: Exam, directory: str) -> str:
    fname = f"笔记_{exam.createdAt}.json"
    fpath = Path(directory) / fname
    fpath.write_text(exam.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    return str(fpath)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """笔记分析工具 — 试卷拍照整理全流程"""


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def init(exam_dir):
    """扫描目录中的照片，生成初始 JSON 骨架"""
    photos = _scan_images(exam_dir)
    now = _now_str()
    exam = Exam(
        examId=str(uuid.uuid4())[:8],
        photos=photos,
        boxes=[],
        createdAt=now,
        weakPoints=[],
    )
    fpath = _save_exam(exam, exam_dir)
    click.echo(f"已生成: {fpath}")
    click.echo(f"  照片数: {len(photos)}")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True))
def box(exam_dir):
    """CV 框选大题（待实现）"""
    click.echo("框选功能待实现")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True))
def serve(exam_dir):
    """启动 Web UI（待实现）"""
    click.echo("Web UI 待实现")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True))
def recognize(exam_dir):
    """Agent 调用 LLM 识别（待实现）"""
    click.echo("识别功能待实现")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True))
def review(exam_dir):
    """Agent 调用 LLM 合理性审查（待实现）"""
    click.echo("审查功能待实现")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True))
def render(exam_dir):
    """Agent 调用学霸笔记 skill 渲染 HTML（待实现）"""
    click.echo("渲染功能待实现")


@cli.command()
@click.argument("exams_dir", type=click.Path(exists=True))
def analyze(exams_dir):
    """Agent 跨卷薄弱点分析（待实现）"""
    click.echo("分析功能待实现")


if __name__ == "__main__":
    cli()
