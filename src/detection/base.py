from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass
class RawJob:
    source_board: str
    external_id: str
    url: str
    title: str
    company_name: str
    location: str | None = None
    description_text: str | None = None
    description_html: str | None = None
    posted_at: str | None = None


class BaseScraper(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def fetch_jobs(self, client: httpx.AsyncClient) -> list[RawJob]: ...
