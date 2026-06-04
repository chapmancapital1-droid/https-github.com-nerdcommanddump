from dataclasses import dataclass


@dataclass
class Signal:
    direction: int      # 1=buy, -1=sell, 0=flat
    confidence: float   # weighted score contribution
    strategy: str
    reason: str

    @property
    def is_active(self) -> bool:
        return self.direction != 0
