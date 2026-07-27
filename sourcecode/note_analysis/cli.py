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
    """CV 框选大题"""
    from note_analysis.cv.engine import CVEngine

    try:
        CVEngine.process_exam(exam_dir)
        click.echo("框选完成")
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def serve(exam_dir: Path) -> None:
    """启动 Web UI（框选微调 + 不确定确认）"""
    from note_analysis.web.server import run_server

    try:
        run_server(exam_dir)
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--threshold",
    default=0.8,
    type=float,
    help="置信度阈值（低于此值的区域标记为不确定，默认 0.8）",
)
def recognize(exam_dir: Path, threshold: float) -> None:
    """Agent 调用 LLM 识别"""
    from note_analysis.agent.recognizer import Recognizer

    try:
        r = Recognizer(exam_dir, threshold=threshold)
        exam = r.recognize()
        click.echo(f"识别完成: {len(exam.boxes)} 道题")
        uncertain_count = sum(len(b.uncertainRegions) for b in exam.boxes)
        if uncertain_count:
            click.echo(f"标记了 {uncertain_count} 个不确定区域")
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"识别错误: {e}", err=True)
        sys.exit(1)


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
