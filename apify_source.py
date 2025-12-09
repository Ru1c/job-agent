# apify_source.py
import time
from typing import List, Optional
from datetime import datetime, timedelta, timezone

import requests

from config import APIFY_API_TOKEN, APIFY_ACTOR_ID, MAX_JOBS_PER_DAY
from job_source import Job, JobSource


class ApifyLinkedInJobSource(JobSource):
    def __init__(self, api_token: str = APIFY_API_TOKEN, actor_id: str = APIFY_ACTOR_ID):
        if not api_token or not actor_id:
            raise ValueError("APIFY_API_TOKEN or APIFY_ACTOR_ID not set")
        self.api_token = api_token
        self.actor_id = actor_id

    def _start_actor_run(self, query: str, location: str, posted_within_hours: int) -> str:
        """触发 Apify actor run，返回 runId"""
        url = f"https://api.apify.com/v2/acts/{self.actor_id}/runs?token={self.api_token}"

        # 具体 input 要参考你选的 actor 文档
        # Here is a sample input structure：
        payload = {
            "searchQuery": query,
            "location": location,
            "postedWithin": posted_within_hours,  # 有些 actor 是 "maxListedAt" 之类
            "maxResults": MAX_JOBS_PER_DAY,
        }

        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["id"]  # runId

    def _wait_for_run_and_get_dataset_id(self, run_id: str, poll_interval: int = 5) -> str:
        """轮询 run 状态，直到 SUCCEEDED，返回 datasetId"""
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={self.api_token}"

        while True:
            resp = requests.get(status_url)
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data["status"]
            if status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED_OUT"]:
                if status != "SUCCEEDED":
                    raise RuntimeError(f"Apify run failed with status: {status}")
                return data["defaultDatasetId"]
            time.sleep(poll_interval)

    def _fetch_dataset_items(self, dataset_id: str, limit: Optional[int] = None) -> List[dict]:
        url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        params = {"token": self.api_token}
        if limit:
            params["limit"] = limit
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def fetch_jobs(
        self,
        query: str,
        location: str,
        posted_within_hours: int = 24,
        limit: Optional[int] = None,
    ) -> List[Job]:
        run_id = self._start_actor_run(query, location, posted_within_hours)
        dataset_id = self._wait_for_run_and_get_dataset_id(run_id)
        raw_items = self._fetch_dataset_items(dataset_id, limit=limit or MAX_JOBS_PER_DAY)

        jobs: List[Job] = []
        now = datetime.now(timezone.utc)
        min_time = now - timedelta(hours=posted_within_hours)

        for item in raw_items:
            # 下面这些字段名需要根据你 actor 的实际输出来调整
            title = item.get("title") or item.get("position")
            company = item.get("companyName") or item.get("company")
            location_str = item.get("location") or item.get("jobLocation")
            desc = item.get("description") or item.get("descriptionText") or ""

            link = item.get("url") or item.get("jobUrl")

            # 尝试解析发布时间
            posted_at_raw = item.get("listedAt") or item.get("timeAgo")
            posted_at: Optional[datetime] = None
            if isinstance(posted_at_raw, str):
                # 这里你可以自己写 parse，比如 ISO8601 / "3 days ago"
                # MVP 可以先不严格过滤，只要保证结构不报错即可
                try:
                    posted_at = datetime.fromisoformat(posted_at_raw.replace("Z", "+00:00"))
                except Exception:
                    posted_at = None

            # 简单过滤：如果有 posted_at，就丢掉太久的
            if posted_at and posted_at < min_time:
                continue

            if not (title and company and desc and link):
                continue

            job: Job = {
                "id": item.get("id") or link,
                "title": title,
                "company": company,
                "location": location_str,
                "description": desc,
                "posted_at": posted_at,
                "link": link,
                "source_raw": item,
            }
            jobs.append(job)

        return jobs
