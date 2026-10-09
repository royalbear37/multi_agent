"""Reserve one bounded call per remaining role before retrieval or repairs."""
class TimeBudget:
    def __init__(self, start, total, agents):
        self.deadline = start + total
        # Lower explicit total limits are honored by scaling all reservations,
        # rather than starving the final audit or silently increasing the limit.
        caps = [a.max_timeout_seconds for a in agents]
        scale = min(1.0, total * .85 / sum(caps))
        self.reservations = [cap * scale for cap in caps]

    def available(self, now, index, *, retrieval=False):
        tail = self.reservations[index if retrieval else index+1:]
        return max(0.0, self.deadline - now - sum(tail))

    def call_timeout(self, now, index, cap):
        return min(cap, self.available(now, index))
