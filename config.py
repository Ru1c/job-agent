# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "")  # 你在 Apify 选的 LinkedIn jobs actor

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Job picking
JOB_QUERIES = ["Data Scientist", "Machine Learning Engineer", "LLM"]  # 按需改
JOB_LOCATION = "United States"  # 或 "Remote", "San Francisco Bay Area" 等
POSTED_WITHIN_HOURS = 24
MAX_JOBS_PER_DAY = 800   # 成本控制

# Matching and reporting
TOP_K_JOBS = 15
REPORT_DIR = "reports"

# Resume path
RESUME_PATH = "resume_latest.pdf"
