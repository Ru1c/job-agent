# pipeline.py
import os
from datetime import datetime
from typing import List

import pdfplumber  # 记得加入 requirements

from config import (
    JOB_QUERIES,
    JOB_LOCATION,
    POSTED_WITHIN_HOURS,
    TOP_K_JOBS,
    REPORT_DIR,
    RESUME_PATH,
)
from apify_source import ApifyLinkedInJobSource
from llm_matcher import extract_profile_from_resume, score_jobs_for_profile
from job_source import Job


def load_resume_text(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Resume file not found: {path}")
    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return "\n".join(texts)


def fetch_all_jobs() -> List[Job]:
    source = ApifyLinkedInJobSource()
    all_jobs: List[Job] = []
    for q in JOB_QUERIES:
        jobs = source.fetch_jobs(
            query=q,
            location=JOB_LOCATION,
            posted_within_hours=POSTED_WITHIN_HOURS,
        )
        all_jobs.extend(jobs)

    # 去重（按 link 或 id）
    seen = set()
    deduped: List[Job] = []
    for job in all_jobs:
        key = job["link"]
        if key not in seen:
            seen.add(key)
            deduped.append(job)
    return deduped


def generate_markdown_report(results, date_str: str) -> str:
    lines = []
    lines.append(f"# Job Recommendations for {date_str}\n")
    lines.append(f"Top {TOP_K_JOBS} matches based on your profile.\n")

    for idx, r in enumerate(results[:TOP_K_JOBS], start=1):
        job = r.job
        lines.append(f"## {idx}. {job['title']} @ {job['company']}")
        if job.get("location"):
            lines.append(f"- **Location:** {job['location']}")
        if job.get("posted_at"):
            lines.append(f"- **Posted at:** {job['posted_at']}")
        lines.append(f"- **Score:** {r.total_score:.3f}")
        lines.append(
            f"- **Scores detail:** "
            f"required={r.detail_scores['skill_required_score']}, "
            f"nice={r.detail_scores['skill_nice_score']}, "
            f"exp={r.detail_scores['exp_score']}, "
            f"lang={r.detail_scores['lang_score']}"
        )
        lines.append(f"- **Link:** {job['link']}")
        lines.append("")
        lines.append(f"**Why this role:** {r.reasoning}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    today = datetime.today().strftime("%Y-%m-%d")

    print("Loading resume...")
    resume_text = load_resume_text(RESUME_PATH)
    profile = extract_profile_from_resume(resume_text)
    print("Profile extracted:", profile)

    print("Fetching jobs from Apify...")
    jobs = fetch_all_jobs()
    print(f"Fetched {len(jobs)} jobs after deduplication.")

    print("Scoring jobs...")
    results = score_jobs_for_profile(profile, jobs)

    print("Generating report...")
    md = generate_markdown_report(results, today)
    report_path = os.path.join(REPORT_DIR, f"jobs_report_{today}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
