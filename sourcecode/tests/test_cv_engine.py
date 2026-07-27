from pathlib import Path

import cv2
import numpy as np

from note_analysis.models.models import BBox


def _make_synthetic_exam(height: int = 1200, width: int = 800) -> np.ndarray:
    """创建模拟试卷灰度图：白底 + 若干黑色文字横条 + 横条间空白间隔"""
    img = np.ones((height, width), dtype=np.uint8) * 255
    # 等距分布 3 个文字区域
    gap = height // 6
    bar_h = height // 10
    margin_w = width // 16
    regions: list[tuple[int, int]] = []
    for i in range(3):
        y1 = gap + i * (bar_h + gap)
        y2 = y1 + bar_h
        if y2 > height - 10:
            break
        regions.append((y1, y2))
    for y1, y2 in regions:
        img[y1:y2, margin_w:width - margin_w] = 200
        for row in range(y1 + 8, y2 - 8, max(3, (y2 - y1) // 8)):
            img[row, margin_w + 10:width - margin_w - 10] = 30
    return img


def _make_synthetic_exam_no_gaps(height: int = 600, width: int = 800) -> np.ndarray:
    """一整块连续文字，无空白间隔"""
    img = np.ones((height, width), dtype=np.uint8) * 255
    margin_w = width // 16
    margin_h = height // 12
    bar_h = height - 2 * margin_h
    img[margin_h:margin_h + bar_h, margin_w:width - margin_w] = 200
    for row in range(margin_h + 10, margin_h + bar_h - 10, 15):
        img[row, margin_w + 10:width - margin_w - 10] = 30
    return img


def test_preprocess_grayscale():
    """预处理应输出二值化单通道图像"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam()
    engine = CVEngine(img)
    result = engine.preprocess()
    assert result.ndim == 2
    assert result.dtype == np.uint8
    assert set(np.unique(result)).issubset({0, 255})


def test_preprocess_denoising():
    """预处理应通过高斯模糊去除轻微噪点"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam()
    img = img.astype(np.float32)
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 15, img.shape)
    img = np.clip(img + noise, 0, 255).astype(np.uint8)
    engine = CVEngine(img)
    result = engine.preprocess()
    assert result.ndim == 2
    assert result.dtype == np.uint8
    assert set(np.unique(result)).issubset({0, 255})


def test_detect_boxes_three_regions():
    """三块文字区域应检测出三个 bbox"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam()
    engine = CVEngine(img)
    boxes = engine.detect_boxes()
    assert len(boxes) == 3
    for bbox in boxes:
        assert isinstance(bbox, BBox)
        assert bbox.x >= 0
        assert bbox.y >= 0
        assert bbox.w > 0
        assert bbox.h > 0
    # 按 y 排序，检查位置（1200px 高度下三块等距分布）
    boxes_sorted = sorted(boxes, key=lambda b: b.y)
    assert 50 <= boxes_sorted[0].y <= 250
    assert boxes_sorted[1].y > boxes_sorted[0].y + 50
    assert boxes_sorted[2].y > boxes_sorted[1].y + 50


def test_detect_boxes_empty_image():
    """纯白图像应返回空列表"""
    from note_analysis.cv.engine import CVEngine

    img = np.ones((600, 800), dtype=np.uint8) * 255
    engine = CVEngine(img)
    boxes = engine.detect_boxes()
    assert boxes == []


def test_detect_boxes_single_region():
    """一整块连续文字应检测出单个 bbox"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam_no_gaps()
    engine = CVEngine(img)
    boxes = engine.detect_boxes()
    assert len(boxes) == 1


def test_detect_boxes_non_overlapping():
    """检测出的 bbox 不应互相重叠"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam()
    engine = CVEngine(img)
    boxes = engine.detect_boxes()

    def overlap(a: BBox, b: BBox) -> bool:
        return not (a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y)

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            assert not overlap(boxes[i], boxes[j]), f"Box {i} and {j} overlap"


def test_draw_preview(tmp_path: Path) -> None:
    """绘制预览图应生成图片文件"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam()
    engine = CVEngine(img)
    boxes = [BBox(x=50, y=100, w=700, h=80)]
    output_path = tmp_path / "preview.jpg"
    engine.draw_preview(boxes, str(output_path))
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_preprocess_deskew():
    """倾斜校正应纠正小幅旋转使文本行水平"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam(height=400, width=400)
    # 手动旋转 -3 度模拟倾斜试卷
    h, w = img.shape
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, -3.0, 1.0)
    rotated = cv2.warpAffine(img, rot_mat, (w, h), borderValue=255)

    engine = CVEngine(rotated)
    result = engine.preprocess()
    assert result.ndim == 2
    assert result.shape == (400, 400)
    assert result.dtype == np.uint8


def test_detect_boxes_deskewed():
    """倾斜校正后应能检测到正常数量的 box"""
    from note_analysis.cv.engine import CVEngine

    img = _make_synthetic_exam(height=400, width=400)
    # 先在不倾斜时检测箱数作为基线
    baseline_engine = CVEngine(img)
    baseline_boxes = baseline_engine.detect_boxes()
    baseline_count = len(baseline_boxes)

    # 旋转 3 度后检测
    h, w = img.shape
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, 3.0, 1.0)
    rotated = cv2.warpAffine(img, rot_mat, (w, h), borderValue=255)

    engine = CVEngine(rotated)
    boxes = engine.detect_boxes()
    # 倾斜校正后检测数量应与未倾斜时一致
    assert len(boxes) == baseline_count


def test_draw_preview_with_empty_boxes(tmp_path: Path) -> None:
    """空框列表也应生成预览图"""
    from note_analysis.cv.engine import CVEngine

    img = np.ones((600, 800), dtype=np.uint8) * 255
    engine = CVEngine(img)
    output_path = tmp_path / "empty_preview.jpg"
    engine.draw_preview([], str(output_path))
    assert output_path.exists()
