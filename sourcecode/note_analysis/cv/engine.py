from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from note_analysis.models.models import BBox


class CVEngine:
    """基于传统 OpenCV 的试卷大题框选引擎"""

    MIN_REGION_HEIGHT = 30
    WHITE_THRESHOLD = 0.98

    def __init__(self, image: np.ndarray) -> None:
        self._original = image
        self._gray: np.ndarray | None = None

    def preprocess(self) -> np.ndarray:
        """灰度化 → 高斯模糊去噪 → OTSU 二值化 → 形态学开运算 → 倾斜校正"""
        if self._original.ndim == 3:
            gray = cv2.cvtColor(self._original, cv2.COLOR_BGR2GRAY)
        else:
            gray = self._original.copy()

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        deskewed = self._deskew(cleaned)
        self._gray = deskewed
        return deskewed

    @staticmethod
    def _deskew(binary: np.ndarray) -> np.ndarray:
        """基于最小面积外接矩形检测倾斜角并校正"""
        coords = np.column_stack(np.where(binary == 0))
        if len(coords) < 100:
            return binary

        rect = cv2.minAreaRect(coords)
        angle = rect[2]
        if angle < -45:
            angle = 90 + angle

        if abs(angle) < 0.5:
            return binary

        h, w = binary.shape
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(binary, rot_mat, (w, h), borderValue=255, flags=cv2.INTER_NEAREST)
        return rotated

    def detect_boxes(self) -> list[BBox]:
        """水平投影法检测大题边界"""
        if self._gray is None:
            self.preprocess()
        assert self._gray is not None

        binary: np.ndarray = self._gray
        height, width = binary.shape

        # 形态学闭运算合并同一区域内的相邻文字行
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 15))
        merged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        row_sums = np.sum(merged == 0, axis=1)
        gap_mask = row_sums < width * (1 - self.WHITE_THRESHOLD)

        regions: list[tuple[int, int]] = []
        in_region = False
        start = 0
        for row in range(height):
            if not gap_mask[row] and not in_region:
                start = row
                in_region = True
            elif gap_mask[row] and in_region:
                if row - start >= self.MIN_REGION_HEIGHT:
                    regions.append((start, row))
                in_region = False
        if in_region and height - start >= self.MIN_REGION_HEIGHT:
            regions.append((start, height))

        boxes: list[BBox] = []
        for y1, y2 in regions:
            col_sums = np.sum(binary[y1:y2] == 0, axis=0)
            col_mask = col_sums > 0
            cols = np.where(col_mask)[0]
            if len(cols) == 0:
                continue
            x1, x2 = int(cols[0]), int(cols[-1])
            pad = 5
            x1 = max(0, x1 - pad)
            x2 = min(width, x2 + pad)
            y1_pad = max(0, y1 - pad)
            y2_pad = min(height, y2 + pad)
            boxes.append(BBox(x=float(x1), y=float(y1_pad), w=float(x2 - x1), h=float(y2_pad - y1_pad)))

        return boxes

    def draw_preview(self, boxes: list[BBox], output_path: str | Path) -> None:
        """在原图上绘制红色 bbox 矩形框并保存"""
        display = self._original.copy()
        if display.ndim == 2:
            display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)

        for bbox in boxes:
            x, y, w, h = int(bbox.x), int(bbox.y), int(bbox.w), int(bbox.h)
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 0, 255), 3)

        cv2.imwrite(str(output_path), display)

    @classmethod
    def process_exam(cls, exam_dir: str | Path) -> None:
        """对目录中 JSON 指定的每张照片执行框选并更新 JSON"""
        from note_analysis.models.models import QuestionBox
        from note_analysis.models.serializer import Serializer

        exam_dir = Path(exam_dir)
        json_files = Serializer.find_exam_files(exam_dir)
        if not json_files:
            msg = f"未找到 JSON 文件: {exam_dir}"
            raise FileNotFoundError(msg)

        exam = Serializer.load(json_files[0])
        all_boxes: list[QuestionBox] = []
        box_id = 1

        import sys

        for photo_idx, photo_path in enumerate(exam.photos):
            img = cv2.imread(photo_path)
            if img is None:
                print(f"警告: 无法读取图片 {photo_path}，已跳过", file=sys.stderr)
                continue

            engine = cls(img)
            boxes = engine.detect_boxes()

            photo_name = Path(photo_path).stem
            preview_path = exam_dir / f"{photo_name}_bbox_preview.jpg"
            engine.draw_preview(boxes, str(preview_path))

            for bbox in boxes:
                all_boxes.append(QuestionBox(id=box_id, bbox=bbox, photoIndex=photo_idx))
                box_id += 1

        exam.boxes = all_boxes
        Serializer.save(exam, exam_dir)
