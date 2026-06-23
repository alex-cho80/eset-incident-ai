from __future__ import annotations


class ApproveAnalysis:
    def execute(self, *, approved: bool) -> str:
        return "approved" if approved else "rejected"
