"""
Author: Noah Masegosa Caceres
Center: @ugr

Objective: File that encapsulates the LLM interaction logic for the Input Agent.
This file contains the classes and methods to interact with the LLM, send prompts, and process responses.

"""

import contextlib
import hashlib
import json
import os
import threading
import time

from openai import OpenAI

try:
    from anthropic import Anthropic
except ModuleNotFoundError:
    Anthropic = None


_raw_capture = threading.local()


@contextlib.contextmanager
def capture_raw_responses():
    """
    Record every LLM call this thread makes inside the block: finish reason,
    raw response text and, when the server returns it, the reasoning.
    Logging only: requests are built exactly as without it.
    """
    records = []
    previous = getattr(_raw_capture, "records", None)
    _raw_capture.records = records
    try:
        yield records
    finally:
        _raw_capture.records = previous


def _describe_raw_call(mode, chat_completion, error):
    record = {
        "finish_reason": None,
        "content": None,
        "reasoning": None,
        "reasoning_field": None,
        "message_extra_keys": [],
        "model": None,
        "usage": None,
        "error": None if error is None else str(error),
    }
    if chat_completion is None:
        return record

    record["model"] = getattr(chat_completion, "model", None)
    record["usage"] = LLMService._normalize_usage(getattr(chat_completion, "usage", None))

    if mode == "anthropic":
        blocks = getattr(chat_completion, "content", None) or []
        record["finish_reason"] = getattr(chat_completion, "stop_reason", None)
        record["content"] = "".join(getattr(b, "text", None) or "" for b in blocks)
        thinking = [getattr(b, "thinking", None) for b in blocks]
        record["reasoning"] = "\n".join(t for t in thinking if t) or None
        record["reasoning_field"] = "thinking" if record["reasoning"] else None
        return record

    choice = chat_completion.choices[0]
    message = choice.message
    record["finish_reason"] = choice.finish_reason
    record["content"] = message.content
    extra = dict(getattr(message, "model_extra", None) or {})
    record["message_extra_keys"] = sorted(extra)
    for field in ("reasoning", "reasoning_content", "thinking"):
        if extra.get(field):
            record["reasoning"] = extra[field]
            record["reasoning_field"] = field
            break
    record["system_fingerprint"] = getattr(chat_completion, "system_fingerprint", None)
    return record


def _record_raw_call(mode, chat_completion, error=None, request_kwargs=None):
    records = getattr(_raw_capture, "records", None)
    if records is None:
        return
    try:
        record = _describe_raw_call(mode, chat_completion, error)
        if request_kwargs is not None:
            messages = request_kwargs.get("messages") or []
            system = request_kwargs.get("system")
            if system is None and messages and messages[0].get("role") == "system":
                system = messages[0].get("content")
            record["request"] = {
                "params": {k: v for k, v in request_kwargs.items() if k not in ("messages", "system")},
                "system_sha256": None if system is None else hashlib.sha256(system.encode("utf-8")).hexdigest(),
            }
        records.append(record)
    except Exception as exc:  # logging must never change the outcome of a call
        records.append({"capture_error": str(exc)})


# Request formats of earlier versions of LLMService for openai_compatible
# servers, reproducible on demand (``request_profile`` or LLM_REQUEST_PROFILE).
# Without a profile the current format is used.
REQUEST_PROFILES = {
    # Commits 12e3297/6e07a45 (March 2026), which humanised both datasets: no
    # JSON suffix, JSON response format, no max_tokens unless given, no
    # extra_body, and the response parsed with json.loads alone.
    "2026-03-humaniser": {
        "json_suffix": False, "response_format": True, "default_max_tokens": None,
        "extra_body": False, "strict_json": True,
    },
    # Commit a224cae (28 April 2026), which ran the gpt-oss:20b benchmark: no
    # JSON suffix, no response format, max_tokens 4096 unless given,
    # extra_body from the environment, lenient JSON extraction.
    "2026-04-28-benchmark": {
        "json_suffix": False, "response_format": False, "default_max_tokens": 4096,
        "extra_body": True, "strict_json": False,
    },
}


