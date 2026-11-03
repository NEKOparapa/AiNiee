"""Plan locally located OCR crops before asking a provider to recognize text.

The two detection views share the original image coordinate system. Crops are
identified by their geometry and keep vertical writing upright; remote OCR is
responsible only for text, never for constructing replacement coordinates.
"""
import hashlib
import io
import json
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.ocr.dashscope import MAX_IMAGE_BYTES, _line, validate_polygon
from Backend.infrastructure.ocr.geometry import _check_cancelled, detect_polygons
from Backend.infrastructure.ocr.layout import order_page


DETECTION_VERSION = "rapidocr-regions-v1"
REGIONS_VERSION = DETECTION_VERSION
CROP_VERSION = "polygon-white-v1"
MAX_REGIONS = 128
MAX_DETECTION_CANDIDATES = 2000


def _bounds(polygon):
    xs, ys = zip(*polygon)
    return min(xs), min(ys), max(xs), max(ys)


def _area(polygon):
    return abs(cv2.contourArea(np.asarray(polygon, dtype=np.float32)))


def _overlap(a, b):
    overlap, _ = cv2.intersectConvexConvex(np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32))
    return max(0.0, float(overlap))


def _shape(polygon):
    x0, y0, x1, y1 = _bounds(polygon)
    w, h = x1 - x0, y1 - y0
    return w, h, "vertical" if h > w * 1.25 else "horizontal"


def _canonical(polygon):
    hull = cv2.convexHull(np.asarray(polygon, dtype=np.float32)).reshape(-1, 2).tolist()
    start = min(range(len(hull)), key=lambda i: (hull[i][1], hull[i][0]))
    return [[round(float(x), 4), round(float(y), 4)] for x, y in hull[start:] + hull[:start]]


def _deduplicate(candidates):
    """Prefer complete long lines, then compact isolated glyphs.

    A coarse box spanning two nearby square glyphs should not supersede a
    complete column plus a separate glyph found by the other view.
    """
    def priority(record):
        w, h, _ = _shape(record["polygon"])
        aspect = max(w, h) / min(w, h)
        area = _area(record["polygon"])
        location = tuple(value for point in record["polygon"] for value in point)
        return (0, -aspect, -area, location) if aspect >= 2 else (1, area, aspect, location)

    kept = []
    for candidate in sorted(candidates, key=priority):
        polygon = candidate["polygon"]
        area = _area(polygon)
        duplicates = [record for record in kept if _overlap(polygon, record["polygon"])
                      >= .75 * min(area, _area(record["polygon"]))]
        if duplicates:
            record = duplicates[0]
            record["views"] = sorted(set(record["views"] + candidate["views"]))
            # Same-line near duplicates may differ by a clipped stroke. Union
            # only when both shapes agree and overlap most of BOTH boxes.
            common = _overlap(polygon, record["polygon"])
            if (_shape(polygon)[2] == _shape(record["polygon"])[2]
                    and common >= .65 * max(area, _area(record["polygon"]))):
                record["polygon"] = _canonical(record["polygon"] + polygon)
            continue
        kept.append({"polygon": polygon, "views": list(candidate["views"])})
    return kept


def _fragment_pair(a, b):
    aa, bb = _bounds(a), _bounds(b)
    aw, ah, ad = _shape(a)
    bw, bh, bd = _shape(b)
    # A near-square glyph can be a detached first/last character of a line.
    elongated_a, elongated_b = max(aw, ah) >= 2 * min(aw, ah), max(bw, bh) >= 2 * min(bw, bh)
    if not elongated_a and not elongated_b:
        return False
    direction = ad if elongated_a else bd
    if elongated_a and elongated_b and ad != bd:
        return False
    if direction == "vertical":
        short_a, short_b = aw, bw
        across = max(0, min(aa[2], bb[2]) - max(aa[0], bb[0]))
        along = max(aa[1], bb[1]) - min(aa[3], bb[3])
    else:
        short_a, short_b = ah, bh
        across = max(0, min(aa[3], bb[3]) - max(aa[1], bb[1]))
        along = max(aa[0], bb[0]) - min(aa[2], bb[2])
    if not .5 <= short_a / short_b <= 2 or across < .75 * min(short_a, short_b):
        return False
    # Keep overlapping parallel lines separate; this operation joins only
    # end-to-end pieces of one column/row, with at most slight box overlap.
    return -.2 * min(short_a, short_b) <= along <= .5 * min(short_a, short_b)


def _merge_fragments(records):
    records = list(records)
    while True:
        merged = False
        for i, first in enumerate(records):
            for j in range(i + 1, len(records)):
                second = records[j]
                if not _fragment_pair(first["polygon"], second["polygon"]):
                    continue
                polygon = _canonical(first["polygon"] + second["polygon"])
                # Joining pieces must not swallow a third detected line.
                if any(_overlap(polygon, other["polygon"]) > .15 * _area(other["polygon"])
                       for k, other in enumerate(records) if k not in (i, j)):
                    continue
                records[i] = {"polygon": polygon, "views": sorted(set(first["views"] + second["views"]))}
                records.pop(j)
                merged = True
                break
            if merged:
                break
        if not merged:
            return records


