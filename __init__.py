"""Top-level package for pixel_img_downscaler."""

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]

__author__ = """comfyui-pixel-img-downscaler"""
__email__ = "feishengfei@126.com"
__version__ = "0.0.1"

from .src.pixel_img_downscaler.nodes import NODE_CLASS_MAPPINGS
from .src.pixel_img_downscaler.nodes import NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"
