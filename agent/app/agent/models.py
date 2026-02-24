"""Model factory for LangChain ChatAnthropic instances."""

from langchain_anthropic import ChatAnthropic

from app.config import Settings


def get_primary_model(settings: Settings) -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.primary_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )


def get_verification_model(settings: Settings) -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.verification_model,
        api_key=settings.anthropic_api_key,
        max_tokens=2048,
    )
