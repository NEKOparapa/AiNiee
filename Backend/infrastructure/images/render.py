"""Conservative text masks and fitted typesetting; no model/network coupling."""
import math
import os
from pathlib import Path
import re

import cv2
import freetype
import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_item import TranslationStatus
from Backend.infrastructure.files.pipeline_support import file_sha256


def polygon_points(value, size):
    if not isinstance(value, (list, tuple)) or len(value) < 3 or len(value) > 1000:
        raise PipelineError("INVALID_IMAGE_POLYGON", "图片文字区域需要有效多边形")
    points = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2 or any(
                isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in point):
            raise PipelineError("INVALID_IMAGE_POLYGON", "多边形坐标必须是有限数字")
        x, y = point
        if not 0 <= x <= size[0] or not 0 <= y <= size[1]:
            raise PipelineError("IMAGE_POLYGON_OUT_OF_BOUNDS", "文字区域超出规范化图片边界")
        points.append((float(x), float(y)))
    if abs(cv2.contourArea(np.array(points, dtype=np.float32))) < 1:
        raise PipelineError("INVALID_IMAGE_POLYGON", "文字区域面积必须大于零")
    return points


def find_font(font_path=None):
    if font_path:
        candidates = [Path(font_path).expanduser()]
    else:
        windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        candidates = [windows / "msyh.ttc", windows / "simhei.ttf", windows / "simsun.ttc",
                      Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                      Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
                      Path("/System/Library/Fonts/PingFang.ttc"),
                      Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for candidate in candidates:
        if candidate.is_file():
            try:
                ImageFont.truetype(str(candidate), 16)
                return candidate.resolve()
            except (OSError, ValueError):
                continue
    raise PipelineError("IMAGE_FONT_UNAVAILABLE", "找不到可用字体，请通过 font_path 指定支持目标语言的字体")


def _check_glyphs(path, text):
    try:
        face = freetype.Face(str(path))
        missing = sorted({c for c in text if not c.isspace() and not face.get_char_index(ord(c))})
        if missing:
            raise PipelineError("IMAGE_FONT_MISSING_GLYPHS", "所选字体缺少译文字形，请更换字体",
                                details={"codepoints": [f"U+{ord(c):04X}" for c in missing[:20]]})
    except PipelineError:
        raise
    except Exception as error:
        raise PipelineError("IMAGE_FONT_UNAVAILABLE", "无法校验字体字形") from error


def _bounds(points, size, margin=0):
    return (max(0, math.floor(min(p[0] for p in points)) - margin),
            max(0, math.floor(min(p[1] for p in points)) - margin),
            min(size[0], math.ceil(max(p[0] for p in points)) + margin),
            min(size[1], math.ceil(max(p[1] for p in points)) + margin))


def _local_polygon(points, bounds):
    return [(x - bounds[0], y - bounds[1]) for x, y in points]


def _poly_mask(points, size):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return np.array(mask)


def _wrap(text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            if font.getlength(char) > max_width:
                return None
            if current and font.getlength(current + char) > max_width:
                lines.append(current)
                current = char
            else:
                current += char
        lines.append(current)
    return lines


def _largest_rectangle(mask):
    """Largest all-allowed rectangle, including non-convex balloon interiors."""
    heights = np.zeros(mask.shape[1], dtype=np.int32)
    best, rectangle = 0, None
    for y, row in enumerate(mask):
        heights = np.where(row > 0, heights + 1, 0)
        stack = []
        for x in range(len(heights) + 1):
            height = int(heights[x]) if x < len(heights) else 0
            start = x
            while stack and stack[-1][1] > height:
                start, old_height = stack.pop()
                area = old_height * (x - start)
                if area > best:
                    best, rectangle = area, (start, y + 1 - old_height, x, y + 1)
            if height and (not stack or stack[-1][1] < height):
                stack.append((start, height))
    return rectangle


_VERTICAL_CLOSERS = set("，。、．,.!?！？：；:;）)]｝}】》〉」』”’")
_VERTICAL_OPENERS = set("（([｛{【《〈「『“‘")
_VERTICAL_ROTATE = set("（）()［］[]｛｝{}【】《》〈〉「」『』…‥—–ー_")


def _vertical_columns(text, font, cell, available_height):
    # OCR line breaks represent source columns, not independent paragraphs.
    # Keep explicit blank-line paragraphs; reflow single newlines in reading order.
    paragraphs = [re.sub(r"(?<=[A-Za-z0-9])\n(?=[A-Za-z0-9])", " ", p).replace("\n", "")
                  for p in text.split("\n\n")]
    columns = []
    for paragraph in paragraphs:
        units = []
        for token in re.findall(r"[A-Za-z0-9]+(?:[._+\-][A-Za-z0-9]+)*|.", paragraph):
            bbox = font.getbbox(token)
            glyph = Image.new("L", (max(1, bbox[2]-bbox[0]), max(1, bbox[3]-bbox[1])), 0)
            ImageDraw.Draw(glyph).text((-bbox[0], -bbox[1]), token, font=font, fill=255)
            sideways = (len(token) > 1 and token[0].isascii() and token[0].isalnum()) or token in _VERTICAL_ROTATE
            if sideways:
                glyph = glyph.transpose(Image.Transpose.ROTATE_270)
            advance = max(cell, glyph.height + math.ceil(cell * .1)) if sideways and len(token) > 1 else cell
            if advance > available_height or glyph.width > cell:
                return None
            units.append((token, glyph, advance))
        current, used = [], 0
        for unit in units:
            if current and used + unit[2] > available_height:
                carry = []
                if unit[0] in _VERTICAL_CLOSERS or current[-1][0] in _VERTICAL_OPENERS:
                    carry = [current.pop()]
                    used -= carry[0][2]
                if not current or sum(u[2] for u in carry) + unit[2] > available_height:
                    return None
                columns.append(current)
                current, used = carry, sum(u[2] for u in carry)
            current.append(unit)
            used += unit[2]
        if current:
            columns.append(current)
    return columns


def _typeset(text, polygon, size, font_path, options, direction, safe_region=None, expand_region=False):
    box = _bounds(polygon, size)
    requested_polygon = polygon
    if safe_region:
        bounds, region_mask = safe_region
        if expand_region:
            box = bounds
            allowed = region_mask
        else:
            allowed = _poly_mask(_local_polygon(polygon, box), (box[2]-box[0], box[3]-box[1]))
            clipped = np.zeros_like(allowed)
            left, top = max(box[0], bounds[0]), max(box[1], bounds[1])
            right, bottom = min(box[2], bounds[2]), min(box[3], bounds[3])
            if right > left and bottom > top:
                clipped[top-box[1]:bottom-box[1], left-box[0]:right-box[0]] = region_mask[
                    top-bounds[1]:bottom-bounds[1], left-bounds[0]:right-bounds[0]]
            allowed &= clipped
        rect = _largest_rectangle(allowed)
        if rect is None:
            raise PipelineError("IMAGE_TEXT_OVERFLOW", "气泡安全区域无法容纳译文，已保留原图文字")
        box = (box[0]+rect[0], box[1]+rect[1], box[0]+rect[2], box[1]+rect[3])
        polygon = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    width, height = box[2] - box[0], box[3] - box[1]
    padding = options["padding"]
    available_width, available_height = width - padding * 2, height - padding * 2
    if available_width <= 0 or available_height <= 0:
        raise PipelineError("IMAGE_TEXT_OVERFLOW", "文字区域太小，无法回填译文")
    _check_glyphs(font_path, text)
    sizes = [options["font_size"]] if options["font_size"] else range(options["max_font_size"], options["min_font_size"] - 1, -1)
    allowed = _poly_mask(_local_polygon(polygon, box), (width, height))
    for font_size in sizes:
        font = ImageFont.truetype(str(font_path), font_size)
        layer = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(layer)
        line_height = max(1, math.ceil(font_size * 1.22))
        fits = True
        if direction == "vertical":
            columns = _vertical_columns(text, font, line_height, available_height)
            if not columns:
                continue
            total_width = len(columns) * line_height
            if total_width > available_width:
                continue
            common_top = (height - max(sum(u[2] for u in col) for col in columns)) / 2
            for col, units in enumerate(columns):
                x = (width + total_width) / 2 - (col + 1) * line_height
                y = common_top
                for token, glyph, advance in units:
                    left = x + (line_height - glyph.width) / 2
                    top = y + (advance - glyph.height) / 2
                    if token in "，。、．,.":
                        left = x + line_height * .78 - glyph.width / 2
                        top = y + line_height * .08
                    if (left < padding or left + glyph.width > width - padding
                            or top < padding or top + glyph.height > height - padding):
                        fits = False
                        break
                    layer.paste(glyph, (round(left), round(top)))
                    y += advance
                if not fits:
                    break
        else:
            lines = _wrap(text, font, available_width)
            if lines is None or len(lines) * line_height > available_height:
                continue
            y = (height - len(lines) * line_height) / 2
            for line in lines:
                bb = font.getbbox(line)
                x = (width - (bb[2] - bb[0])) / 2 - bb[0]
                if (x + bb[0] < padding or x + bb[2] > width - padding
                        or y < padding or y + bb[3] - bb[1] > height - padding):
                    fits = False
                    break
                draw.text((x, y - bb[1]), line, font=font, fill=255)
                y += line_height
        if not fits:
            continue
        ink = np.array(layer)
        if np.any((ink > 0) & (allowed == 0)):
            continue
        return box, layer, {"font_size": font_size, "direction": direction,
                            "font_path": str(font_path), "polygon": [list(p) for p in polygon],
                            "requested_polygon": [list(p) for p in requested_polygon],
                            "expanded_to_bubble": bool(expand_region and safe_region),
                            "safe_area": "closed_bubble" if safe_region else "ocr_polygon"}
    raise PipelineError("IMAGE_TEXT_OVERFLOW", "译文无法在最小字号以上完整放入区域，已保留原图文字")


def _text_mask(pixels, polygon, mode, safe_region=None, calibrated=False):
    raw_box = _bounds(polygon, pixels.size)
    short_side = min(raw_box[2] - raw_box[0], raw_box[3] - raw_box[1])
    # Small punctuation may be only partly inside a detector box. Inspect a
    # bounded neighborhood, then keep only connected foreground components
    # intersecting the OCR region. Do not erase arbitrary nearby marks.
    margin = min(24, max(8, math.ceil(short_side * .25) + 2))
    box = safe_region[0] if safe_region else _bounds(polygon, pixels.size, margin=margin)
    crop = np.array(pixels.crop(box).convert("RGBA"))
    if safe_region:
        # Only a complete, single-block bubble can use its whole interior.
        # This includes detached punctuation missed by a tight OCR box, while
        # component and boundary checks below still protect the balloon outline.
        inside = safe_region[1]
        ring = (inside > 0) & (cv2.erode(inside, np.ones((3, 3), np.uint8)) == 0)
    else:
        inside = _poly_mask(_local_polygon(polygon, box), (crop.shape[1], crop.shape[0]))
        # Detector boxes occasionally clip an antialiased stroke by one or two
        # pixels. Expand only the glyph-search region, never paint the whole box.
        search_boundary = cv2.dilate(inside, np.ones((5, 5), np.uint8))
        expanded = cv2.dilate(search_boundary, np.ones((7, 7), np.uint8))
        ring = (expanded > 0) & (search_boundary == 0)
    # At the image edge use the polygon boundary; ambiguous results remain unpainted.
    if np.count_nonzero(ring) < 8:
        ring = (inside > 0) & (cv2.erode(inside, np.ones((3, 3), np.uint8)) == 0)

    def grazes_boundary(labels, label):
        if not calibrated or safe_region:
            return False
        core = cv2.erode(inside, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
        overlap = (labels == label) & (inside > 0)
        return (not np.any((labels == label) & (core > 0))
                and np.count_nonzero(overlap) <= np.count_nonzero(inside) * .1)

    background = np.median(crop[ring], axis=0) if np.any(ring) else np.array([0, 0, 0, 0])
    if not safe_region and np.any(inside):
        # On a narrow caption between two panel rules the ring itself can be
        # mostly black. A dominant interior color must also occur in the ring
        # before it can replace that contaminated background estimate.
        interior_background = np.median(crop[inside > 0], axis=0)
        difference = np.max(np.abs(crop.astype(np.float32) - interior_background), axis=2)
        if (np.mean(difference[inside > 0] < 20) >= .65
                and np.any(ring) and np.mean(difference[ring] < 20) >= .25):
            background = interior_background
    if background[3] < 8 and np.mean(crop[ring, 3] < 8) > .9:
        foreground = crop[:, :, 3] > 8
        uniform = True
    else:
        colors = crop[:, :, :3].astype(np.float32)
        distances = np.max(np.abs(colors - background[:3]), axis=2)
        if not safe_region:
            # A nearby panel rule can cross the sampling ring while remaining
            # completely outside the detector polygon. Exclude only those
            # exterior, crop-spanning components from background estimation.
            # A stroke entering the actual text polygon still fails the normal
            # component check below, so this does not crop connected line art.
            external = (distances > 24) & (crop[:, :, 3] > 8)
            _, labels, external_stats, _ = cv2.connectedComponentsWithStats(external.astype(np.uint8), connectivity=8)
            touching_text = set(np.unique(labels[inside > 0]))
            filtered_ring = ring.copy()
            for label in np.unique(labels[ring]):
                if not label or (label in touching_text and not grazes_boundary(labels, label)):
                    continue
                x, y, w, h, _ = external_stats[label]
                if x == 0 or y == 0 or x + w == crop.shape[1] or y + h == crop.shape[0]:
                    filtered_ring &= labels != label
            if np.count_nonzero(filtered_ring) >= max(8, np.count_nonzero(ring) * .4):
                ring = filtered_ring
                background = np.median(crop[ring], axis=0)
                distances = np.max(np.abs(colors - background[:3]), axis=2)
        ring_distance = distances[ring]
        uniform = bool(len(ring_distance) and np.quantile(ring_distance, .85) < 20 and background[3] > 245)
        if not uniform and mode != "inpaint":
            raise PipelineError("IMAGE_BACKGROUND_COMPLEX", "文字周围背景不够均匀，已保留原区域供复核")
        foreground = (distances > 24) & (crop[:, :, 3] > 8)
    _, components, stats, _ = cv2.connectedComponentsWithStats(foreground.astype(np.uint8), connectivity=8)
    seeded = np.unique(components[(inside > 0) & foreground])
    seeded = seeded[seeded != 0]
    candidate = np.zeros(foreground.shape, dtype=bool)
    for label in seeded:
        x, y, width, height, _ = stats[label]
        # A line-art component continuing out of the local neighborhood must
        # not be followed or partly erased as if it were a text glyph.
        if x == 0 or y == 0 or x + width == crop.shape[1] or y + height == crop.shape[0]:
            # A local detector may include the last raster row of a neighboring
            # frame. Leave that component untouched; do not grant this tolerance
            # to unverified provider boxes or to anything entering the text core.
            if grazes_boundary(components, label):
                continue
            raise PipelineError("IMAGE_TEXT_MASK_UNCERTAIN", "文字与邻近图案连通或超出检测范围，已保留原区域")
        candidate |= components == label
    count = np.count_nonzero(candidate)
    density = count / max(1, np.count_nonzero(inside))
    if count < 2 or density > .65:
        raise PipelineError("IMAGE_TEXT_MASK_UNCERTAIN", "无法可靠分离原文字像素，已保留原区域")
    mask = cv2.dilate(candidate.astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    # The only pixels outside the OCR region are connected glyph strokes and
    # their one-pixel antialias fringe; the rectangle itself is never painted.
    return box, mask, tuple(int(round(v)) for v in background), uniform


def _ocr_geometry_analysis(pixels, items):
    """Reject demonstrably inconsistent OCR without inventing missing text.

    Closed light bubbles provide a useful independent completeness check: all
    isolated ink components inside them should intersect at least one OCR line.
    Page backgrounds and textured/illustrated regions are not treated as bubbles.
    """
    issues, records, safe_regions = {}, [], {}
    for item in items:
        try:
            fallback = [{"polygon": (item.locator or {}).get("polygon")}]
            lines = ((item.extra or {}).get("ocr") or {}).get("lines") or fallback
            for line in lines:
                points = polygon_points(line.get("polygon"), pixels.size)
                hull = cv2.convexHull(np.array(points, dtype=np.float32))
                records.append((item.item_id, points, hull, cv2.contourArea(hull)))
        except (PipelineError, AttributeError, TypeError):
            continue  # The normal per-item validator reports malformed geometry.
    for index, (item_id, _, hull, area) in enumerate(records):
        for other_id, _, other_hull, other_area in records[index + 1:]:
            overlap, _ = cv2.intersectConvexConvex(hull, other_hull)
            if overlap >= .5 * min(area, other_area):
                error = PipelineError("IMAGE_OCR_REGIONS_CONFLICT", "不同 OCR 文字行区域严重重叠，已保留原区域，请复核识别坐标")
                issues[item_id] = issues[other_id] = error
    rgba = np.asarray(pixels.convert("RGBA"))
    bright = ((rgba[:, :, :3].min(axis=2) >= 225) & (rgba[:, :, 3] > 245)).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    height, width = bright.shape
    bubbles = {}
    for record in records:
        x0, y0, x1, y1 = _bounds(record[1], pixels.size)
        roi = labels[y0:y1, x0:x1]
        ids, counts = np.unique(roi, return_counts=True)
        if not len(ids):
            continue
        label = int(ids[np.argmax(counts)])
        x, y, w, h, area = stats[label]
        if (label and x > 0 and y > 0 and x + w < width and y + h < height
                and area >= max(64, roi.size * 1.2) and max(counts) >= roi.size * .5
                and w * h <= width * height * .2):
            bubbles.setdefault(label, []).append(record)
    for label, bubble_records in bubbles.items():
        x, y, w, h, area = stats[label]
        background = (labels[y:y+h, x:x+w] == label).astype(np.uint8)
        contours, _ = cv2.findContours(background, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(background)
        cv2.drawContours(filled, contours, -1, 1, cv2.FILLED)
        filled_area = np.count_nonzero(filled)
        if not filled_area or area < filled_area * .72 or filled_area < w * h * .4:
            continue
        # Closed white scene backgrounds can enclose large parts of a panel.
        # Their deep concavities distinguish them from a balloon (including
        # its small tail). Do not treat their line art as missing OCR text.
        hull_area = cv2.contourArea(cv2.convexHull(np.vstack(contours)))
        contour_area = sum(cv2.contourArea(contour) for contour in contours)
        if not hull_area or contour_area < hull_area * .85:
            continue
        interior = cv2.erode(filled, np.ones((5, 5), np.uint8))
        for item_id, _, _, _ in bubble_records:
            safe_regions[item_id] = ((int(x), int(y), int(x+w), int(y+h)), interior * 255)
        foreground = interior & (1 - bright[y:y+h, x:x+w])
        count, ink_labels, ink_stats, _ = cv2.connectedComponentsWithStats(foreground, connectivity=8)
        seed = np.zeros_like(background)
        # A tight OCR box around a bold letter can contain less than 50%
        # background and miss the bubble-assignment heuristic. Its actual
        # coordinates still count as coverage inside this bubble.
        for _, points, _, _ in records:
            seed |= _poly_mask([(px-x, py-y) for px, py in points], (w, h))
        seed = cv2.dilate(seed, np.ones((5, 5), np.uint8))
        covered = set(np.unique(ink_labels[seed > 0]))
        total, missing = 0, 0
        for component in range(1, count):
            _, _, cw, ch, component_area = ink_stats[component]
            if component_area < 3 or cw < 2 or ch < 2:
                continue
            total += component_area
            if component not in covered:
                missing += component_area
        if missing > max(12, total * .08):
            for item_id, _, _, _ in bubble_records:
                issues.setdefault(item_id, PipelineError(
                    "IMAGE_OCR_INCOMPLETE_BUBBLE", "气泡内仍有未被 OCR 定位的文字或图案，已保留整个区域，请复核识别结果"))
    return issues, safe_regions


def _ocr_geometry_issues(pixels, items):
    return _ocr_geometry_analysis(pixels, items)[0]


def _single_block_bubble(item_id, safe_region, items, size):
    """Allow whole-interior erasure only when no other OCR block owns ink there."""
    if not safe_region:
        return None
    box, mask = safe_region
    for other in items:
        if other.item_id == item_id:
            # A grouped item must belong wholly to this one bubble. Otherwise
            # the last bubble found for its lines could swallow text from an
            # earlier bubble during whole-interior erasure and reflow.
            own_lines = ((other.extra or {}).get("ocr") or {}).get("lines") or [other.locator or {}]
            for line in own_lines:
                try:
                    points = polygon_points(line.get("polygon"), size)
                except PipelineError:
                    return None
                coverage = _poly_mask(_local_polygon(points, box), (mask.shape[1], mask.shape[0]))
                area = abs(cv2.contourArea(np.asarray(points, dtype=np.float32)))
                if np.count_nonzero((coverage > 0) & (mask > 0)) < area * .9:
                    return None
            continue
        try:
            points = polygon_points((other.locator or {}).get("polygon"), size)
        except PipelineError:
            return None
        other_mask = _poly_mask(_local_polygon(points, box), (mask.shape[1], mask.shape[0]))
        if np.any((other_mask > 0) & (mask > 0)):
            return None
    return safe_region


def _automatic_layout(polygon, region, lines, size):
    """Keep manually adjusted item/paragraph geometry authoritative."""
    polygons = [polygon_points(line.get("polygon"), size) for line in lines]
    if not polygons:
        return False
    if len(polygons) == 1:
        derived = polygons[0]
    else:
        points = [point for line in polygons for point in line]
        x0, y0 = min(p[0] for p in points), min(p[1] for p in points)
        x1, y1 = max(p[0] for p in points), max(p[1] for p in points)
        derived = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return polygon == region == derived


def _source_font_limit(lines, options):
    """Estimate line scale geometrically; region OCR need not supply line text."""
    widths = [min(cv2.minAreaRect(np.asarray(line["polygon"], dtype=np.float32))[1]) for line in lines]
    suggested = round(float(np.median(widths)) * .85)
    return min(options["max_font_size"], max(options["min_font_size"], suggested))


def prepare_image_plan(pixels, cache_file, options, context):
    """Validate a complete repair/typesetting plan without changing source pixels.

    Font/layout preflight deliberately precedes erasure: a block which cannot
    receive its translation must retain its original ink in the repaired image.
    """
    result = pixels.convert("RGBA")
    union = Image.new("L", result.size, 0)
    debug = result.copy()
    debug_draw = ImageDraw.Draw(debug)
    warnings, rendered, skipped, placements, preserved, planned = [], 0, 0, [], [], []
    unready = {item.item_id for item in cache_file.items
               if ((item.extra or {}).get("ocr") or {}).get("status") in ("pending", "failed")}
    unchanged = {item.item_id for item in cache_file.items
                 if item.item_id not in unready
                 and item.translation_status in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED)
                 and (item.source_text or "").strip()
                 and item.source_text.replace("\r\n", "\n").replace("\r", "\n").strip()
                 == (item.translated_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()}
    excluded = {item.item_id for item in cache_file.items
                if item.translation_status == TranslationStatus.EXCLUDED and item.item_id not in unready}
    retained = unchanged | excluded
    font_path = find_font(options["font_path"]) if len(retained | unready) < len(cache_file.items) else None
    font_hash = file_sha256(font_path) if font_path else None
    occupied = np.zeros((result.height, result.width), dtype=np.uint8)
    protected = np.zeros_like(occupied)
    for item in cache_file.items:
        if item.item_id in retained | unready:
            try:
                points = polygon_points((item.locator or {}).get("polygon"), result.size)
                protected |= _poly_mask(points, result.size)
            except PipelineError:
                pass  # Report invalid coordinates through the usual item path.
    protected = cv2.dilate(protected, np.ones((5, 5), np.uint8))
    geometry_issues, safe_regions = _ocr_geometry_analysis(pixels, cache_file.items)
    for item in cache_file.items:
        if context.is_cancelled():
            break
        try:
            locator = item.locator or {}
            if locator.get("kind") != "image":
                raise PipelineError("INVALID_IMAGE_LOCATOR", "图片条目缺少 image 定位")
            polygon = polygon_points(locator.get("polygon"), result.size)
            debug_draw.polygon(polygon, outline=(0, 130, 255, 255), width=2)
            if item.item_id in unready:
                raise PipelineError("IMAGE_OCR_REQUIRED", "该文字块尚未完成 OCR，已保留原图文字")
            if item.item_id in retained:
                preserved.append({"item_id": item.item_id,
                                  "reason": "excluded" if item.item_id in excluded else "source_unchanged"})
                continue
            if item.translation_status not in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED) or not (item.translated_text or "").strip():
                raise PipelineError("IMAGE_UNTRANSLATED", "片段尚无有效译文，已保留原图文字")
            if item.item_id in geometry_issues:
                raise geometry_issues[item.item_id]
            text = item.translated_text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").strip()
            if any(ord(c) < 32 and c != "\n" for c in text):
                raise PipelineError("IMAGE_INVALID_TEXT", "译文包含不支持的控制字符")
            extra = item.extra or {}
            layout = extra.get("layout") or {}
            region = polygon_points(layout.get("polygon", polygon), result.size)
            direction = options["text_direction"]
            if direction == "auto":
                direction = layout.get("direction", "horizontal")
            if direction not in ("horizontal", "vertical"):
                direction = "horizontal"
            original_lines = (extra.get("ocr") or {}).get("lines")
            lines = original_lines or [{"polygon": polygon}]
            if not isinstance(lines, list):
                raise PipelineError("INVALID_IMAGE_POLYGON", "OCR 文字行格式无效")
            whole_bubble = _single_block_bubble(item.item_id, safe_regions.get(item.item_id), cache_file.items, result.size)
            expand_region = bool(original_lines and whole_bubble and _automatic_layout(polygon, region, lines, result.size))
            typeset_options = options
            if expand_region and options["font_size"] is None:
                typeset_options = {**options, "max_font_size": _source_font_limit(lines, options)}
            box, ink, placement = _typeset(text, region, result.size, font_path, typeset_options, direction,
                                         safe_regions.get(item.item_id), expand_region=expand_region)
            if np.any((np.array(ink) > 0) & ((occupied | protected)[box[1]:box[3], box[0]:box[2]] > 0)):
                raise PipelineError("IMAGE_REGIONS_OVERLAP", "译文排版区域相互重叠，保留该区域供复核")
            if whole_bubble:
                masks = [_text_mask(pixels, polygon, options["erase_mode"], safe_region=whole_bubble)]
            else:
                local_geometry = (extra.get("ocr") or {}).get("recognition_scope") == "region"
                masks = [_text_mask(pixels, polygon_points(line.get("polygon"), result.size), options["erase_mode"],
                                    calibrated=local_geometry or bool(line.get("provider_polygon"))) for line in lines]
            # Prevent a later OCR block from erasing previously rendered output.
            for mb, mask, _, _ in masks:
                if np.any((mask > 0) & ((occupied | protected)[mb[1]:mb[3], mb[0]:mb[2]] > 0)):
                    raise PipelineError("IMAGE_REGIONS_OVERLAP", "文字区域相互重叠，保留该区域供复核")
                if item.item_id in safe_regions:
                    safe_box, safe_mask = safe_regions[item.item_id]
                    allowed = np.zeros(mask.shape, dtype=np.uint8)
                    left, top = max(mb[0], safe_box[0]), max(mb[1], safe_box[1])
                    right, bottom = min(mb[2], safe_box[2]), min(mb[3], safe_box[3])
                    if right > left and bottom > top:
                        allowed[top-mb[1]:bottom-mb[1], left-mb[0]:right-mb[0]] = safe_mask[
                            top-safe_box[1]:bottom-safe_box[1], left-safe_box[0]:right-safe_box[0]]
                    if np.any((mask > 0) & (allowed == 0)):
                        raise PipelineError("IMAGE_TEXT_MASK_UNCERTAIN", "擦字区域接近或越出气泡边界，已保留原区域")
            if options["erase_mode"] != "inpaint":
                # Open/ambiguous bubbles may not yield a closed contour. Even
                # there, translated ink must not cover unrecognized line art.
                erased = np.zeros((box[3]-box[1], box[2]-box[0]), dtype=np.uint8)
                for mb, mask, _, _ in masks:
                    left, top = max(box[0], mb[0]), max(box[1], mb[1])
                    right, bottom = min(box[2], mb[2]), min(box[3], mb[3])
                    if right > left and bottom > top:
                        erased[top-box[1]:bottom-box[1], left-box[0]:right-box[0]] |= mask[
                            top-mb[1]:bottom-mb[1], left-mb[0]:right-mb[0]]
                original = np.asarray(pixels.crop(box).convert("RGBA"), dtype=np.int16)
                bg = np.asarray(masks[0][2], dtype=np.int16)
                unexpected = ((np.max(np.abs(original[:, :, :3] - bg[:3]), axis=2) > 32)
                              | (np.abs(original[:, :, 3] - bg[3]) > 24))
                if bg[3] < 8:
                    unexpected = original[:, :, 3] > 8
                if np.any((np.asarray(ink) > 0) & (erased == 0) & unexpected):
                    raise PipelineError("IMAGE_LAYOUT_UNSAFE", "译文排版会覆盖未识别的原字或线稿，已保留原区域")
            for mb, mask, background, uniform in masks:
                current_mask = np.array(union.crop(mb))
                union.paste(Image.fromarray(np.maximum(current_mask, mask)), (mb[0], mb[1]))
                if not uniform:
                    warnings.append({"item_id": item.item_id, "code": "IMAGE_INPAINT_REVIEW", "message": "已按显式 inpaint 模式处理复杂背景，请复核修复效果"})
            bg = masks[0][2]
            color = options["font_color"] or ("#ffffff" if sum(bg[:3]) < 384 and bg[3] > 128 else "#000000")
            occupied[box[1]:box[3], box[0]:box[2]] = np.maximum(occupied[box[1]:box[3], box[0]:box[2]], np.array(ink))
            placements.append({"item_id": item.item_id, **placement, "color": color, "font_sha256": font_hash})
            planned.append({"item_id": item.item_id, "box": box, "ink": ink, "color": color, "masks": masks})
            rendered += 1
        except PipelineError as error:
            warnings.append({"item_id": item.item_id, "code": error.code, "message": error.message})
            skipped += 1
    return {"size": pixels.size, "source_mode": pixels.mode, "items": planned, "mask": union, "debug": debug,
            "report": {"rendered_items": rendered, "skipped_items": skipped,
                       "preserved_items": len(preserved), "preserved": preserved,
                       "warnings": warnings, "placements": placements, "cancelled": context.is_cancelled()}}


def repair_image(pixels, plan, options, context):
    """Apply only the validated erasure/inpainting masks; never paint translations."""
    result = pixels.convert("RGBA")
    for entry in plan["items"]:
        if context.is_cancelled():
            break
        for box, mask, background, _ in entry["masks"]:
            crop = result.crop(box)
            if options["erase_mode"] == "inpaint" and background[3] > 245:
                array = np.array(crop)
                array[:, :, :3] = cv2.inpaint(array[:, :, :3], mask, 3, cv2.INPAINT_TELEA)
                crop = Image.fromarray(array)
            else:
                crop.paste(background, (0, 0, crop.width, crop.height), Image.fromarray(mask))
            result.paste(crop, (box[0], box[1]))
    return result.convert("RGB") if plan["source_mode"] == "RGB" else result


def paint_image(repaired, plan, context):
    """Compose validated text layers onto an already repaired image, without erasure."""
    if tuple(repaired.size) != tuple(plan["size"]):
        raise PipelineError("IMAGE_REPAIR_STALE", "修复图尺寸与文字渲染计划不一致", 409)
    result = repaired.convert("RGBA")
    for entry in plan["items"]:
        if context.is_cancelled():
            break
        box, ink = entry["box"], entry["ink"]
        fill = Image.new("RGBA", ink.size, ImageColor.getcolor(entry["color"], "RGBA"))
        result.paste(fill, (box[0], box[1]), ink)
    return result.convert("RGB") if plan["source_mode"] == "RGB" else result


def render_image(pixels, cache_file, options, context):
    """Compatibility helper for callers needing both independent pixel stages."""
    plan = prepare_image_plan(pixels, cache_file, options, context)
    repaired = repair_image(pixels, plan, options, context)
    rendered = paint_image(repaired, plan, context)
    return rendered, plan["mask"], plan["debug"], {**plan["report"], "cancelled": context.is_cancelled()}
