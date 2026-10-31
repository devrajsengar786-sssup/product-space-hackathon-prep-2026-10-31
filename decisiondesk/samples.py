"""Small fictional Atlas meetings for a reproducible local demonstration."""

from datetime import date, timedelta


def get_demo_meetings(as_of: str) -> list[dict]:
    """Return two fictional meetings relative to an ISO reference date.

    Explicit speaker labels and simple sentences are intentional: the offline
    extractor is rule-based and is not a general language model.
    """
    today = date.fromisoformat(as_of)

    def day(offset: int) -> str:
        return (today + timedelta(days=offset)).isoformat()

    return [
        {
            "title": "Atlas launch planning",
            "date": day(-2),
            "transcript": "\n".join(
                [
                    "Maya: Project Atlas launch planning starts now.",
                    f"Maya: Decision: launch date is {day(6)}.",
                    f"Arjun: I will prepare the demo by {day(3)}.",
                    f"Maya: Leena will draft the release notes by {day(5)}.",
                    "Maya: Action: follow up on the security review.",
                    "Leena: I will confirm the accessibility checklist.",
                ]
            ),
        },
        {
            "title": "Atlas launch readiness update",
            "date": day(0),
            "transcript": "\n".join(
                [
                    "Maya: Project Atlas launch readiness update starts now.",
                    f"Maya: Decision: launch date is {day(9)}.",
                    f"Arjun: I will update the demo recording by {day(4)}.",
                    f"Leena: I will send the stakeholder update by {day(2)}.",
                    "Maya: Action: follow up on the analytics review.",
                ]
            ),
        },
    ]
