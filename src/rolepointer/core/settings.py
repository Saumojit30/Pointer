"""
RolePointer — Application Settings
Loads all environment variables through pydantic-settings.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Provider Selector ("auto" | "bedrock" | "gemini" | "ollama" | "lmstudio")
    llm_provider: str = "auto"

    # AWS Bedrock (Official SDK & Boto3 Converse API)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Google Cloud (GCP) & Gemini (Official google-genai SDK & Vertex AI)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_application_credentials: str = ""
    use_vertex_ai: bool = False

    # Local Ollama Fallback
    use_local_model: bool = False
    local_model_name: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434/v1"

    # Database
    database_url: str = "sqlite:///rolepointer.db"

    # Server & Runtime
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    use_mock_feeds: bool = False
    log_level: str = "INFO"


settings = Settings()
