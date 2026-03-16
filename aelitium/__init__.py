"""
Public API for the aelitium package.

Usage:
    from aelitium import capture_openai, CaptureResult
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

# Convenience aliases — preferred public API
capture_openai = capture_chat_completion

try:
    from engine.capture.anthropic import capture_message as capture_anthropic_message
    capture_anthropic = capture_anthropic_message
    __all_anthropic__ = ["capture_anthropic_message", "capture_anthropic"]
except ImportError:
    def capture_anthropic_message(*args, **kwargs):
        raise ImportError(
            "Anthropic adapter requires the 'anthropic' package. "
            "Install it with: pip install aelitium[anthropic]"
        )
    capture_anthropic = capture_anthropic_message
    __all_anthropic__ = []

try:
    from engine.capture.litellm import capture_completion as capture_litellm_completion
    capture_litellm = capture_litellm_completion
except ImportError:
    def capture_litellm_completion(*args, **kwargs):
        raise ImportError(
            "LiteLLM adapter requires the 'litellm' package. "
            "Install it with: pip install aelitium[litellm]"
        )
    capture_litellm = capture_litellm_completion

__version__ = "0.2.4"

__all__ = [
    "capture_openai",
    "capture_anthropic",
    "capture_litellm",
    "capture_chat_completion",
    "capture_chat_completion_stream",
    "capture_anthropic_message",
    "capture_litellm_completion",
    "CaptureResult",
    "EvidenceLog",
    "export_eu_ai_act_art12",
]