class LLMService:
    def __init__(
        self,
        mode="openai_compatible",
        api_key=None,
        temperature=0,
        seed=None,
        model=None,
        base_url=None,
        timeout=None,
        max_tokens=None,
        extra_body=None,
        request_profile=None,
    ):
        """
        :param mode: Provider name or legacy alias. Preferred values:
                     "openai", "openai_compatible", "anthropic".
                     Legacy aliases "server" and "ollama" are accepted
                     and normalized to "openai_compatible".
        :param api_key: Provider API key.
        :param temperature: Temperature for the LLM.
        :param request_profile: Name in REQUEST_PROFILES to reproduce an earlier
                     request format (openai_compatible only); defaults to
                     LLM_REQUEST_PROFILE, else the current format.
        """
        provider_aliases = {
            "server": "openai_compatible",
            "ollama": "openai_compatible",
            "auto": "auto",
            "openai-compatible": "openai_compatible",
            "openai_compatible": "openai_compatible",
            "openai": "openai",
            "anthropic": "anthropic",
        }

        if mode in (None, "", "auto"):
            mode = os.getenv("BENCHMARK_LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "openai_compatible"

        if mode not in provider_aliases and api_key is None:
            api_key = mode
            mode = os.getenv("LLM_PROVIDER", os.getenv("BENCHMARK_LLM_PROVIDER", "openai_compatible"))

        self.mode = provider_aliases.get(mode, mode)
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self.max_tokens = max_tokens

        extra_body_env = os.getenv("LLM_EXTRA_BODY_JSON") or os.getenv("BENCHMARK_LLM_EXTRA_BODY_JSON")
        if extra_body is None and extra_body_env:
            try:
                extra_body = json.loads(extra_body_env)
            except json.JSONDecodeError as exc:
                raise ValueError("LLM_EXTRA_BODY_JSON must contain valid JSON") from exc
        self.extra_body = extra_body

        model_aliases = {
            "gpt-oss-20b": "gpt-oss:20b",
            "gpt-oss-120b": "gpt-oss:120b",
        }

        if self.mode == "openai":
            default_model_env = (
                os.getenv("OPENAI_MODEL")
                or os.getenv("LLM_MODEL")
                or os.getenv("BENCHMARK_LLM_MODEL")
            )
        elif self.mode == "anthropic":
            default_model_env = (
                os.getenv("ANTHROPIC_MODEL")
                or os.getenv("LLM_MODEL")
                or os.getenv("BENCHMARK_LLM_MODEL")
            )
        else:
            default_model_env = (
                os.getenv("OLLAMA_MODEL")
                or os.getenv("OPENAI_COMPATIBLE_MODEL")
                or os.getenv("LLM_MODEL")
                or os.getenv("BENCHMARK_LLM_MODEL")
            )

        if self.mode == "anthropic":
            if Anthropic is None:
                raise ModuleNotFoundError(
                    "anthropic is not installed. Install it with `pip install anthropic`."
                )
            anthropic_api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY (or LLM_API_KEY) is required for anthropic provider")

            anthropic_kwargs = {"api_key": anthropic_api_key}
            anthropic_base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
            if anthropic_base_url:
                anthropic_kwargs["base_url"] = anthropic_base_url
            if timeout is not None:
                anthropic_kwargs["timeout"] = timeout

            self.client = Anthropic(**anthropic_kwargs)
            resolved_model = model or default_model_env or "claude-sonnet-4-5"
            self.model = model_aliases.get(resolved_model, resolved_model)
        else:
            openai_base_url = (
                base_url
                or os.getenv("LLM_BASE_URL")
                or os.getenv("OPENAI_BASE_URL")
                or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
            )
            if self.mode == "openai_compatible" and openai_base_url is None:
                openai_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

            openai_api_key = (
                api_key
                or os.getenv("LLM_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("OPENAI_COMPATIBLE_API_KEY")
                or os.getenv("DEEPSEEK_API_KEY")
                or os.getenv("OLLAMA_API_KEY")
            )
            if not openai_api_key:
                openai_api_key = "dummy"

            openai_kwargs = {"api_key": openai_api_key}
            if openai_base_url:
                openai_kwargs["base_url"] = openai_base_url
            if timeout is not None:
                openai_kwargs["timeout"] = timeout

            self.client = OpenAI(**openai_kwargs)
            resolved_model = model or default_model_env or (
                "gpt-4o-mini" if self.mode == "openai" else "gpt-oss:20b"
            )
            self.model = model_aliases.get(resolved_model, resolved_model)

        self.request_profile = request_profile or os.getenv("LLM_REQUEST_PROFILE") or None
        self._request_profile = None
        if self.request_profile is not None:
            if self.request_profile not in REQUEST_PROFILES:
                raise ValueError(
                    f"Unknown request profile '{self.request_profile}'; choose from {sorted(REQUEST_PROFILES)}"
                )
            if self.mode != "openai_compatible":
                raise ValueError("Request profiles reproduce openai_compatible requests only")
            self._request_profile = REQUEST_PROFILES[self.request_profile]

        self._usage_lock = threading.Lock()
        self._last_token_usage = {"prompt": 0, "completion": 0, "total": 0}
        self._request_count = 0
        self._last_latency_s = 0.0

    def _apply_request_profile(self, request_kwargs, system_prompt):
        """Rewrite a current-format request into the selected earlier format."""
        profile = self._request_profile
        if not profile["json_suffix"]:
            request_kwargs["messages"][0]["content"] = system_prompt
        if not profile["response_format"]:
            request_kwargs.pop("response_format", None)
        if self.max_tokens is None:
            if profile["default_max_tokens"] is None:
                request_kwargs.pop("max_tokens", None)
            else:
                request_kwargs["max_tokens"] = profile["default_max_tokens"]
        if not profile["extra_body"]:
            request_kwargs.pop("extra_body", None)

    @staticmethod
    def _normalize_usage(raw_usage):
        if raw_usage is None:
            return {"prompt": 0, "completion": 0, "total": 0}

        prompt_tokens = int(getattr(raw_usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(raw_usage, "completion_tokens", 0) or 0)
        if prompt_tokens == 0 and hasattr(raw_usage, "input_tokens"):
            prompt_tokens = int(getattr(raw_usage, "input_tokens", 0) or 0)
        if completion_tokens == 0 and hasattr(raw_usage, "output_tokens"):
            completion_tokens = int(getattr(raw_usage, "output_tokens", 0) or 0)
        total_tokens = int(getattr(raw_usage, "total_tokens", 0) or (prompt_tokens + completion_tokens))
        return {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
        }

    def get_last_token_usage(self):
        with self._usage_lock:
            return dict(self._last_token_usage)

    def get_runtime_metadata(self):
        with self._usage_lock:
            metadata = {
                "provider": self.mode,
                "model_name": self.model,
                "temperature": self.temperature,
                "seed": self.seed,
                "seed_effective": bool(self.seed is not None and self.mode in {"openai", "openai_compatible"}),
                "timeout": self.timeout,
                "max_tokens": self.max_tokens,
                "request_count": int(self._request_count),
                "last_latency_s": float(self._last_latency_s),
                "last_token_usage": dict(self._last_token_usage),
            }
            if self.request_profile is not None:
                metadata["request_profile"] = self.request_profile
            return metadata

    def _extract_text(self, response_obj):
        if self.mode == "anthropic":
            content = getattr(response_obj, "content", None) or []
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    return text
            return ""
        return response_obj.choices[0].message.content

    @staticmethod
    def _extract_json_object_from_text(raw_text):
        if raw_text is None:
            raise ValueError("Empty LLM response")

        text = str(raw_text).strip()
        if not text:
            raise ValueError("Empty LLM response")

        # Fast path: full response is valid JSON.
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Common wrapper: fenced markdown block.
        if "```" in text:
            chunks = text.split("```")
            for chunk in chunks:
                candidate = chunk.strip()
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                if not candidate:
                    continue
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    continue

        # Last resort: find the first JSON object embedded in text.
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[idx:])
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed

        raise ValueError("Could not parse JSON object from LLM response")

    def llm_with_usage(self, system_prompt, user_query):
        response_content = "No response"
        usage = {"prompt": 0, "completion": 0, "total": 0}
        started_at = time.perf_counter()
        chat_completion = None
        request_kwargs = None
        try:
            if self.mode == "anthropic":
                request_kwargs = {
                    "model": self.model,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_query},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens or 4096,
                }
                if self.timeout is not None:
                    request_kwargs["timeout"] = self.timeout
                chat_completion = self.client.messages.create(**request_kwargs)
            else:
                # For openai_compatible (Ollama/DeepSeek), append JSON instruction to system prompt
                effective_system_prompt = system_prompt
                if self.mode == "openai_compatible" and system_prompt:
                    effective_system_prompt = system_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON object, no markdown, no extra text."
                
                request_kwargs = {
                    "messages": [
                        {"role": "system", "content": effective_system_prompt},
                        {"role": "user", "content": user_query},
                    ],
                    "model": self.model,
                    "temperature": self.temperature,
                    "response_format": {"type": "json_object"},
                }

                if self.seed is not None:
                    request_kwargs["seed"] = self.seed
                if self.timeout is not None:
                    request_kwargs["timeout"] = self.timeout
                if self.mode == "openai":
                    request_kwargs["max_completion_tokens"] = self.max_tokens or 4096
                else:
                    request_kwargs["max_tokens"] = self.max_tokens or 4096
                if self.extra_body is not None:
                    request_kwargs["extra_body"] = self.extra_body
                if self._request_profile is not None:
                    self._apply_request_profile(request_kwargs, system_prompt)

                chat_completion = self.client.chat.completions.create(**request_kwargs)

            usage = self._normalize_usage(getattr(chat_completion, "usage", None))

            response_content = self._extract_text(chat_completion)
            if self._request_profile is not None and self._request_profile["strict_json"]:
                response_json = json.loads(response_content)
            else:
                response_json = self._extract_json_object_from_text(response_content)

            with self._usage_lock:
                self._last_token_usage = dict(usage)
                self._request_count += 1
                self._last_latency_s = time.perf_counter() - started_at

            _record_raw_call(self.mode, chat_completion, request_kwargs=request_kwargs)
            return response_json, usage

        except Exception as e:
            with self._usage_lock:
                self._last_token_usage = dict(usage)
                self._request_count += 1
                self._last_latency_s = time.perf_counter() - started_at
            _record_raw_call(self.mode, chat_completion, error=e, request_kwargs=request_kwargs)
            return {
                "error": str(e),
                "mode": self.mode,
                "raw_response": response_content,
            }, usage

    def llm(self, system_prompt, user_query):
        response_json, _ = self.llm_with_usage(system_prompt, user_query)
        return response_json