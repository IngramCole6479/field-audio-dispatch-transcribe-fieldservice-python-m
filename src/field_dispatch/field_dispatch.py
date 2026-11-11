from typing import Literal

from pydantic import BaseModel, Field


class WorkOrderPhoto(BaseModel):
    object_key: str
    caption: str


class WorkOrder(BaseModel):
    work_order_id: str
    technician_id: str
    customer_name: str
    audio_path: str
    audio_content_type: Literal["audio/mpeg", "audio/wav"]
    photos: list[WorkOrderPhoto] = Field(default_factory=list)


class TranscriptFacts(BaseModel):
    transcript: str
    urgency: Literal["routine", "urgent"]
    visit_blocked: bool
    follow_up: str


class DispatchDecision(BaseModel):
    work_order_id: str
    status: Literal["completed", "follow_up_needed", "priority_dispatch"]
    transcript: str
    technician_follow_up: str
    audio_object_key: str
    photo_count: int


def choose_dispatch_status(facts: TranscriptFacts) -> Literal[
    "completed", "follow_up_needed", "priority_dispatch"
]:
    if facts.urgency == "urgent" and facts.visit_blocked:
        return "priority_dispatch"
    if facts.visit_blocked or facts.follow_up.strip():
        return "follow_up_needed"
    return "completed"
