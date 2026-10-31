"""Keep BabelDOC importable without dependencies of unused features."""
import importlib.util
import sys


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
