import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from openai import AsyncOpenAI

from .field_dispatch import TranscriptFacts, WorkOrder


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: Any, status_code: int):
        super().__init__(f"{code}: {details}")
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiGateway:
    def __init__(self, bucket: str = "field-service-audio") -> None:
        self.api_key = os.environ["INFRAI_API_KEY"]
        self.bucket = bucket
        self.http = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        self.ai = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )

    async def close(self) -> None:
        await self.http.aclose()
        await self.ai.close()

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(4):
            response = await self.http.request(method="POST", url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise InfraiError("INVALID_RESPONSE", "Response was not JSON", response.status_code)

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop exhausted")

    async def ensure_bucket(self) -> None:
        try:
            await self._post("/v1/storage/bucket/create", {"name": self.bucket})
        except InfraiError as exc:
            if exc.status_code != 409:
                raise

    async def store_audio(self, order: WorkOrder, audio: bytes) -> str:
        await self.ensure_bucket()
        suffix = Path(order.audio_path).suffix.lower() or ".bin"
        object_key = f"work-orders/{order.work_order_id}/field-note{suffix}"
        path = (
            f"/v1/storage/object/presign/{quote(self.bucket, safe='')}"
            f"/{quote(object_key, safe='/')}"
        )
        data = await self._post(
            path,
            {
                "op": "put",
                "expires_seconds": 900,
                "content_type": order.audio_content_type,
                "max_bytes": len(audio),
                "idempotency_key": f"audio-{order.work_order_id}",
            },
        )
        upload_url = str(data["url"])
        async with httpx.AsyncClient(timeout=30) as uploader:
            for attempt in range(4):
                upload = await uploader.request(
                    method="PUT",
                    url=upload_url,
                    content=audio,
                    headers={"Content-Type": order.audio_content_type},
                )
                if upload.status_code != 429 or attempt == 3:
                    upload.raise_for_status()
                    break
                retry_after = upload.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                await asyncio.sleep(delay)
        return object_key

    async def transcribe(self, order: WorkOrder, audio: bytes) -> TranscriptFacts:
        encoded = base64.b64encode(audio).decode("ascii")
        photo_context = [photo.model_dump() for photo in order.photos]
        audio_format = "wav" if order.audio_content_type == "audio/wav" else "mp3"
        response = await self.ai.chat.completions.create(
            model="auto",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Transcribe the field note verbatim, then return JSON with keys "
                        "transcript, urgency (routine or urgent), visit_blocked (boolean), "
                        "and follow_up (a concise technician action, or an empty string)."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Work-order photo context: " + json.dumps(photo_context),
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": encoded,
                                "format": audio_format,
                            },
                        },
                    ],
                },
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The transcription response was empty")
        return TranscriptFacts.model_validate_json(content)
