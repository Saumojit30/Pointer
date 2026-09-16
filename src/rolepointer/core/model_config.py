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
        self._server_root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        logger.info(f"[ModelConfig] Initialized Local Ollama Model: {model_id} @ {self.base_url}")

    def discover_local_models(self) -> list[str]:
        """Queries Ollama /api/tags to list available downloaded model weights."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self._server_root}/api/tags")
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    return [m.get("name", "") for m in models if m.get("name")]
        except Exception as e:
            logger.debug(f"[Ollama] Local /api/tags inspection note: {e}")
        return []

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

    def invoke(self, prompt: str) -> str:
        return self.generate(prompt)


class LMStudioStrandsModel:
    """Local LM Studio adapter compatible with OpenAI drop-in completion protocol."""

    def __init__(self, model_id: str = "local-model", base_url: str = "http://localhost:1234/v1"):
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        logger.info(f"[ModelConfig] Initialized Local LM Studio Model: {model_id} @ {self.base_url}")

    def discover_loaded_models(self) -> list[str]:
        """Queries LM Studio /v1/models to list active loaded models."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/models")
                if res.status_code == 200:
                    models = res.json().get("data", [])
                    return [m.get("id", "") for m in models if m.get("id")]
        except Exception as e:
            logger.debug(f"[LMStudio] Local /v1/models inspection note: {e}")
        return []

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
                logger.warning(f"LM Studio returned HTTP {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"LM Studio invocation failed: {e}")
        return ""

    def invoke(self, prompt: str) -> str:
        return self.generate(prompt)


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


class GCPGeminiStrandsModel:
    """Official Google Cloud (GCP) Gemini client supporting both Google AI Studio and Vertex AI."""

    def __init__(
        self,
        model_id: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        location: str = "us-central1",
        use_vertex_ai: bool = False,
    ):
        self.model_id = model_id
        self.api_key = api_key
        self.project = project
        self.location = location
        self.use_vertex_ai = use_vertex_ai
        self._genai_client = None

        # 1. Official google-genai SDK
        try:
            from google import genai  # type: ignore
            if use_vertex_ai and project:
                self._genai_client = genai.Client(vertexai=True, project=project, location=location)
                logger.info(f"[GCP] Initialized Vertex AI Client (project={project}, location={location}, model={model_id})")
            elif api_key:
                self._genai_client = genai.Client(api_key=api_key)
                logger.info(f"[GCP] Initialized AI Studio Client (model={model_id})")
        except Exception as e:
            logger.debug(f"[GCP] google-genai SDK load note: {e}")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Try google-genai client
        if self._genai_client:
            try:
                config: dict[str, Any] = {}
                if system_prompt:
                    config["system_instruction"] = system_prompt
                res = self._genai_client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=config if config else None,
                )
                if res and hasattr(res, "text") and res.text:
                    return res.text
            except Exception as e:
                logger.warning(f"[GCP] google-genai generation note: {e}")

        # Official Google AI Studio REST API
        if self.api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent?key={self.api_key}"
                body: dict[str, Any] = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
                }
                if system_prompt:
                    body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "")
                    logger.warning(f"[GCP] Gemini REST API returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.warning(f"[GCP] Gemini REST API invocation failed: {e}")

        return ""

    def invoke(self, prompt: str) -> str:
        return self.generate(prompt)


def get_strands_model() -> Any:
    """Returns Strands BedrockModel, GCP Gemini, or Ollama fallback."""
    provider = settings.llm_provider.lower().strip()
    has_aws_keys = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    has_gemini_keys = bool(settings.gemini_api_key or (settings.use_vertex_ai and settings.google_cloud_project))

    # Explicit or auto-detected Bedrock
    if provider == "bedrock" or (provider == "auto" and has_aws_keys and not settings.use_local_model):
        return BedrockStrandsModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            aws_session_token=settings.aws_session_token or None,
        )

    # Explicit or auto-detected Google Cloud / Gemini
    if provider in ("gemini", "gcp", "vertex") or (provider == "auto" and has_gemini_keys and not settings.use_local_model):
        return GCPGeminiStrandsModel(
            model_id=settings.gemini_model,
            api_key=settings.gemini_api_key or None,
            project=settings.google_cloud_project or None,
            location=settings.google_cloud_location,
            use_vertex_ai=settings.use_vertex_ai,
        )

    # Explicit LM Studio
    if provider in ("lmstudio", "lm_studio"):
        return LMStudioStrandsModel(
            model_id=settings.local_model_name,
            base_url=settings.lm_studio_base_url,
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
