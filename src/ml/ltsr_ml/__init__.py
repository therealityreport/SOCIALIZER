"""
SOCIALIZER ML package exposing training and inference utilities.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("ltsr_ml")
except PackageNotFoundError:  # pragma: no cover - package metadata optional
    __version__ = "0.0.0"

__all__ = ["__version__"]
