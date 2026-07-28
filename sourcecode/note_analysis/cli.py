import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from note_analysis.models.models import Exam
from note_analysis.models.serializer import Serializer


@click.group()
@click.option(
    "--env-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help=".env 配置文件路径（可配置 LLM_API_KEY、LLM_API_URL 等）",
)
@click.pass_context
def cli(ctx: click.Context, env_file: Path | None) -> None:
    """笔记分析工具 — 自动将试卷照片整理为手写风格笔记"""
    if env_file is not None:
        load_dotenv(env_file)


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
    """启动 Web UI（框选微调 + 不确定区域确认）"""
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
def uncertain(exam_dir: Path) -> None:
    """Agent 调用 LLM 对不确定区域生成更精确的文本猜测"""
    from note_analysis.agent.uncertainty import UncertaintyResolver

    try:
        r = UncertaintyResolver(exam_dir)
        exam = r.resolve()
        total = sum(len(b.uncertainRegions) for b in exam.boxes)
        click.echo(f"不确定区域处理完成: {total} 个区域")
        if total:
            click.echo("请运行 `serve` 命令在 Web UI 中确认")
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"处理错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def review(exam_dir: Path) -> None:
    """Agent 调用 LLM 合理性审查"""
    from note_analysis.agent.review import Reviewer
    from note_analysis.agent.uncertainty import UncertaintyResolver

    try:
        json_files = Serializer.find_exam_files(exam_dir)
        if not json_files:
            click.echo("错误: 未找到 JSON 文件", err=True)
            sys.exit(1)
        exam = Serializer.load(json_files[0])
        if not UncertaintyResolver.all_confirmed(exam):
            click.echo("错误: 尚有不确定区域未确认，请先运行 `serve` 完成确认", err=True)
            sys.exit(1)

        r = Reviewer(exam_dir)
        exam = r.review()
        summary_lines = [f"审查完成: {len(exam.boxes)} 道题"]
        for box in exam.boxes:
            summary_lines.append(
                f"  题目 #{box.id}: {box.reviewStatus} — {box.reviewNotes}"
            )
        click.echo("\n".join(summary_lines))
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"审查错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def correct(exam_dir: Path) -> None:
    """Agent 调用 LLM 为错题生成修正解答"""
    from note_analysis.agent.correction import Corrector

    try:
        c = Corrector(exam_dir)
        exam = c.correct()
        corrected_count = sum(1 for b in exam.boxes if b.correction and b.isError)
        click.echo(f"修正完成: {corrected_count} 道错题已生成修正解答")
        if not corrected_count:
            click.echo("没有标记为错误的题目，无需修正")
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"修正错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--open/--no-open",
    "open_browser",
    default=True,
    help="渲染后自动在浏览器中打开预览（默认打开）",
)
def render(exam_dir: Path, open_browser: bool) -> None:
    """基于学霸笔记 skill 模板渲染 HTML 笔记页"""
    from note_analysis.renderer.engine import NoteRenderer

    try:
        r = NoteRenderer(exam_dir)
        output_path = r.save(open_browser=open_browser)
        click.echo(f"HTML 笔记已生成: {output_path}")
        if open_browser:
            click.echo("已在浏览器中打开预览")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exams_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def analyze(exams_dir: Path) -> None:
    """Agent 跨卷薄弱点分析"""
    from note_analysis.analyzer.engine import Analyzer

    try:
        a = Analyzer(exams_dir)
        exams = a.analyze()
        if not exams:
            click.echo("未找到试卷 JSON 文件")
            return
        click.echo(f"分析完成: {len(exams)} 份试卷")
        for exam in exams:
            click.echo(f"  试卷 {exam.examId}: {len(exam.weakPoints)} 个薄弱点")
            for wp in exam.weakPoints:
                click.echo(f"    - {wp.knowledgePoint} (错误频次: {wp.errorCount})")
                click.echo(f"      建议: {wp.llmAdvice}")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("exam_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--threshold",
    default=0.8,
    type=float,
    help="置信度阈值（默认 0.8）",
)
@click.option(
    "--open/--no-open",
    "open_browser",
    default=True,
    help="渲染后自动打开浏览器（默认打开）",
)
def pipeline(exam_dir: Path, threshold: float, open_browser: bool) -> None:
    """一键执行完整流水线: init → box → recognize → uncertain → review → correct → render"""
    from note_analysis.agent.recognizer import Recognizer
    from note_analysis.agent.review import Reviewer
    from note_analysis.agent.uncertainty import UncertaintyResolver
    from note_analysis.cv.engine import CVEngine
    from note_analysis.models.serializer import Serializer
    from note_analysis.renderer.engine import NoteRenderer

    click.echo("=== 步骤 1/7: init — 扫描照片 ===")
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    photos: list[str] = []
    for f in sorted(exam_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in image_extensions:
            photos.append(str(f.resolve()))
    if not photos:
        click.echo(f"错误: 未在 {exam_dir} 中找到图片", err=True)
        sys.exit(1)
    exam = Exam.create(photos)
    Serializer.save(exam, exam_dir)
    click.echo(f"  已扫描 {len(photos)} 张图片")

    click.echo("=== 步骤 2/7: box — CV 框选大题 ===")
    try:
        CVEngine.process_exam(exam_dir)
        click.echo("  框选完成")
    except FileNotFoundError as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)

    click.echo("=== 步骤 3/7: recognize — LLM 识别 ===")
    try:
        rec = Recognizer(exam_dir, threshold=threshold)
        exam = rec.recognize()
        uncertain_count = sum(len(b.uncertainRegions) for b in exam.boxes)
        click.echo(f"  识别完成: {len(exam.boxes)} 道题, {uncertain_count} 个不确定区域")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)

    click.echo("=== 步骤 4/7: uncertain — 不确定区域处理 ===")
    try:
        unc = UncertaintyResolver(exam_dir)
        exam = unc.resolve()
        total = sum(len(b.uncertainRegions) for b in exam.boxes)
        click.echo(f"  处理完成: {total} 个区域")
        if total:
            click.echo("  ! 请运行 `note-analysis serve <dir>` 在 Web UI 中确认不确定区域")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)

    click.echo("=== 步骤 5/7: review — 合理性审查 ===")
    try:
        json_files = Serializer.find_exam_files(exam_dir)
        exam = Serializer.load(json_files[0]) if json_files else exam
        if not UncertaintyResolver.all_confirmed(exam):
            click.echo("  ! 跳过审查: 尚有不确定区域未确认", err=True)
        else:
            rev = Reviewer(exam_dir)
            exam = rev.review()
            click.echo(f"  审查完成: {len(exam.boxes)} 道题")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)

    click.echo("=== 步骤 6/7: correct — 错题修正 ===")
    try:
        from note_analysis.agent.correction import Corrector

        corr = Corrector(exam_dir)
        exam = corr.correct()
        corrected_count = sum(1 for b in exam.boxes if b.correction and b.isError)
        click.echo(f"  修正完成: {corrected_count} 道错题")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)

    click.echo("=== 步骤 7/7: render — HTML 渲染 ===")
    try:
        rend = NoteRenderer(exam_dir)
        output_path = rend.save(open_browser=open_browser)
        click.echo(f"  HTML 笔记已生成: {output_path}")
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)

    click.echo("=== 流水线完成 ===")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
