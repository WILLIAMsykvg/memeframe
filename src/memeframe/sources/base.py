"""Source contract. Every adapter implements search() and nothing else is required."""

from __future__ import annotations

from abc import ABC, abstractmethod

from memeframe.models import Meme, SearchOptions


class Source(ABC):
    id: str
    name: str
    description: str
    requires_auth: bool = False
    enabled: bool = True
    referer: str = ""

    @abstractmethod
    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        raise NotImplementedError

    def info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "requires_auth": self.requires_auth,
            "enabled": self.enabled,
        }
