"""
Public API for the aelitium package.

Usage:
    from aelitium import capture_chat_completion, CaptureResult
    from aelitium import EvidenceLog
    from aelitium import export_eu_ai_act_art12

Optional extras:
    pip install aelitium[openai]     # OpenAI capture adapter
    pip install aelitium[anthropic]  # Anthropic capture adapter
    pip install aelitium[all]        # All adapters
"""
from engine.capture.openai import capture_chat_completion, capture_chat_completion_stream, CaptureResult
from engine.capture.log import EvidenceLog
from engine.compliance import export_eu_ai_act_art12

try:
    from engine.capture.anthropic import capture_message as capture_anthropic_message
    __all_anthropic__ = ["capture_anthropic_message"]
except ImportError:
    def capture_anthropic_message(*args, **kwargs):
        raise ImportError(
            "Anthropic adapter requires the 'anthropic' package. "
            "Install it with: pip install aelitium[anthropic]"
        )
    __all_anthropic__ = []

__version__ = "0.2.2"

__all__ = [
    "capture_chat_completion",
    "capture_chat_completion_stream",
    "CaptureResult",
    "EvidenceLog",
    "export_eu_ai_act_art12",
    "capture_anthropic_message",
]
