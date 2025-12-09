# llm_matcher.py
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from openai import OpenAI

from config import OPENAI_API_KEY
from job_source import Job

client = OpenAI(api_key=OPENAI_API_KEY)


@dataclass
class ProfileInfo:
    skills: List[str]
    years_experience: float
    languages: List[str]
    domains: List[str]


@dataclass
class JobInfo:
    title: str
    required_skills: List[str]
    nice_to_have_skills: List[str]
    experience_level: str
    languages: List[str]
    location_type: str
    domain: str


@dataclass
class MatchResult:
    job: Job
    total_score: float
    detail_scores: Dict[str, float]
    reasoning: str


def _call_structured_llm(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    # 这里用最简单的 JSON 解析方式（你也可以加 function calling / response_format）
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    import json
    return json.loads(resp.choices[0].message.content)


def extract_profile_from_resume(resume_text: str) -> ProfileInfo:
    system_prompt = (
        "You are an assistant that extracts structured information from CVs. "
        "Always respond with JSON only."
    )
    user_prompt = f"""
Please extract the candidate's profile from the following resume text.

Return JSON with keys:
- skills: list of strings
- years_experience: number (approx total years of professional experience)
- languages: list of languages (e.g. ["English", "Chinese"])
- domains: list of domains (e.g. ["Fintech", "E-commerce", "Ads"])

Resume:
\"\"\"{resume_text}\"\"\"
"""
    data = _call_structured_llm(system_prompt, user_prompt)
    return ProfileInfo(
        skills=data.get("skills", []),
        years_experience=float(data.get("years_experience", 0)),
        languages=data.get("languages", []),
        domains=data.get("domains", []),
    )


def extract_job_info(job: Job) -> JobInfo:
    system_prompt = (
        "You are an assistant that extracts structured information from job descriptions. "
        "Always respond with JSON only."
    )
    user_prompt = f"""
Extract structured info from this job posting.

Return JSON with:
- title: string
- required_skills: list of strings
- nice_to_have_skills: list of strings
- experience_level: one of ["junior","mid","senior","lead","principal","mixed","unknown"]
- languages: list of required languages
- location_type: one of ["remote","hybrid","onsite","unspecified"]
- domain: string like "Fintech", "Ads", "E-commerce", or "General".

Job title: {job['title']}
Company: {job['company']}
Location: {job.get('location')}
Description:
\"\"\"{job['description']}\"\"\"
"""
    data = _call_structured_llm(system_prompt, user_prompt)
    return JobInfo(
        title=data.get("title") or job["title"],
        required_skills=data.get("required_skills", []),
        nice_to_have_skills=data.get("nice_to_have_skills", []),
        experience_level=data.get("experience_level", "unknown"),
        languages=data.get("languages", []),
        location_type=data.get("location_type", "unspecified"),
        domain=data.get("domain", "General"),
    )


def compute_match_score(profile: ProfileInfo, job_info: JobInfo) -> MatchResult:
    prof_skills = set(s.lower() for s in profile.skills)
    req_skills = [s.lower() for s in job_info.required_skills]
    nice_skills = [s.lower() for s in job_info.nice_to_have_skills]

    if req_skills:
        covered = sum(1 for s in req_skills if s in prof_skills)
        skill_required_score = covered / len(req_skills)
    else:
        skill_required_score = 0.5  # 没写要求，就给个中立分

    nice_covered = sum(1 for s in nice_skills if s in prof_skills)
    skill_nice_score = min(nice_covered / 5, 1.0)

    # 经验（非常粗略，可以以后升级）
    exp_score = 0.7
    # 语言匹配（只要包含必需语言就加分）
    lang_required = [l.lower() for l in job_info.languages]
    prof_lang = [l.lower() for l in profile.languages]
    if lang_required:
        lang_match = all(l in prof_lang for l in lang_required)
        lang_score = 1.0 if lang_match else 0.3
    else:
        lang_score = 0.7

    total = (
        0.5 * skill_required_score
        + 0.2 * skill_nice_score
        + 0.2 * exp_score
        + 0.1 * lang_score
    )

    # 让 LLM 用自然语言解释为什么推荐（可选）
    reasoning_prompt = f"""
Given this profile and job, explain in 2-3 sentences why this job is or isn't a good fit.

Profile:
skills: {profile.skills}
years_experience: {profile.years_experience}
languages: {profile.languages}
domains: {profile.domains}

Job:
title: {job_info.title}
required_skills: {job_info.required_skills}
nice_to_have_skills: {job_info.nice_to_have_skills}
languages_required: {job_info.languages}
domain: {job_info.domain}

Use concise English.
"""
    reasoning_data = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You explain job fit to a candidate briefly."},
            {"role": "user", "content": reasoning_prompt},
        ],
        temperature=0.3,
    )
    reasoning = reasoning_data.choices[0].message.content.strip()

    detail_scores = {
        "skill_required_score": round(skill_required_score, 3),
        "skill_nice_score": round(skill_nice_score, 3),
        "exp_score": round(exp_score, 3),
        "lang_score": round(lang_score, 3),
    }

    return MatchResult(
        job=job_info.__dict__.get("job", None) or {},  # 占位，下面 pipeline 会替换
        total_score=float(round(total, 3)),
        detail_scores=detail_scores,
        reasoning=reasoning,
    )


def score_jobs_for_profile(profile: ProfileInfo, jobs: List[Job]) -> List[MatchResult]:
    results: List[MatchResult] = []
    for job in jobs:
        job_info = extract_job_info(job)
        r = compute_match_score(profile, job_info)
        # 把原始 job 放进去，方便后面输出
        r.job = job
        results.append(r)

    results.sort(key=lambda x: x.total_score, reverse=True)
    return results
