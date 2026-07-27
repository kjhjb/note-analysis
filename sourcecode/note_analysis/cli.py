import sys
from pathlib import Path

import click

from note_analysis.models.models import Exam
from note_analysis.models.serializer import Serializer


@click.group()
def cli() -> None:
    """笔记分析工具 — 自动将试卷照片整理为手写风格笔记"""


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def init(exam_dir: Path) -> None:
    """扫描 exam-dir 中的照片，生成初始 JSON 骨架"""
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    photos: list[str] = []
    for f in sorted(exam_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in image_extensions:
            photos.append(str(f.resolve()))

    if not photos:
        click.echo(f"错误: 未在 {exam_dir} 中找到任何图片文件", err=True)
        sys.exit(1)

    exam = Exam.create(photos)
    output_path = Serializer.save(exam, exam_dir)
    click.echo(f"已扫描 {len(photos)} 张图片")
    click.echo(f"JSON 骨架已生成: {output_path}")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def box(exam_dir: Path) -> None:
    """CV 框选大题（待实现）"""
    click.echo("框选功能待实现（Ticket 02）")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def serve(exam_dir: Path) -> None:
    """启动 Web UI（框选微调 + 不确定确认）"""
    click.echo("Web UI 待实现（Ticket 03）")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def recognize(exam_dir: Path) -> None:
    """Agent 调用 LLM 识别（待实现）"""
    click.echo("识别功能待实现（Ticket 04）")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def review(exam_dir: Path) -> None:
    """Agent 调用 LLM 合理性审查（待实现）"""
    click.echo("审查功能待实现（Ticket 05）")


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def render(exam_dir: Path) -> None:
    """Agent 调用学霸笔记 skill 渲染 HTML（待实现）"""
    click.echo("渲染功能待实现（Ticket 06）")


@cli.command()
@click.argument("exams_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def analyze(exams_dir: Path) -> None:
    """Agent 跨卷薄弱点分析（待实现）"""
    click.echo("分析功能待实现（Ticket 07）")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
