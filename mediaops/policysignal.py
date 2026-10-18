"""Platform-policy signal: fake seeded feed + live stub with explicit gap.

The fake backend returns deterministic policy changes (seeded). The live
backend raises SignalGap — it never hallucinates a policy change.
"""

from __future__ import annotations


class SignalGap(Exception):
    pass


_FAKE_POLICIES = [
    {"policy_id": "POL-101", "platform": "SocialFeed",
     "change": "Video ads under 15s get a 10% delivery boost",
     "effective_day": 10},
    {"policy_id": "POL-102", "platform": "SearchNet",
     "change": "New restricted category: wellness claims need certification",
     "effective_day": 12},
    {"policy_id": "POL-103", "platform": "SocialFeed",
     "change": "Carousel frequency cap lowered to 3 per user per day",
     "effective_day": 14},
]


class FakePolicyFeed:
    """Seeded, deterministic policy changes."""

    def changes_since(self, day: int) -> list:
        return [p for p in _FAKE_POLICIES if p["effective_day"] > day]


class LivePolicyFeed:
    """Live platform-policy API stub — not wired; raises SignalGap."""

    def changes_since(self, day: int) -> list:
        raise SignalGap(
            "Live policy feed is not connected; no policy data available. "
            "Use the fake feed for demos."
        )
