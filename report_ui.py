"""Public interface for the fixed, approved AI-risk dashboard renderer."""
from ui_data import (
    AXES, CHANGES, LEVELS, RULES_VERSION, UI_VERSION,
    adapt_legacy, classify, esc, validate,
)
from ui_render import build_html

__all__ = [
    'AXES', 'CHANGES', 'LEVELS', 'RULES_VERSION', 'UI_VERSION',
    'adapt_legacy', 'classify', 'esc', 'validate', 'build_html',
]
