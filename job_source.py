# job_source.py
from typing import List, Protocol, TypedDict, Optional
from datetime import datetime


class Job(TypedDict, total=False):
    id: str
    title: str
    company: str
    location: str
    description: str
    posted_at: Optional[datetime]
    link: str
    source_raw: dict  # keep original data，for debug / scale up


class JobSource(Protocol):
    def fetch_jobs(
        self,
        query: str,
        location: str,
        posted_within_hours: int = 24,
        limit: Optional[int] = None,
    ) -> List[Job]:
        """
        return job list in uniformed schema：
        - title, company, location, description, posted_at, link
        - source_raw: raw field
        """
        ...
