"""Conservative page reading order; panel detection never changes erase masks."""


def bounds(region):
    xs, ys = zip(*region["polygon"])
    return min(xs), min(ys), max(xs), max(ys)


def reading_order(regions, *, rtl):
    """Recursive whitespace cuts: rows first, then columns in reading order.

    Unlike globally sorting X, this finishes the upper panel row before a
    lower panel at the right edge. A panel spanning multiple rows prevents a
    horizontal cut, so the encompassing column is read as a unit.
    """
    if len(regions) < 2:
        return list(regions)
    boxes = {id(region): bounds(region) for region in regions}
    for axis in (1, 0):
        intervals = sorted((box[axis], box[axis + 2]) for box in boxes.values())
        end, gaps = intervals[0][1], []
        for start, stop in intervals[1:]:
            if start > end:
                gaps.append((start - end, (start + end) / 2))
            end = max(end, stop)
        if not gaps:
            continue
        middle = (intervals[0][0] + max(stop for _, stop in intervals)) / 2
        _, cut = max(gaps, key=lambda gap: (gap[0], -abs(gap[1] - middle)))
        before = [r for r in regions if boxes[id(r)][axis + 2] <= cut]
        after = [r for r in regions if boxes[id(r)][axis] >= cut]
        if not before or not after or len(before) + len(after) != len(regions):
            continue
        halves = (after, before) if axis == 0 and rtl else (before, after)
        return [r for half in halves for r in reading_order(half, rtl=rtl)]
    # Overlapping/irregular regions have no clean separating whitespace. Read
    # the upper region first; exact ties follow the selected column direction.
    return sorted(regions, key=lambda r: (boxes[id(r)][1], -boxes[id(r)][2] if rtl else boxes[id(r)][0]))


def _rows(regions, *, rtl):
    """Within a panel, overlapping balloons form a row before lower captions."""
    remaining = sorted(regions, key=lambda region: (bounds(region)[1], bounds(region)[0]))
    result = []
    while remaining:
        first = remaining.pop(0)
        a = bounds(first)
        row, rest = [first], []
        for region in remaining:
            b = bounds(region)
            overlap = min(a[3], b[3]) - max(a[1], b[1])
            (row if overlap >= .5 * min(a[3] - a[1], b[3] - b[1]) else rest).append(region)
        result.extend(sorted(row, key=lambda region: -bounds(region)[2] if rtl else bounds(region)[0]))
        remaining = rest
    return result


def panel_regions(image):
    """Find large framed regions, excluding contained bubble/art contours.

    At least three sides must contain a nearly continuous dark frame. A panel
    cropped at the image edge may have two opposite sides. This is a reading
    order hint, not a claim that arbitrary comics have rectangular panels.
    """
    import cv2
    import numpy as np
    from PIL import Image

    scale = min(1.0, 2048 / max(image.size))
    thumbnail = image.convert("L")
    if scale < 1:
        thumbnail = thumbnail.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    ink = np.asarray(thumbnail) < 128
    height, width = ink.shape
    contours, _ = cv2.findContours(ink.astype("uint8"), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    band = max(2, round(min(width, height) / 250))
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        if area < width * height * .02 or w < width * .12 or h < height * .08:
            continue
        edges = [np.any(ink[y:y + band, x:x + w], axis=0).mean(),
                 np.any(ink[y + h - band:y + h, x:x + w], axis=0).mean(),
                 np.any(ink[y:y + h, x:x + band], axis=1).mean(),
                 np.any(ink[y:y + h, x + w - band:x + w], axis=1).mean()]
        cropped = x <= 1 or y <= 1 or x + w >= width - 1 or y + h >= height - 1
        opposite = (edges[0] >= .85 and edges[1] >= .85) or (edges[2] >= .85 and edges[3] >= .85)
        if sum(edge >= .8 for edge in edges) < 3 and not (cropped and opposite and area / (w * h) >= .6):
            continue
        candidates.append((x, y, x + w, y + h))
    # Bubble contours can share two panel edges. Keep only the enclosing frame,
    # not its nested speech balloon or a duplicate contour on the other edge.
    kept = []
    for box in sorted(candidates, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True):
        if any(box[0] >= outer[0] - band and box[1] >= outer[1] - band
               and box[2] <= outer[2] + band and box[3] <= outer[3] + band for outer in kept):
            continue
        kept.append(box)
    sx, sy = image.width / width, image.height / height
    return [{"polygon": [[x0 * sx, y0 * sy], [x1 * sx, y0 * sy], [x1 * sx, y1 * sy], [x0 * sx, y1 * sy]]}
            for x0, y0, x1, y1 in kept]


def order_page(regions, image, *, rtl):
    """Order blocks by detected frame, then by whitespace within each frame."""
    if len(regions) < 2:
        return list(regions)
    panels = panel_regions(image)
    if len(panels) < 2:
        return reading_order(regions, rtl=rtl)
    containers = [{**panel, "regions": []} for panel in panels]
    loose = []
    for region in regions:
        x0, y0, x1, y1 = bounds(region)
        area = max(1, (x1 - x0) * (y1 - y0))
        best, overlap = None, 0
        for container in containers:
            a, b, c, d = bounds(container)
            coverage = max(0, min(x1, c) - max(x0, a)) * max(0, min(y1, d) - max(y0, b)) / area
            if coverage > overlap:
                best, overlap = container, coverage
        if best is not None and overlap >= .7:
            best["regions"].append(region)
        else:
            loose.append({"polygon": region["polygon"], "regions": [region]})
    occupied = [container for container in containers if container["regions"]] + loose
    return [region for container in reading_order(occupied, rtl=rtl)
            for region in _rows(container["regions"], rtl=rtl)]
