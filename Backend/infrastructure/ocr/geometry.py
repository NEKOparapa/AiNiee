"""Conservatively align provider OCR lines with independent local detections.

The detector supplies geometry only. It never replaces recognized text, guesses
which sentence belongs to another column, or relaxes the renderer's ink checks.
"""
import copy
from functools import lru_cache
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from PIL import Image

from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.ocr.dashscope import _line, validate_polygon


CALIBRATION_VERSION = "rapidocr-det-v1"
MAX_DETECTION_SIDE = 2000
MIN_MATCH_IOU = .4
MIN_MATCH_RATIO = 2.0
_DETECTOR_LOCK = Lock()


def _check_cancelled(context):
    if context is not None and context.is_cancelled():
        raise PipelineError("OCR_CANCELLED", "OCR 坐标校准已取消", 409)


@lru_cache(maxsize=1)
def _detector():
    # Construct only the detection session. RapidOCR() also initializes its
    # recognizer and classifier, neither of which belongs to this operation.
    try:
        import rapidocr_onnxruntime
        import yaml
        from rapidocr_onnxruntime.ch_ppocr_det import TextDetector
    except ImportError as error:
        raise PipelineError("OCR_LOCAL_DETECTOR_UNAVAILABLE", "本地文字定位组件不可用，请安装 rapidocr-onnxruntime", 500) from error
    root = Path(rapidocr_onnxruntime.__file__).resolve().parent
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))["Det"]
    config.update(model_path=str(root / config["model_path"]), use_cuda=False, use_dml=False,
                  limit_type="max", limit_side_len=MAX_DETECTION_SIDE,
                  intra_op_num_threads=2, inter_op_num_threads=1)
    return TextDetector(config)


def _detect_polygons(pixels, context=None):
    _check_cancelled(context)
    width, height = pixels.size
    if width < 1 or height < 1:
        raise ValueError("OCR calibration needs a nonempty image")
    ratio = min(1.0, MAX_DETECTION_SIDE / max(width, height))
    size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
    source = pixels.resize(size, Image.Resampling.LANCZOS) if size != pixels.size else pixels
    rgba = source.convert("RGBA")
    image = Image.new("RGB", rgba.size, "white")
    image.paste(rgba, mask=rgba.getchannel("A"))
    # Avoid the model's multiple-of-32 rounding producing an empty dimension
    # for a narrow source; padding never changes source coordinate scale.
    if min(size) < 32:
        padded = Image.new("RGB", (max(32, size[0]), max(32, size[1])), "white")
        padded.paste(image, (0, 0))
        image = padded
    bgr = np.ascontiguousarray(np.asarray(image)[:, :, ::-1])
    # TextDetector mutates preprocessing state on each call; share the loaded
    # model safely between independent API operations.
    with _DETECTOR_LOCK:
        _check_cancelled(context)
        boxes, _ = _detector()(bgr)
    _check_cancelled(context)
    if boxes is None:
        return []
    result = []
    for box in boxes:
        values = np.asarray(box, dtype=np.float64)
        if values.shape != (4, 2) or not np.all(np.isfinite(values)):
            raise PipelineError("OCR_LOCAL_GEOMETRY_INVALID", "本地文字定位返回无效坐标", 500)
        # A detection in white padding is not source text. Clipped detections
        # with zero area are discarded before validation and matching.
        polygon = [[min(width, max(0, float(x) * width / size[0])),
                    min(height, max(0, float(y) * height / size[1]))] for x, y in values]
        if abs(cv2.contourArea(np.asarray(polygon, dtype=np.float32))) >= 1:
            result.append(validate_polygon(polygon, width, height))
    return result


def detect_polygons(pixels, context=None):
    """Return independent local text geometry, without recognizing any text."""
    return _detect_polygons(pixels, context)


def _direction(polygon):
    xs, ys = zip(*polygon)
    return "vertical" if max(ys) - min(ys) > 1.25 * (max(xs) - min(xs)) else "horizontal"


def _clear_best(values):
    """Return a sufficiently strong unique winner, or no association."""
    if not len(values):
        return None
    order = np.argsort(values)
    best = int(order[-1])
    score = float(values[best])
    runner_up = float(values[order[-2]]) if len(order) > 1 else 0.0
    if score < MIN_MATCH_IOU or (runner_up > 0 and score < MIN_MATCH_RATIO * runner_up):
        return None
    return best


def match_line_polygons(lines, candidates, image_size):
    """Pure one-to-one matching, usable without loading a detection model.

    Both ends must independently choose the same unambiguous best overlap.
    Provider boxes competing for the same column therefore remain unchanged.
    """
    width, height = image_size
    result = copy.deepcopy(lines)
    if not lines or not candidates:
        return result, []
    current = [validate_polygon(line["polygon"], width, height) for line in lines]
    # Keep associations anchored to the provider evidence across repeated
    # previews/exports. Otherwise moving an accepted box can reduce competing
    # overlap and make a previously ambiguous line appear safe on the next run.
    originals = [validate_polygon(line.get("provider_polygon", line["polygon"]), width, height)
                 for line in lines]
    detected = [validate_polygon(polygon, width, height) for polygon in candidates]
    source_arrays = [np.asarray(polygon, dtype=np.float32) for polygon in originals]
    target_arrays = [np.asarray(polygon, dtype=np.float32) for polygon in detected]
    scores = np.zeros((len(lines), len(detected)), dtype=np.float64)
    for i, source in enumerate(source_arrays):
        if not cv2.isContourConvex(source):
            continue
        direction = lines[i].get("direction", _direction(originals[i]))
        source_area = abs(cv2.contourArea(source))
        for j, target in enumerate(target_arrays):
            if not cv2.isContourConvex(target) or direction != _direction(detected[j]):
                continue
            intersection, _ = cv2.intersectConvexConvex(source, target)
            union = source_area + abs(cv2.contourArea(target)) - intersection
            scores[i, j] = max(0.0, min(1.0, intersection / union)) if union else 0.0
    corrections = []
    for i, line in enumerate(result):
        j = _clear_best(scores[i])
        if j is None or _clear_best(scores[:, j]) != i or current[i] == detected[j]:
            continue
        provider_polygon = copy.deepcopy(line.get("provider_polygon", originals[i]))
        normalized = _line({"text": line["text"], "polygon": detected[j]}, width, height)
        line.update({key: normalized[key] for key in ("polygon", "rotation", "direction")})
        line["provider_polygon"] = provider_polygon
        corrections.append({"line_index": i, "method": CALIBRATION_VERSION,
                            "iou": round(float(scores[i, j]), 4),
                            "provider_polygon": provider_polygon, "polygon": copy.deepcopy(line["polygon"])})
    return result, corrections


def calibrate_lines(pixels, lines, context=None):
    """Detect local text and calibrate only unambiguous provider associations.

    Errors are propagated to the caller so paid OCR output can be retained and
    any unavailable detector or failed calibration can be reported explicitly.
    """
    _check_cancelled(context)
    if not lines:
        return [], []
    polygons = _detect_polygons(pixels, context)
    calibrated = match_line_polygons(lines, polygons, pixels.size)
    _check_cancelled(context)
    return calibrated
