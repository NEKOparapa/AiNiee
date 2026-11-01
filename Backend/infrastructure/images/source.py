"""Canonical EXIF-oriented image pixels shared by image operations."""
from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.files.pipeline_support import file_sha256

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
MAX_PIXELS = 80_000_000


def load_image(path):
    path = Path(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened:
                if opened.format not in ("PNG", "JPEG", "WEBP"):
                    raise PipelineError("UNSUPPORTED_IMAGE_FORMAT", "只支持静态 PNG、JPEG 和 WebP 图片")
                if getattr(opened, "n_frames", 1) != 1:
                    raise PipelineError("ANIMATED_IMAGE_UNSUPPORTED", "当前仅支持静态图片")
                if opened.width * opened.height > MAX_PIXELS:
                    raise PipelineError("IMAGE_TOO_LARGE", "图片超过 8000 万像素限制")
                raw_size = opened.size
                orientation = opened.getexif().get(274, 1)
                has_alpha = opened.mode in ("RGBA", "LA") or "transparency" in opened.info
                pixels = ImageOps.exif_transpose(opened).convert("RGBA" if has_alpha else "RGB")
                pixels.load()
                metadata = {"width": pixels.width, "height": pixels.height,
                            "raw_width": raw_size[0], "raw_height": raw_size[1],
                            "exif_orientation": orientation if type(orientation) is int else 1,
                            "coordinate_space": "exif_oriented_pixel", "color_mode": pixels.mode,
                            "has_alpha": has_alpha, "format": opened.format.lower(),
                            "size_bytes": path.stat().st_size}
                return pixels, metadata
    except PipelineError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise PipelineError("IMAGE_READ_FAILED", "无法解码图片或图片尺寸不安全") from error


def verified_image(cache_file):
    ref = cache_file.source_ref or {}
    try:
        path = Path(ref.get("path", "")).expanduser().resolve(strict=True)
        expected = ref.get("sha256")
        if not path.is_file() or not expected or file_sha256(path) != expected:
            raise PipelineError("SOURCE_CHANGED", "图片源文件不存在、未校验或已发生变化")
        pixels, metadata = load_image(path)
        if file_sha256(path) != expected:
            raise PipelineError("SOURCE_CHANGED", "读取期间图片源文件发生变化")
        declared = cache_file.media_metadata or {}
        if (declared.get("width"), declared.get("height")) != (metadata["width"], metadata["height"]):
            raise PipelineError("IMAGE_SIZE_MISMATCH", "中间模型图片尺寸与规范化原图不一致")
        return pixels, path
    except PipelineError:
        raise
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise PipelineError("IMAGE_SOURCE_UNAVAILABLE", "图片源文件不可访问") from error
