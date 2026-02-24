"""AgentForge configuration — loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "agentforge-openemr"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # OpenEMR connection
    openemr_base_url: str = "http://openemr:80"
    openemr_api_url: str = "http://openemr:80/apis/default"
    openemr_fhir_url: str = "http://openemr:80/apis/default/fhir"
    openemr_username: str = "admin"
    openemr_password: str = "pass"
    openemr_verify_ssl: bool = True

    # Models
    primary_model: str = "claude-sonnet-4-20250514"
    verification_model: str = "claude-opus-4-20250514"

    # Agent settings
    agent_port: int = 8000
    frontend_port: int = 3000
    tool_timeout_seconds: float = 30.0

    # Optional
    pubmed_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
