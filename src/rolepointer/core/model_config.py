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


def get_strands_model() -> Any:
    """Returns Strands BedrockModel or Ollama fallback."""
    if settings.use_local_model or os.getenv("USE_LOCAL_MODEL", "false").lower() == "true":
        return OllamaStrandsModel(
            model_id=settings.local_model_name,
            base_url=settings.ollama_base_url,
        )

    # AWS Bedrock via Strands SDK
    try:
        from strands.models import BedrockModel  # type: ignore
        return BedrockModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_region,
        )
    except Exception as e:
        logger.debug(f"Strands BedrockModel direct load note: {e}")
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
