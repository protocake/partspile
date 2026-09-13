from __future__ import annotations

from ..config import Config


def get_provider(cfg: Config):
    if cfg.provider == "claude_code":
        from .claude_code import ClaudeCodeProvider
        return ClaudeCodeProvider(cfg)
    if cfg.provider == "anthropic":
        from .anthropic_ import AnthropicProvider
        return AnthropicProvider(cfg)
    if cfg.provider == "openai_compat":
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(cfg)
    if cfg.provider == "ollama":
        from .ollama_native import OllamaNativeProvider
        return OllamaNativeProvider(cfg)
    raise ValueError(f"Unknown provider: {cfg.provider}")
