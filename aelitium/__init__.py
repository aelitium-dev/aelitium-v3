"""
Public API for the aelitium package.

Usage:
    from aelitium import capture_chat_completion, CaptureResult
    from aelitium import EvidenceLog
    from aelitium import export_eu_ai_act_art12
"""
from engine.capture.openai import capture_chat_completion, capture_chat_completion_stream, CaptureResult
from engine.capture.log import EvidenceLog
from engine.compliance import export_eu_ai_act_art12

try:
    from engine.capture.anthropic import capture_message as capture_anthropic_message
except ImportError:
    pass

__version__ = "0.2.1"

__all__ = [
    "capture_chat_completion",
    "capture_chat_completion_stream",
    "CaptureResult",
    "EvidenceLog",
    "export_eu_ai_act_art12",
]
