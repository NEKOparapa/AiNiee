"""Protect EPUB links and anchors while translating their surrounding text.

The cache contains the trusted HTML represented by each token. Model output is
always escaped; only these saved fragments are allowed to become markup.
"""

import copy
import html
import re
from collections.abc import Callable

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


TOKEN_RE = re.compile(r"⟦EPUB_\d+⟧")
EPUB_TOKEN_INSTRUCTION = (
    "EPUB tokens such as ⟦EPUB_0001⟧ represent protected links and markup. "
    "Copy every token exactly once, in its original order and at the corresponding "
    "position in the translated text. Do not translate, delete, duplicate, or invent tokens."
)
_TOKEN_START = "⟦EPUB_"
_LITERAL_TOKEN_RE = re.compile(r"⟦EPUB_(?:[^⟦⟧\r\n]*⟧)?")
_NOTE_LABEL_RE = re.compile(r"[\s\d\[\](){}.*†‡§¶#※⁎⁑⁂¹²³⁴⁵⁶⁷⁸⁹⁰]+")


def validate_tokens(source_text: str, target_text: str) -> bool:
    """Require the same tokens exactly once and in their original nesting order."""
    source_tokens = TOKEN_RE.findall(source_text)
    target_tokens = TOKEN_RE.findall(target_text)
    if not source_tokens:
        # This check also runs for other file formats. Their ordinary text may
        # contain the reserved prefix without containing any EPUB placeholders.
        return not target_tokens
    return (
        source_tokens == target_tokens
        and target_text.count(_TOKEN_START) == len(target_tokens)
    )


def transform_plain_text(text: str, transform: Callable[[str], str]) -> str:
    """Apply a text transform without exposing EPUB tokens to replacement rules."""
    parts = []
    start = 0
    for match in TOKEN_RE.finditer(text):
        parts.append(transform(text[start:match.start()]))
        parts.append(match.group())
        start = match.end()
    parts.append(transform(text[start:]))
    return "".join(parts)


def has_link_or_anchor(tag: Tag) -> bool:
    return bool(
        tag.has_attr("id")
        or tag.has_attr("xml:id")
        or (tag.name == "a" and (tag.has_attr("href") or tag.has_attr("name")))
    )


def is_note_reference(tag: Tag) -> bool:
    """Recognize note markers, leaving descriptive links available to translate."""
    if tag.name != "a" or "#" not in str(tag.get("href", "")):
        return False
    label = tag.get_text().strip()
    if not label or _NOTE_LABEL_RE.fullmatch(label):
        return True
    semantics = " ".join(
        [str(tag.get("epub:type", "")), str(tag.get("role", ""))]
        + list(tag.get("class", []))
    ).lower()
    # A short alphabetic note label (a, iv) or return arrow is also structural.
    # Longer text such as "see note" still needs translation.
    return len(label) <= 4 and any(
        kind in semantics for kind in ("noteref", "backlink", "footnotelink", "footnoteanchor")
    )


def _is_note_container(tag: Tag) -> bool:
    """Keep a note's superscript/span and return-anchor ID in one atomic token."""
    if is_note_reference(tag):
        return True
    if tag.name not in {"span", "sup", "sub", "b", "i", "em", "strong"}:
        return False
    children = [child for child in tag.children if isinstance(child, Tag) or str(child).strip()]
    return len(children) == 1 and isinstance(children[0], Tag) and _is_note_container(children[0])


def protect_fragment(original_html: str) -> tuple[str, dict[str, str]]:
    """Return translatable text and a JSON-serializable token-to-HTML mapping.

    The outer element is retained by the writer. Inside linked fragments we
    preserve all tags, so anchors nested in spans and note return links survive
    together with their original formatting. Ordinary fragments stay token-free.
    """
    soup = BeautifulSoup(original_html, "html.parser")
    root = soup.find()
    if root is None:
        return soup.get_text().strip(), {}

    protect_markup = any(has_link_or_anchor(tag) for tag in root.find_all(True))
    if not protect_markup and _TOKEN_START not in root.get_text():
        return root.get_text().strip(), {}

    placeholders = {}
    next_index = 1

    def token(fragment: str) -> str:
        nonlocal next_index
        while True:
            marker = f"⟦EPUB_{next_index:04d}⟧"
            next_index += 1
            if marker not in original_html:
                break
        placeholders[marker] = fragment
        return marker

    def plain_text(text: str) -> str:
        # A literal token in the book must not collide with generated markers.
        return _LITERAL_TOKEN_RE.sub(lambda match: token(html.escape(match.group(), quote=False)), text)

    def walk(node) -> str:
        if isinstance(node, Comment):
            return token(str(node.output_ready()))
        if isinstance(node, NavigableString):
            return plain_text(str(node))
        if not isinstance(node, Tag):
            return ""
        if not protect_markup:
            return "".join(walk(child) for child in node.children)
        if node.is_empty_element or not node.contents or _is_note_container(node):
            return token(str(node))

        shell = copy.copy(node)
        shell.clear()
        closing = f"</{node.name}>"
        serialized_shell = str(shell)
        opening = serialized_shell[:-len(closing)]
        opening_token = token(opening)
        children = "".join(walk(child) for child in node.children)
        return opening_token + children + token(closing)

    return "".join(walk(child) for child in root.children).strip(), placeholders


def restore_fragment_text(text: str, placeholders: dict[str, str]) -> str:
    """Restore trusted inner HTML, rejecting lost, added, or reordered tokens."""
    if not validate_tokens("".join(placeholders), text):
        raise ValueError("EPUB 链接占位符缺失、重复或顺序错误")
    parts = []
    start = 0
    for match in TOKEN_RE.finditer(text):
        parts.append(html.escape(text[start:match.start()], quote=False))
        parts.append(placeholders[match.group()])
        start = match.end()
    parts.append(html.escape(text[start:], quote=False))
    return "".join(parts)
