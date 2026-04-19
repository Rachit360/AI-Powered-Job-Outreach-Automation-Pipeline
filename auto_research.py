"""
auto_research.py — Automated Research Filler
Reads your Google Sheet, finds rows missing research data,
fetches company info automatically, then uses Groq to fill
"Why This Company" and "Your Angle" columns.

Run this BEFORE generate_emails.py
"""

import os
import time
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
import logging
from datetime import datetime

load_dotenv()
logging.basicConfig(
    filename="research_log.txt",
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)

# ─────────────────────────────────────────────
# YOUR PERSONAL CONTEXT BLOCK — EDIT THIS ONCE
# This is what Groq uses to figure out your angle
# for each company. Be specific about your projects.
# ─────────────────────────────────────────────
MY_PERSONAL_CONTEXT = """
I am a 4th year Computer Science engineering student graduating in 2025.

My top projects:
1. AI-Powered Lead Email Automation Pipeline — Built an end-to-end Python automation 
   system using Groq (Llama AI), Google Sheets API, Gmail SMTP, and Windows Task Scheduler.
   Reads leads from a Google Form, generates personalized cold emails using AI, and logs 
   everything to a CSV dashboard. Shows my ability to build real AI-powered workflows.

2. [ADD YOUR SECOND PROJECT HERE — e.g., "Built a REST API using FastAPI and PostgreSQL 
   for a food delivery app with JWT authentication and deployed on AWS EC2"]

3. [ADD YOUR THIRD PROJECT HERE — e.g., "ML model that predicts stock prices using LSTM 
   networks, trained on 5 years of NSE data with 78% directional accuracy"]

My skills: Python, AI/ML APIs, automation, backend development, REST APIs, SQL
What I'm looking for: SDE / ML Engineer / Backend Engineer roles at early-stage startups
What excites me: companies solving real problems with AI, automation, or data
"""

# ─────────────────────────────────────────────
# GOOGLE SHEETS SETUP
# ─────────────────────────────────────────────
SHEET_NAME = os.getenv("SHEET_NAME", "Job Outreach Tracker")  # Your sheet name
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet():
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# ─────────────────────────────────────────────
# COLUMN INDEX MAP — adjust if your sheet differs
# ─────────────────────────────────────────────
COL = {
    "company_name":   1,   # A
    "website":        2,   # B
    "industry":       3,   # C
    "stage":          4,   # D
    "contact_name":   5,   # E
    "contact_role":   6,   # F
    "contact_email":  7,   # G
    "role_wanted":    8,   # H
    "recent_news":    9,   # I  ← auto-filled
    "why_company":    10,  # J  ← Groq-filled
    "your_angle":     11,  # K  ← Groq-filled
    "status":         12,  # L
    "date_sent":      13,  # M
    "reply":          14,  # N
}

# ─────────────────────────────────────────────
# STEP 1: SCRAPE COMPANY ABOUT PAGE
# ─────────────────────────────────────────────
def scrape_about_page(website: str) -> str:
    """Fetch a short description from the company's website."""
    if not website:
        return ""
    try:
        # Make sure URL has scheme
        if not website.startswith("http"):
            website = "https://" + website
        headers = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
        resp = requests.get(website, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try meta description first (usually the cleanest summary)
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"][:400]

        # Fallback: first meaningful paragraph
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 80:
                return text[:400]

        return ""
    except Exception as e:
        logging.warning(f"Could not scrape {website}: {e}")
        return ""

# ─────────────────────────────────────────────
# STEP 2: FETCH RECENT NEWS via NewsAPI
# ─────────────────────────────────────────────
def fetch_recent_news(company_name: str) -> str:
    """Search Google News RSS for recent news about the company."""
    try:
        query = requests.utils.quote(f"{company_name} startup india")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=8)
        
        soup = BeautifulSoup(resp.text, "xml")
        items = soup.find_all("item")
        
        if items:
            top = items[0]
            title = top.find("title").text if top.find("title") else ""
            pub_date = top.find("pubDate").text[:16] if top.find("pubDate") else ""
            title = title.split(" - ")[0].strip()
            return f"{title} ({pub_date})"
        return ""
    except Exception as e:
        logging.warning(f"Google News RSS failed for {company_name}: {e}")
        return ""

def fetch_news_via_google(company_name: str) -> str:
    """Fallback: scrape Google News search snippet."""
    try:
        query = f"{company_name} startup funding launch 2024 2025"
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=nws"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract first news snippet
        for div in soup.find_all("div", class_=True):
            text = div.get_text(strip=True)
            if len(text) > 60 and company_name.lower() in text.lower():
                return text[:250]
        return ""
    except Exception as e:
        logging.warning(f"Google news fallback failed for {company_name}: {e}")
        return ""

