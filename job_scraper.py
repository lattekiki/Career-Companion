import os
import re
import json
import time
import threading
from urllib.parse import urljoin


AFRIWORK_URL = "https://afriworket.com/jobs"
BASE_URL = "https://afriworket.com"
AFRIWORK_JOBS_FILE = "afriwork_jobs.json"


def clean_text(text):
    """Normalize whitespace."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def await_count(locator):
    """Safely get the number of matching elements."""
    try:
        return locator.count()
    except Exception:
        return 0


def get_afriwork_jobs(url=AFRIWORK_URL):
    # Lazy import Playwright inside the scraper function
    from playwright.sync_api import sync_playwright

    jobs = []

    print("\n" + "=" * 70)
    print("AFRIWORK JOB SCRAPER")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        try:
            print("\nOpening:")
            print(url)

            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Wait explicitly for job links to appear on page
            try:
                page.wait_for_selector("a[href*='/jobs/']", timeout=15000)
            except Exception:
                print("Warning: Timed out waiting for job links to render.")

            # Scroll to trigger dynamic/lazy loading
            for _ in range(5):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1000)

            print("\nPage loaded:")
            print(page.url)

            # ==================================================
            # ROBUST LINK-BASED EXTRACTION
            # ==================================================
            job_links = page.locator("a[href*='/jobs/']")
            count = job_links.count()

            print(f"\nFound {count} candidate job links")

            for i in range(count):
                try:
                    link_el = job_links.nth(i)
                    href = link_el.get_attribute("href")

                    # Skip non-job links or main hub links
                    if not href or href.strip() in ["/jobs", "/jobs/", "https://afriworket.com/jobs"]:
                        continue

                    title = clean_text(link_el.inner_text())
                    if not title or len(title) < 3:
                        continue

                    full_link = urljoin(BASE_URL, href)

                    # Get parent container text for full context/description
                    card_container = link_el.locator(
                        "xpath=./ancestor::div[contains(@class, 'flex') or contains(@class, 'card') or contains(@class, 'group')][1]"
                    )
                    
                    full_text = clean_text(card_container.inner_text()) if await_count(card_container) > 0 else title

                    job = {
                        "title": title,
                        "company": "Afriwork Employer",
                        "location": "Ethiopia",
                        "posted": "Recently",
                        "url": href,
                        "link": full_link,
                        "description": full_text
                    }

                    jobs.append(job)

                    print("\n" + "-" * 70)
                    print(f"JOB {len(jobs)}")
                    print(f"Title: {title}")
                    print(f"Link:  {full_link}")

                except Exception as e:
                    print(f"\nCould not extract job link #{i + 1}: {e}")

            # ==================================================
            # REMOVE DUPLICATES
            # ==================================================
            unique_jobs = []
            seen = set()

            for job in jobs:
                if job["link"] in seen:
                    continue
                seen.add(job["link"])
                unique_jobs.append(job)

            jobs = unique_jobs

            # ==================================================
            # SAVE JSON
            # ==================================================
            with open(AFRIWORK_JOBS_FILE, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=4, ensure_ascii=False)

            print("\n" + "=" * 70)
            print(f"SUCCESS: {len(jobs)} jobs extracted")
            print(f"Saved to: {AFRIWORK_JOBS_FILE}")
            print("=" * 70)

        finally:
            browser.close()

    return jobs


# ============================================================
# MATCHING & RANKING ALGORITHM
# ============================================================

def load_afriwork_jobs():
    """Load saved jobs from the json file."""
    if not os.path.exists(AFRIWORK_JOBS_FILE):
        return []

    try:
        with open(AFRIWORK_JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        if not isinstance(jobs, list):
            return []

        return jobs
    except Exception as e:
        print(f"Could not read {AFRIWORK_JOBS_FILE}: {e}")
        return []


def tokenize(text):
    """Convert text into lowercase searchable words."""
    if not text:
        return set()
    return set(re.findall(r"[a-zA-Z0-9+#.]+", str(text).lower()))


def extract_skills(text):
    """Extract useful skill-like terms from text."""
    if not text:
        return set()

    text = str(text).lower()
    common_skills = {
        "python", "java", "javascript", "typescript", "react", "node", "node.js",
        "sql", "mysql", "postgresql", "postgres", "mongodb", "api", "apis", "rest",
        "rest api", "git", "github", "docker", "kubernetes", "aws", "azure", "gcp",
        "machine learning", "ai", "data analysis", "data analytics", "excel",
        "power bi", "tableau", "figma", "communication", "leadership", "sales",
        "marketing", "customer service", "project management", "engineering", "autocad"
    }

    return {skill for skill in common_skills if skill in text}


def calculate_job_match(job, profile):
    """Calculate a match score for a single job against a user profile."""
    job_text = " ".join([
        str(job.get("title", "")),
        str(job.get("company", "")),
        str(job.get("location", "")),
        str(job.get("description", "")),
    ]).lower()

    target_role = str(profile.get("target_role", ""))
    current_role = str(profile.get("current_role", ""))
    profile_skills = str(profile.get("skills", ""))
    profile_experience = str(profile.get("experience", ""))

    # Target Role Score
    target_words = tokenize(target_role)
    target_matches = [w for w in target_words if len(w) > 2 and w in job_text]
    target_score = min(40, int(40 * len(target_matches) / len(target_words))) if target_words else 0

    # Current Role Score
    current_words = tokenize(current_role)
    current_matches = [w for w in current_words if len(w) > 2 and w in job_text]
    current_score = min(15, int(15 * len(current_matches) / len(current_words))) if current_words else 0

    # Skills Score
    profile_skill_set = extract_skills(profile_skills)
    job_skill_set = extract_skills(job_text)
    matched_skills = sorted(profile_skill_set & job_skill_set)
    skill_score = min(35, int(35 * len(matched_skills) / len(profile_skill_set))) if profile_skill_set else 0

    # Experience Score
    experience_numbers = re.findall(r"\d+", profile_experience)
    if experience_numbers:
        user_years = float(experience_numbers[0])
        job_exp_text = str(job.get("description", "")).lower()
        req_numbers = re.findall(r"\d+", job_exp_text)

        if req_numbers:
            req_years = float(req_numbers[0])
            if user_years >= req_years:
                experience_score = 10
            elif user_years + 1 >= req_years:
                experience_score = 6
            else:
                experience_score = 2
        else:
            experience_score = 7
    else:
        experience_score = 5

    score = min(100, target_score + current_score + skill_score + experience_score)

    return {
        "score": score,
        "matched_skills": matched_skills,
    }


def get_ranked_jobs(profile):
    """Imported by app.py to get ranked jobs."""
    jobs = load_afriwork_jobs()

    # If local JSON is missing or empty, trigger scraper
    if not jobs:
        jobs = get_afriwork_jobs()

    ranked_jobs = []
    for job in jobs:
        match = calculate_job_match(job, profile)
        ranked_jobs.append({
            **job,
            "match_score": match["score"],
            "matched_skills": match["matched_skills"]
        })

    ranked_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    return ranked_jobs


# ============================================================
# RUN STANDALONE SCRAPER THREAD
# ============================================================

def run_scraper_in_thread():
    print("\nInitiating Afriwork scraper...")
    jobs = get_afriwork_jobs()
    print(f"\nScraper thread finished with {len(jobs)} jobs.")


if __name__ == "__main__":
    scraper_thread = threading.Thread(target=run_scraper_in_thread)
    scraper_thread.start()
    scraper_thread.join()