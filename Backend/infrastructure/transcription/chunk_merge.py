"""Conservative, time-constrained alignment of overlapping ASR chunks.

This reconciles recognition hypotheses, not ground truth. Core-side coverage
and nearby alignment anchors resolve competing overlap hypotheses. Uncovered
words are retained with a warning; speakers remain local to each chunk.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import unicodedata

from Backend.application.pipeline_common import PipelineError


def _invalid(message):
    return PipelineError("ASR_INVALID_CHUNK_RESULT", message, 502)


def _field(chunk, name):
    return chunk[name] if isinstance(chunk, Mapping) else getattr(chunk, name)


def _interval(start, end, duration):
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration:
        raise _invalid("切片转录时间戳超出音频范围")
    return start, end


def _normalized(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    letters = "".join(char for char in text if unicodedata.category(char)[0] not in "PZC")
    return letters or text.strip()


@dataclass
class _Unit:
    text: str
    start: int
    end: int
    chunk: int
    segment: int
    speaker: str | None
    fine: bool
    owned: bool
    audio_start: int
    audio_end: int
    selected: bool = True

    @property
    def middle(self):
        return (self.start + self.end) / 2


@dataclass
class _Span:
    units: tuple
    text: str

    @property
    def start(self):
        return self.units[0].start

    @property
    def end(self):
        return max(unit.end for unit in self.units)

    @property
    def middle(self):
        return (self.start + self.end) / 2


def _spans(units):
    """Bounded adjacent groups; keep original words and their actual timings."""
    endings = [[] for _ in range(len(units) + 1)]
    for end in range(1, len(units) + 1):
        for count in range(1, min(4, end) + 1):
            group = tuple(units[end - count:end])
            if any(a.speaker != b.speaker or b.start - a.end >= 800 for a, b in zip(group, group[1:])):
                break
            endings[end].append(_Span(group, _normalized("".join(unit.text for unit in group))))
    return endings


def _alignment(left, right):
    """Monotone 1..4-to-1..4 word alignment constrained by actual audio time.

    Japanese word tokenization can change between chunks. Match whole adjacent
    groups without inventing per-character timing. Prefer finer matches when
    equal amounts of text align, then minimize drift to protect real repetitions.
    """
    scores = [[(0, 0, 0)] * (len(right) + 1) for _ in range(len(left) + 1)]
    left_spans, right_spans = _spans(left), _spans(right)
    moves = {}
    for i in range(1, len(left) + 1):
        for j in range(1, len(right) + 1):
            best, move = (scores[i - 1][j], "left") if scores[i - 1][j] >= scores[i][j - 1] else (scores[i][j - 1], "right")
            for first in left_spans[i]:
                for second in right_spans[j]:
                    if not first.text or first.text != second.text:
                        continue
                    gap = max(first.start, second.start) - min(first.end, second.end)
                    distance = abs(first.middle - second.middle)
                    if distance <= 750 and gap <= 250:
                        chars, groups, drift = scores[i - len(first.units)][j - len(second.units)]
                        match = chars + len(first.text), groups + 1, drift - distance
                        if match > best:
                            best, move = match, (first, second)
            scores[i][j], moves[i, j] = best, move
    pairs = []
    i, j = len(left), len(right)
    while i and j:
        move = moves[i, j]
        if isinstance(move, tuple):
            first, second = move
            pairs.append(move)
            i, j = i - len(first.units), j - len(second.units)
        elif move == "left":
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    accepted = []
    for index, (first, second) in enumerate(pairs):
        intersection = min(first.end, second.end) - max(first.start, second.start)
        # An isolated identical word needs substantial temporal overlap. Weak
        # overlap needs a second aligned token with consistent timing drift.
        strong = intersection >= min(first.end - first.start, second.end - second.start) / 2
        shift = second.middle - first.middle
        supported = any(abs((b.middle - a.middle) - shift) <= 200
                        and abs(a.middle - first.middle) <= 1500
                        for a, b in pairs[max(0, index - 1):index] + pairs[index + 1:index + 2])
        if strong or supported:
            accepted.append((first.units, second.units))
    return accepted


def _covered_conflicts(source, other, anchors, aligned_units):
    """Discard a non-core alternative only when core words cover its audio.

    An adjacent exact alignment establishes both timing drift and the local
    speaker correspondence. Coverage is measured against original word times;
    an anchor alone is insufficient, so unique unrecognized tails survive.
    """
    discarded = []
    for unit in source:
        if not unit.selected or unit.owned or id(unit) in aligned_units or not unit.text.strip():
            continue
        nearby = []
        for source_anchor, other_anchor in anchors:
            source_start = source_anchor[0].start
            source_end = max(word.end for word in source_anchor)
            gap = max(unit.start, source_start) - min(unit.end, source_end)
            if gap > 1500 or source_anchor[0].speaker != unit.speaker:
                continue
            source_middle = (source_start + source_end) / 2
            other_middle = (other_anchor[0].start + max(word.end for word in other_anchor)) / 2
            nearby.append((abs(unit.middle - source_middle), other_middle - source_middle, other_anchor[0].speaker))
        for _, drift, speaker in sorted(nearby, key=lambda candidate: candidate[0]):
            expected_start, expected_end = unit.start + drift, unit.end + drift
            intervals = sorted((max(expected_start, candidate.start), min(expected_end, candidate.end))
                               for candidate in other if candidate.selected and candidate.owned
                               and candidate.speaker == speaker and candidate.text.strip()
                               and candidate.end > expected_start and candidate.start < expected_end)
            coverage, cursor = 0, expected_start
            for start, end in intervals:
                coverage += max(0, end - max(cursor, start))
                cursor = max(cursor, end)
            if coverage >= (unit.end - unit.start) * 0.6:
                unit.selected = False
                discarded.append(unit)
                break
    return discarded


def merge_chunk_results(chunks, results, *, duration_ms):
    if type(duration_ms) is not int or duration_ms <= 0 or not isinstance(results, Mapping):
        raise _invalid("切片拼接参数无效")
    layouts = []
    try:
        for chunk in chunks:
            index = _field(chunk, "index")
            start, end = _interval(_field(chunk, "start_ms"), _field(chunk, "end_ms"), duration_ms)
            core_start, core_end = _interval(_field(chunk, "core_start_ms"), _field(chunk, "core_end_ms"), duration_ms)
            if type(index) is not int or index < 0 or not start <= core_start < core_end <= end:
                raise _invalid("切片编号或核心区间无效")
            layouts.append((index, start, end, core_start, core_end))
    except (KeyError, AttributeError, TypeError):
        raise _invalid("切片描述缺少必要字段") from None
    layouts.sort(key=lambda layout: layout[3])
    if len({row[0] for row in layouts}) != len(layouts) or any(a[4] > b[3] for a, b in zip(layouts, layouts[1:])):
        raise _invalid("切片编号重复或核心区间重叠")
    warnings, units = [], []
    report = {"chunk_count": len(layouts), "merged_chunk_count": 0, "missing_chunk_indexes": [],
              "aligned_duplicate_words": 0, "discarded_conflicting_words": 0,
              "preserved_ambiguous_words": 0, "coarse_boundary_segments": 0}
    by_chunk = {}
    for index, start, end, core_start, core_end in layouts:
        if index not in results:
            report["missing_chunk_indexes"].append(index)
            warnings.append({"code": "ASR_CHUNK_MISSING", "message": "部分音频切片没有转录结果，已保留可用片段", "chunk_index": index})
            continue
        result = results[index]
        if not isinstance(result, Mapping) or not isinstance(result.get("segments"), list):
            raise _invalid("切片缺少有效转录结果")
        report["merged_chunk_count"] += 1
        chunk_units = []
        for ordinal, segment in enumerate(result["segments"]):
            if not isinstance(segment, Mapping) or not isinstance(segment.get("text"), str):
                raise _invalid("切片转录文本无效")
            local_start, local_end = _interval(segment.get("start_ms"), segment.get("end_ms"), end - start)
            words = segment.get("words")
            if words is not None and not isinstance(words, list):
                raise _invalid("切片词时间戳列表无效")
            fine = bool(words)
            if fine and any(not isinstance(word, Mapping) or not isinstance(word.get("text"), str) for word in words):
                raise _invalid("切片词文本无效")
            if fine and "".join(segment["text"].split()) != "".join("".join(word["text"] for word in words).split()):
                fine = False
                warnings.append({"code": "ASR_CHUNK_WORD_COVERAGE", "message": "词列表未覆盖完整文本，已保留原句", "chunk_index": index})
            speaker = segment.get("speaker_id")
            if speaker is not None and (not isinstance(speaker, (str, int)) or isinstance(speaker, bool)):
                raise _invalid("切片说话人标识无效")
            speaker = f"chunk{index}:{speaker}" if speaker is not None else None
            previous = -1
            for word in words if fine else [segment]:
                word_start, word_end = _interval(word.get("start_ms"), word.get("end_ms"), end - start)
                if fine and not local_start <= word_start < word_end <= local_end:
                    raise _invalid("词时间戳超出所属句子范围")
                if word_start < previous:
                    raise _invalid("切片词时间戳顺序无效")
                previous = word_start
                global_start, global_end = start + word_start, start + word_end
                owned = core_start <= (global_start + global_end) / 2 < core_end
                unit = _Unit(word["text"], global_start, global_end, index, ordinal, speaker, fine, owned, start, end)
                units.append(unit)
                chunk_units.append(unit)
        by_chunk[index] = chunk_units
        for warning in result.get("warnings", []):
            if isinstance(warning, Mapping):
                warnings.append({**warning, "chunk_index": index})
    aligned_units, conflicting_chunks, resolved_chunks = set(), set(), set()
    for first, second in zip(layouts, layouts[1:]):
        overlap_start, overlap_end = max(first[1], second[1]), min(first[2], second[2])
        if overlap_start >= overlap_end:
            continue
        left = [unit for unit in by_chunk.get(first[0], []) if unit.fine and unit.start < overlap_end and unit.end > overlap_start]
        right = [unit for unit in by_chunk.get(second[0], []) if unit.fine and unit.start < overlap_end and unit.end > overlap_start]
        pairs = _alignment(left, right)
        for a, b in pairs:
            # Choose a complete original group, never synthetic character times.
            # A matched group can cross the core boundary on either side.
            def quality(group):
                middle = (group[0].start + max(unit.end for unit in group)) / 2
                return (sum(unit.owned for unit in group) / len(group),
                        min(middle - group[0].audio_start, group[0].audio_end - middle), -group[0].chunk)

            winner = max((a, b), key=quality)
            loser = b if winner is a else a
            for unit in winner:
                unit.selected = True
            for unit in loser:
                unit.selected = False
            aligned_units.update(id(unit) for unit in a + b)
            report["aligned_duplicate_words"] += len(loser)
        discarded = (_covered_conflicts(left, right, pairs, aligned_units)
                     + _covered_conflicts(right, left, [(b, a) for a, b in pairs], aligned_units))
        if discarded:
            resolved_chunks.update((first[0], second[0]))
            report["discarded_conflicting_words"] += len(discarded)
        if any(a.selected and b.selected and id(a) not in aligned_units and id(b) not in aligned_units
               and (min(a.end, b.end) > max(a.start, b.start)
                    or (_normalized(a.text) == _normalized(b.text)
                        and abs(a.middle - b.middle) <= 750
                        and max(a.start, b.start) - min(a.end, b.end) <= 250))
               for a in left for b in right):
            conflicting_chunks.update((first[0], second[0]))
    ambiguous_chunks, coarse_chunks = conflicting_chunks, set()
    layouts_by_index = {layout[0]: layout for layout in layouts}
    for unit in units:
        if not unit.selected:
            continue
        if not unit.owned and id(unit) not in aligned_units and unit.text.strip():
            # No matching hypothesis: dropping a token solely because its time
            # drifted across the core cut can lose real words. Keep and disclose.
            report["preserved_ambiguous_words"] += int(unit.fine)
            ambiguous_chunks.add(unit.chunk)
        layout = layouts_by_index[unit.chunk]
        if not unit.fine and (unit.start < layout[3] or unit.end > layout[4]):
            report["coarse_boundary_segments"] += 1
            coarse_chunks.add(unit.chunk)
    if ambiguous_chunks:
        warnings.append({"code": "ASR_CHUNK_BOUNDARY_UNCERTAIN", "message": "边界内容无法可靠对齐，已保守保留，可能包含重复或识别差异", "chunk_indexes": sorted(ambiguous_chunks)})
    if resolved_chunks:
        warnings.append({"code": "ASR_CHUNK_BOUNDARY_RESOLVED", "message": "重叠区存在识别差异，已依据相邻词对齐和音频时间覆盖保留核心区结果，请复核边界", "chunk_indexes": sorted(resolved_chunks)})
    if coarse_chunks:
        warnings.append({"code": "ASR_CHUNK_COARSE_BOUNDARY", "message": "跨边界句子缺少完整词时间戳，已保留原句，未强行裁剪", "chunk_indexes": sorted(coarse_chunks)})
    selected = sorted((unit for unit in units if unit.selected), key=lambda unit: (unit.start, unit.end, unit.chunk, unit.segment))
    segments, current, previous_unit = [], None, None
    for unit in selected:
        same_segment = previous_unit is not None and (unit.chunk, unit.segment) == (previous_unit.chunk, previous_unit.segment)
        if current is None or not (unit.fine and previous_unit.fine and same_segment and unit.start - previous_unit.end < 800):
            current = {"text": unit.text, "start_ms": unit.start, "end_ms": unit.end, "speaker_id": unit.speaker}
            if unit.fine:
                current["words"] = []
            segments.append(current)
        else:
            current["text"] += unit.text
            current["end_ms"] = max(current["end_ms"], unit.end)
        if unit.fine:
            current["words"].append({"text": unit.text, "start_ms": unit.start, "end_ms": unit.end, "speaker_id": unit.speaker})
        previous_unit = unit
    for segment in segments:
        segment["text"] = segment["text"].strip()
    segments = [segment for segment in segments if segment["text"]]
    return {"text": "\n".join(segment["text"] for segment in segments), "segments": segments,
            "warnings": warnings, "report": report}
