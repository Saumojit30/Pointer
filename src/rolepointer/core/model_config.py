"""
RolePointer — Strands Model Gateway
Supports AWS Bedrock (default) with native local Ollama fallback for 100% offline usage.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional
import httpx
from loguru import logger

from rolepointer.core.settings import settings


class OllamaStrandsModel:
    """Local Ollama adapter compatible with OpenAI/Strands completion protocol."""

    def __init__(self, model_id: str = "llama3.2", base_url: str = "http://localhost:11434/v1"):
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        logger.info(f"[ModelConfig] Initialized Local Ollama Model: {model_id} @ {self.base_url}")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model_id,
                        "messages": messages,
                        "temperature": 0.2,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                logger.warning(f"Ollama returned HTTP {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"Ollama invocation failed: {e}")
        return ""


class BedrockStrandsModel:
    """Official AWS Bedrock client adapter using boto3 converse API and Strands SDK."""

    def __init__(
        self,
        model_id: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        self.model_id = model_id
        self.region_name = region_name
        self._client = None
        self._strands_model = None

        # Attempt Strands BedrockModel
        try:
            from strands.models import BedrockModel  # type: ignore
            self._strands_model = BedrockModel(model_id=model_id, region_name=region_name)
        except Exception as e:
            logger.debug(f"[Bedrock] Strands BedrockModel direct load note: {e}")

        # Official Boto3 Bedrock Runtime Client (Converse API)
        try:
            import boto3
            client_kwargs: dict[str, Any] = {"region_name": region_name}
            if aws_access_key_id and aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = aws_access_key_id
                client_kwargs["aws_secret_access_key"] = aws_secret_access_key
                if aws_session_token:
                    client_kwargs["aws_session_token"] = aws_session_token
            self._client = boto3.client("bedrock-runtime", **client_kwargs)
            logger.info(f"[Bedrock] Initialized Bedrock Runtime Client for model {model_id} in {region_name}")
        except Exception as e:
            logger.warning(f"[Bedrock] Could not initialize boto3 bedrock-runtime client: {e}")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Try Strands model first
        if self._strands_model and hasattr(self._strands_model, "generate"):
            try:
                res = self._strands_model.generate(prompt, system_prompt)
                if res:
                    return res
            except Exception as e:
                logger.debug(f"[Bedrock] Strands generate fallback: {e}")

        # Official Boto3 Converse API
        if self._client:
            try:
                params: dict[str, Any] = {
                    "modelId": self.model_id,
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"temperature": 0.2, "maxTokens": 2048},
                }
                if system_prompt:
                    params["system"] = [{"text": system_prompt}]
                response = self._client.converse(**params)
                output_message = response.get("output", {}).get("message", {})
                content_blocks = output_message.get("content", [])
                if content_blocks and "text" in content_blocks[0]:
                    return content_blocks[0]["text"]
            except Exception as e:
                logger.warning(f"[Bedrock] Converse API invocation note: {e}")
        return ""

    def invoke(self, prompt: str) -> str:
        return self.generate(prompt)


def get_strands_model() -> Any:
    """Returns Strands BedrockModel or Ollama fallback."""
    provider = settings.llm_provider.lower().strip()
    has_aws_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)

    if provider == "bedrock" or (provider == "auto" and has_aws_keys and not settings.use_local_model):
        return BedrockStrandsModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            aws_session_token=settings.aws_session_token or None,
        )

    # Local Ollama Fallback
    return OllamaStrandsModel(
        model_id=settings.local_model_name,
        base_url=settings.ollama_base_url,
    )


def generate_llm_response(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Utility helper for agents to generate structured text."""
    model = get_strands_model()
    if hasattr(model, "generate"):
        return model.generate(prompt, system_prompt)
    if hasattr(model, "invoke"):
        try:
            return model.invoke(prompt)
        except Exception:
            pass
    return ""
