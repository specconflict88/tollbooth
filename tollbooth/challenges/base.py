from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ChallengeType(str, Enum):
    SHA256_BALLOON = "sha256-balloon"
    SHA256 = "sha256"


DIFFICULTY_OFFSETS: dict[ChallengeType, int] = {
    ChallengeType.SHA256_BALLOON: 0,
    ChallengeType.SHA256: 8,
}


def count_leading_zero_bits(data: bytes) -> int:
    for i, byte in enumerate(data):
        if byte:
            return i * 8 + (8 - byte.bit_length())
    return len(data) * 8


@dataclass
class ChallengeBase:
    id: str
    random_data: str
    difficulty: int
    ip_hash: str
    created_at: float
    challenge_type: ChallengeType = ChallengeType.SHA256_BALLOON
    spent: bool = False

    def __post_init__(self):
        if isinstance(self.challenge_type, str):
            self.challenge_type = ChallengeType(self.challenge_type)


class ChallengeHandler(ABC):
    @property
    @abstractmethod
    def challenge_type(self) -> ChallengeType: ...

    @abstractmethod
    def to_difficulty(self, base: int) -> int: ...

    @property
    @abstractmethod
    def template(self) -> str: ...

    @abstractmethod
    def verify(self, random_data: str, nonce: int, difficulty: int) -> bool: ...

    @abstractmethod
    def render_payload(
        self,
        challenge: ChallengeBase,
        verify_path: str,
        redirect: str,
    ) -> dict: ...
