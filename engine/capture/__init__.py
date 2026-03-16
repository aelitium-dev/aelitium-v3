"""
AELITIUM capture layer — SDK adapters that close the trust gap.

Instead of packing manually-written JSON, capture adapters intercept
real LLM calls and pack the request+response automatically.

Usage:
    from engine.capture.openai import capture_chat_completion
    from engine.capture.openai import capture_chat_completion_stream
    from engine.capture.anthropic import capture_message
    from engine.capture.litellm import capture_completion
    from engine.capture.log import EvidenceLog
"""
from .openai import capture_chat_completion, capture_chat_completion_stream, CaptureResult

try:
    from .anthropic import capture_message as capture_anthropic_message
    __all__ = ["capture_chat_completion", "capture_chat_completion_stream", "CaptureResult", "capture_anthropic_message"]
except ImportError:
    __all__ = ["capture_chat_completion", "capture_chat_completion_stream", "CaptureResult"]
