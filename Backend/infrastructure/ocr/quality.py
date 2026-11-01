"""Conservative text-only OCR acceptance anchored to original line geometry."""
from difflib import SequenceMatcher
import unicodedata

VALIDATION_VERSION = 1


def _normalized(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def validate_refinement(lines, provider_text):
    originals = [line["text"].strip() for line in lines]
    outputs = [line.strip() for line in provider_text.splitlines() if line.strip()]
    source = [_normalized(line) for line in originals]
    target = [_normalized(line) for line in outputs]
    validation = {"version": VALIDATION_VERSION, "status": "rejected", "reason": "",
                  "reordered": False, "source_line_count": len(source), "output_line_count": len(target), "line_matches": []}

    def reject(reason):
        return {"text": None, "validation": {**validation, "reason": reason}}

    if not source or not all(source) or len(source) > 200:
        return reject("invalid_source_lines")
    if len(source) != len(target):
        return reject("line_count_mismatch")
    if sum(map(len, target)) < .85 * sum(map(len, source)):
        return reject("text_shrunk")
    if sum(map(len, target)) > 1.3 * sum(map(len, source)):
        return reject("text_expanded")
    if source == target:
        validation.update(status="accepted", reason="equivalent_text", line_matches=[
            {"source_index": i, "output_index": i, "similarity": 1.0} for i in range(len(source))])
        return {"text": "\n".join(outputs), "validation": validation}
    if len(set(target)) != len(target):
        return reject("repeated_output_lines")
    matches, used = [], set()
    for index, value in enumerate(target):
        ranked = sorted(((SequenceMatcher(None, old, value, autojunk=False).ratio(), old_index)
                         for old_index, old in enumerate(source)), reverse=True)
        similarity, old_index = ranked[0]
        old = source[old_index]
        if (similarity < .7 or min(len(old), len(value)) < .75 * max(len(old), len(value))
                or (min(len(old), len(value)) <= 2 and old != value)):
            return reject("unreliable_line_match")
        if len(ranked) > 1 and similarity - ranked[1][0] < .12:
            return reject("ambiguous_line_match")
        if old_index in used:
            return reject("duplicate_line_assignment")
        used.add(old_index)
        matches.append({"source_index": old_index, "output_index": index, "similarity": round(similarity, 4)})
    matches.sort(key=lambda match: match["source_index"])
    validation.update(status="accepted", reason="matched_original_lines",
                      reordered=any(match["source_index"] != match["output_index"] for match in matches), line_matches=matches)
    return {"text": "\n".join(outputs[match["output_index"]] for match in matches), "validation": validation}
