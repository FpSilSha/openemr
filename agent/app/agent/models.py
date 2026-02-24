"""Model factory for LangChain ChatAnthropic instances."""

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from app.config import Settings


def get_primary_model(settings: Settings) -> ChatAnthropic:
    return ChatAnthropic(  # type: ignore[call-arg]
        model_name=settings.primary_model,
        anthropic_api_key=SecretStr(settings.anthropic_api_key),
        max_tokens_to_sample=4096,
    )


def get_verification_model(settings: Settings) -> ChatAnthropic:
    return ChatAnthropic(  # type: ignore[call-arg]
        model_name=settings.verification_model,
        anthropic_api_key=SecretStr(settings.anthropic_api_key),
        max_tokens_to_sample=2048,
    )