# ─────────────────────────────────────────────
# STEP 3: USE GROQ TO FILL WHY + ANGLE
# ─────────────────────────────────────────────
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def groq_fill_why_and_angle(company_name, industry, stage, role_wanted,
                             about_text, recent_news) -> tuple:
    """
    Returns (why_company_sentence, your_angle_sentence)
    Groq figures out the best angle from MY_PERSONAL_CONTEXT.
    """
    prompt = f"""
You are helping a final year engineering student write targeted job outreach.

STUDENT BACKGROUND:
{MY_PERSONAL_CONTEXT}

COMPANY INFO:
- Company: {company_name}
- Industry: {industry}
- Stage: {stage}
- Role being targeted: {role_wanted}
- About the company: {about_text}
- Recent news: {recent_news}

Your task: Write TWO short sentences.

Sentence 1 — WHY THIS COMPANY (1 sentence, max 25 words):
Why would this student genuinely want to work at this company?
Base it on what the company does and what excites the student.

Sentence 2 — YOUR ANGLE (1 sentence, max 30 words):
Which of the student's projects or skills is most relevant to this company's work?
Be specific — name the actual project and connect it to the company's domain.

Reply in exactly this format, nothing else:
WHY: [your sentence here]
ANGLE: [your sentence here]
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        raw = response.choices[0].message.content.strip()

        why = ""
        angle = ""
        for line in raw.split("\n"):
            if line.startswith("WHY:"):
                why = line.replace("WHY:", "").strip()
            elif line.startswith("ANGLE:"):
                angle = line.replace("ANGLE:", "").strip()

        return why, angle

    except Exception as e:
        logging.error(f"Groq fill failed for {company_name}: {e}")
        return "", ""

# ─────────────────────────────────────────────
# MAIN: LOOP THROUGH SHEET AND FILL GAPS
# ─────────────────────────────────────────────
def run_auto_research():
    print("=" * 55)
    print("  AUTO RESEARCH FILLER — Starting")
    print("=" * 55)

    sheet = get_sheet()
    rows = sheet.get_all_values()
    header = rows[0]
    data_rows = rows[1:]  # skip header row

    filled_count = 0
    skipped_count = 0

    for i, row in enumerate(data_rows):
        actual_row = i + 2  # 1-indexed, skip header

        # Pad row in case some columns are empty
        while len(row) < 14:
            row.append("")

        company_name  = row[COL["company_name"] - 1].strip()
        website       = row[COL["website"] - 1].strip()
        industry      = row[COL["industry"] - 1].strip()
        stage         = row[COL["stage"] - 1].strip()
        role_wanted   = row[COL["role_wanted"] - 1].strip()
        recent_news   = row[COL["recent_news"] - 1].strip()
        why_company   = row[COL["why_company"] - 1].strip()
        your_angle    = row[COL["your_angle"] - 1].strip()
        status        = row[COL["status"] - 1].strip()

        # Skip if no company name
        if not company_name:
            continue

        # Skip if already fully researched or already sent
        if status.lower() in ["sent", "approved", "skip"]:
            skipped_count += 1
            continue

        # Check what needs filling
        needs_news  = not recent_news
        needs_why   = not why_company
        needs_angle = not your_angle

        if not (needs_news or needs_why or needs_angle):
            print(f"  ✓ {company_name} — already complete, skipping")
            skipped_count += 1
            continue

        print(f"\n  → Processing: {company_name}")

        # Step 1: Scrape about page
        about_text = scrape_about_page(website)
        print(f"    About page: {'fetched' if about_text else 'not found'}")

        # Step 2: Fetch recent news
        if needs_news:
            print(f"    Fetching news...")
            recent_news = fetch_recent_news(company_name)
            if recent_news:
                sheet.update_cell(actual_row, COL["recent_news"], recent_news)
                print(f"    News: {recent_news[:80]}...")
            else:
                recent_news = "No recent news found"
                sheet.update_cell(actual_row, COL["recent_news"], recent_news)
                print(f"    News: none found")

        # Step 3: Groq fills Why + Angle
        if needs_why or needs_angle:
            print(f"    Asking Groq to fill Why + Angle...")
            why, angle = groq_fill_why_and_angle(
                company_name, industry, stage, role_wanted,
                about_text, recent_news
            )
            if needs_why and why:
                sheet.update_cell(actual_row, COL["why_company"], why)
                print(f"    Why: {why[:80]}")
            if needs_angle and angle:
                sheet.update_cell(actual_row, COL["your_angle"], angle)
                print(f"    Angle: {angle[:80]}")

        filled_count += 1

        # Be polite to APIs — don't hammer them
        time.sleep(2)

    print("\n" + "=" * 55)
    print(f"  DONE — Filled: {filled_count} | Skipped: {skipped_count}")
    print("=" * 55)
    logging.info(f"Auto research run complete. Filled: {filled_count}, Skipped: {skipped_count}")

if __name__ == "__main__":
    run_auto_research()
