"""
Renderer package — modular planset rendering engine.
=====================================================

This package decomposes the monolithic HtmlRenderer into:
  - svg_helpers:     shared color palette, SVG utility functions
  - title_block:     reusable SVG title block generator
  - page_builders/:  individual page builder modules (one per sheet)

The main HtmlRenderer class (html_renderer.py) orchestrates page assembly
and will progressively delegate to these modules.
"""

from renderer.svg_helpers import COLORS, PAGE_WIDTH, PAGE_HEIGHT, svg_page_wrapper
from renderer.title_block import svg_title_block

__all__ = [
    "COLORS",
    "PAGE_WIDTH",
    "PAGE_HEIGHT",
    "svg_page_wrapper",
    "svg_title_block",
]
