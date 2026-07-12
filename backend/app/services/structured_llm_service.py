import json
import os
import urllib.error
import urllib.request


class StructuredLLMError(RuntimeError):
    code = "LLM_GENERATION_FAILED"


def generate_structured(*, model: str, timeout_seconds: int, schema_name: str, schema: dict, instructions: str, input_data: dict) -> dict:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise StructuredLLMError("OPENAI_API_KEY is not configured.")

    payload = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(input_data, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = f"OpenAI request failed with HTTP {error.code}."
        try:
            body = json.loads(error.read().decode("utf-8"))
            message = body.get("error", {}).get("message") or message
        except Exception:
            pass
        raise StructuredLLMError(message) from error
    except (OSError, ValueError, TimeoutError) as error:
        raise StructuredLLMError(f"OpenAI request failed: {error}") from error

    text = _output_text(result)
    if not text:
        raise StructuredLLMError("OpenAI returned no structured output.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise StructuredLLMError("OpenAI returned invalid JSON.") from error
    if not isinstance(parsed, dict):
        raise StructuredLLMError("OpenAI structured output must be a JSON object.")
    return parsed


def _output_text(result: dict) -> str | None:
    if isinstance(result.get("output_text"), str):
        return result["output_text"]
    for item in result.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise StructuredLLMError(content.get("refusal") or "OpenAI refused the request.")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    return None
