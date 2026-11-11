from field_dispatch.field_dispatch import TranscriptFacts, choose_dispatch_status


def test_blocked_urgent_visit_gets_priority_dispatch() -> None:
    facts = TranscriptFacts(
        transcript="Main relay burned. The replacement is not on the truck.",
        urgency="urgent",
        visit_blocked=True,
        follow_up="Dispatch a relay and book the earliest return visit.",
    )

    assert choose_dispatch_status(facts) == "priority_dispatch"


def test_clear_visit_with_no_follow_up_is_completed() -> None:
    facts = TranscriptFacts(
        transcript="Replaced the filter and verified normal pressure.",
        urgency="routine",
        visit_blocked=False,
        follow_up="",
    )

    assert choose_dispatch_status(facts) == "completed"
