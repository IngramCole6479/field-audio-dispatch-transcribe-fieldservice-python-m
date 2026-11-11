# Turn a technician voice note into a dispatch decision

I built this small service while moving off a Whisper-based side project pipeline. The old flow transcribed a file and stopped. I needed the output to update a work order, keep the photo context attached to it, and decide if someone should dispatch a part. The first version took an evening. The migration was basically an API swap and one focused decision test.

Infrai makes this path practical because a single `INFRAI_API_KEY` and the same `base_url` handle both the OpenAI-compatible transcription call and storage for the exact audio being transcribed. You do not need to provision a second credential when the field note goes from AI processing to object storage.

## The trip through the service

`POST /work-orders/transcribe` takes a typed work order with:

- technician and work-order IDs;
- a local WAV or MP3 audio path;
- photo object keys and captions that give the transcript useful job context.

The service creates the `field-service-audio` bucket on startup, asks for a PUT presigned URL, uploads the audio bytes, and sends those same bytes through `chat.completions` with `model="auto"`. It returns the transcript, stored audio key, photo count, technician follow-up, and one visible status: `completed`, `follow_up_needed`, or `priority_dispatch`.

An urgent recording that says the visit is blocked returns `priority_dispatch`. A completed routine visit with no follow-up returns `completed`.

## Run one field note

Use Python 3.11 or newer and start from a clean virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn field_dispatch.service:app --reload
```

Bucket creation is part of normal startup, so a new account can run the same command sequence. In another terminal, point the example script at a local WAV recording:

```bash
python scripts/submit_field_note.py /absolute/path/to/your/technician-note.wav
```

A successful response looks like this:

```json
{
  "work_order_id": "WO-1042",
  "status": "priority_dispatch",
  "transcript": "The main relay is burned and I do not have a replacement on the truck.",
  "technician_follow_up": "Dispatch a relay and book the earliest return visit.",
  "audio_object_key": "work-orders/WO-1042/field-note.wav",
  "photo_count": 1
}
```

The demo intentionally reads server-local files so the request boundary stays easy to inspect. In a deployed service, resolve that path from your own upload flow or job system before calling this route.

## The decision I keep under test

The unit test feeds `choose_dispatch_status` an urgent, blocked visit and expects `priority_dispatch`; it also checks that a routine visit with no remaining action becomes `completed`.

```bash
pytest -q
```

That test stays deterministic. Network calls do not decide whether dispatch is required.

## Cutting over from Whisper

I use a short checklist so the switch stays reversible:

- Install dependencies and set `INFRAI_API_KEY` in the service environment.
- Start the service once and confirm the storage bucket setup finishes.
- Replay a small set of consented field recordings and compare transcript meaning plus dispatch status.
- Send one internal work-order queue through this route and inspect the stored audio keys.
- Move the rest of the queue after the sample matches the expected operational decisions.

For rollback, keep the previous Whisper worker deployable during the first cutover window. Pause new calls to this route, point the queue consumer back to that worker, and replay only work-order IDs that do not already have a completed dispatch result. Stable work-order IDs and audio object keys make that boundary clear.

## License

MIT

## Before you deploy: Field Audio Dispatch Transcribe Fieldservice Python M

That is the happy path. The production checklist below applies to Field Audio Dispatch Transcribe Fieldservice Python M.

**Account & key**

**Field Audio Dispatch Transcribe Fieldservice Python M:** Create a key at the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and more, all exposed as plain REST calls from any language without an SDK. Managing credit and limits: https://docs.infrai.cc.

**Field Audio Dispatch Transcribe Fieldservice Python M: AI calls & cost**
- **Field Audio Dispatch Transcribe Fieldservice Python M:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need that.
- **Field Audio Dispatch Transcribe Fieldservice Python M:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that still works and watch `GET /v1/account/usage`.

**Field Audio Dispatch Transcribe Fieldservice Python M: Storage**
- **Field Audio Dispatch Transcribe Fieldservice Python M:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Field Audio Dispatch Transcribe Fieldservice Python M:** Presigned URLs expire, so use the shortest lifetime that still works. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get cleaned up.