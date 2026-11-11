from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .field_dispatch import DispatchDecision, WorkOrder, choose_dispatch_status
from .infrai_gateway import InfraiError, InfraiGateway


gateway: InfraiGateway | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global gateway
    gateway = InfraiGateway()
    await gateway.ensure_bucket()
    yield
    await gateway.close()


app = FastAPI(title="Field Audio Dispatch", lifespan=lifespan)


@app.post("/work-orders/transcribe", response_model=DispatchDecision)
async def transcribe_work_order(order: WorkOrder) -> DispatchDecision:
    audio_path = Path(order.audio_path)
    if not audio_path.is_file():
        raise HTTPException(status_code=422, detail="audio_path must name a readable file")
    audio = audio_path.read_bytes()
    if gateway is None:
        raise HTTPException(status_code=503, detail="service is starting")

    try:
        audio_key = await gateway.store_audio(order, audio)
        facts = await gateway.transcribe(order, audio)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.details},
        ) from exc

    return DispatchDecision(
        work_order_id=order.work_order_id,
        status=choose_dispatch_status(facts),
        transcript=facts.transcript,
        technician_follow_up=facts.follow_up,
        audio_object_key=audio_key,
        photo_count=len(order.photos),
    )