def regions_from_detections(image_size, primary, rotated):
    """Normalize two views into stable recognition regions (pure geometry).

    ``rotated`` coordinates are already mapped back to the original image.
    This helper permits tests and cached local detections without model calls.
    """
    width, height = image_size
    if len(primary) + len(rotated) > MAX_DETECTION_CANDIDATES:
        raise PipelineError("OCR_TOO_MANY_REGIONS", "本地检测区域过多，请拆分图片后重试", 400)
    candidates = [{"polygon": _canonical(validate_polygon(polygon, width, height)), "views": [view]}
                  for view, polygons in (("original", primary), ("rotated_90", rotated)) for polygon in polygons]
    records = _merge_fragments(_deduplicate(candidates))
    if len(records) > MAX_REGIONS:
        raise PipelineError("OCR_TOO_MANY_REGIONS", f"单图识别区域超过 {MAX_REGIONS} 个，请拆分图片后重试", 400)
    regions = []
    for record in records:
        # _line derives direction/skew from geometry. The sentinel is never
        # exposed as recognized text and never sent to translation.
        geometry = _line({"text": "?", "polygon": record["polygon"]}, width, height)
        identity = json.dumps({"version": DETECTION_VERSION, "polygon": geometry["polygon"]}, sort_keys=True)
        regions.append({**geometry, "text": "", "region_id": hashlib.sha256(identity.encode()).hexdigest(),
                        "coordinates_source": "local_detector",
                        "detector": {"engine": "rapidocr_onnxruntime", "model": "ch_PP-OCRv4_det_infer",
                                     "version": DETECTION_VERSION, "views": record["views"]}})
    return regions


def plan_regions(image, *, reading_order="auto", context=None):
    if reading_order not in ("auto", "ltr", "manga_rtl"):
        raise ValueError("invalid OCR reading order")
    _check_cancelled(context)
    primary = detect_polygons(image, context)
    # Detect the same pixels upright and clockwise, then undo that rotation.
    # All returned geometry remains in normalized source-image pixels.
    rotated = detect_polygons(image.transpose(Image.Transpose.ROTATE_270), context)
    mapped = [[[y, image.height - 1 - x] for x, y in polygon] for polygon in rotated]
    regions = regions_from_detections(image.size, primary, mapped)
    _check_cancelled(context)
    rtl = reading_order == "manga_rtl" or (reading_order == "auto" and
          sum(region["direction"] == "vertical" for region in regions) > len(regions) / 2)
    return order_page(regions, image, rtl=rtl)


def prepare_region(image, region, max_pixels):
    """Return a bounded PNG crop with neighboring text masked to white."""
    if type(max_pixels) is not int or not 3136 <= max_pixels <= 23520000:
        raise PipelineError("OCR_CONFIG_ERROR", "识别裁切的 max_pixels 必须为 3136 至 23520000", 400)
    polygon = validate_polygon(region["polygon"], image.width, image.height)
    x0, y0, x1, y1 = _bounds(polygon)
    padding = min(12, max(3, math.ceil(min(x1 - x0, y1 - y0) * .15)))
    box = (max(0, math.floor(x0) - padding), max(0, math.floor(y0) - padding),
           min(image.width, math.ceil(x1) + padding), min(image.height, math.ceil(y1) + padding))
    rgba = image.crop(box).convert("RGBA")
    crop = Image.new("RGB", rgba.size, "white")
    crop.paste(rgba, mask=rgba.getchannel("A"))
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).polygon([(x - box[0], y - box[1]) for x, y in polygon], fill=255)
    isolated = Image.new("RGB", crop.size, "white")
    isolated.paste(crop, mask=mask)
    area = crop.width * crop.height
    scale = min(max(2.0, math.sqrt(3136 / area)), math.sqrt(max_pixels / area))
    size = (max(1, math.ceil(crop.width * scale)), max(1, math.ceil(crop.height * scale)))
    # Integer rounding must respect BOTH provider pixel bounds.
    letterbox = size[0] * size[1] > max_pixels
    if letterbox:
        size = (max(1, math.floor(crop.width * scale)), max(1, math.floor(crop.height * scale)))
    if size[0] * size[1] < 3136:
        size = (size[0], math.ceil(3136 / size[0]))
    if size[0] * size[1] > max_pixels:
        # At the exact minimum budget use padding to a 56×56 square, so a
        # narrow crop does not force an invalid product after integer rounding.
        size = (56, 56)
    if letterbox:
        content = ImageOps.contain(isolated, size, Image.Resampling.LANCZOS)
        upload = Image.new("RGB", size, "white")
        upload.paste(content, ((size[0] - content.width) // 2, (size[1] - content.height) // 2))
    else:
        upload = isolated.resize(size, Image.Resampling.LANCZOS)
    for _ in range(12):
        buffer = io.BytesIO()
        upload.save(buffer, format="PNG", optimize=True)
        if buffer.tell() < MAX_IMAGE_BYTES:
            return buffer.getvalue(), upload.size, {"version": CROP_VERSION, "box": list(box),
                    "polygon": polygon, "padding": padding, "mask": "polygon_white_background",
                    "source_size": list(crop.size), "upload_size": list(upload.size),
                    "coordinates_source": "local_detector"}
        next_size = (max(1, math.floor(upload.width * .8)), max(1, math.floor(upload.height * .8)))
        if next_size[0] * next_size[1] < 3136:
            break
        upload = upload.resize(next_size, Image.Resampling.LANCZOS)
    raise PipelineError("OCR_IMAGE_TOO_LARGE", "文字区域裁切超过 7 MB 上传上限", 400)
