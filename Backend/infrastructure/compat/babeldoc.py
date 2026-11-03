"""Keep BabelDOC importable without dependencies of unused features."""
import importlib.util
from importlib.metadata import PackageNotFoundError, version
import sys


def ensure_pdf_runtime():
    """Reject unvalidated native PDF runtimes before they can abort the backend."""
    from Backend.application.pipeline_common import PipelineError

    # Keep aligned with requirements-backend.txt. PyMuPDF 1.28.0 crashes in
    # get_pixmap on real inputs; that native heap error cannot be caught in Python.
    required = "1.26.7"
    try:
        installed = version("pymupdf")
    except PackageNotFoundError as error:
        raise PipelineError("CAPABILITY_UNAVAILABLE", "PDF 读取需要安装 pymupdf==1.26.7", 503) from error
    if installed != required:
        raise PipelineError(
            "PDF_DEPENDENCY_INCOMPATIBLE",
            f"PDF 解析需要 PyMuPDF {required}，当前为 {installed}。"
            f"请在后端 Python 环境安装 pymupdf=={required} 后重启后端。",
            503,
        )


def ensure_skimage():
    # Prefer an installed scikit-image. Do not hide errors in an installed but
    # broken package by replacing it with the limited compatibility module.
    if "skimage" in sys.modules or importlib.util.find_spec("skimage") is not None:
        return
    from Backend.infrastructure.compat import skimage
    from Backend.infrastructure.compat.skimage import metrics

    sys.modules["skimage"] = skimage
    sys.modules["skimage.metrics"] = metrics


def ensure_hyperscan():
    if "hyperscan" in sys.modules or importlib.util.find_spec("hyperscan") is not None:
        return
    from Backend.infrastructure.compat import hyperscan

    sys.modules["hyperscan"] = hyperscan


def ensure_optional_imports():
    ensure_skimage()
    ensure_hyperscan()
