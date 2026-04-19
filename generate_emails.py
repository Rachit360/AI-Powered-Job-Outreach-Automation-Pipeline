"""
generate_emails.py — AI Job Outreach Email Sender
Reads your Google Sheet, finds rows where Status = "Approved",
generates a personalized cold email using Groq, sends it,
then updates the sheet and logs everything.

Run AFTER auto_research.py has filled the research columns.
"""

import os
import csv
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    filename="email_log.txt",
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)

# ─────────────────────────────────────────────
# YOUR DETAILS — EDIT THESE
# ─────────────────────────────────────────────
MY_NAME       = os.getenv("MY_NAME", "Your Full Name")
MY_EMAIL      = os.getenv("MY_EMAIL")           # your Gmail
MY_GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD") # Gmail App Password
MY_LINKEDIN   = os.getenv("MY_LINKEDIN", "linkedin.com/in/yourprofile")
MY_GITHUB     = os.getenv("MY_GITHUB", "github.com/yourusername")
MY_PORTFOLIO  = os.getenv("MY_PORTFOLIO", "")   # optional

# ─────────────────────────────────────────────
# GOOGLE SHEETS SETUP
# ─────────────────────────────────────────────
SHEET_NAME = os.getenv("SHEET_NAME", "Job Outreach Tracker")
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

COL = {
    "company_name":  1,
    "website":       2,
    "industry":      3,
    "stage":         4,
    "contact_name":  5,
    "contact_role":  6,
    "contact_email": 7,
    "role_wanted":   8,
    "recent_news":   9,
    "why_company":   10,
    "your_angle":    11,
    "status":        12,
    "date_sent":     13,
    "reply":         14,
}

def get_sheet():
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# ─────────────────────────────────────────────
# GROQ: GENERATE THE COLD EMAIL
# ─────────────────────────────────────────────
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_email(row_data: dict) -> str:
    """Generate a personalized cold outreach email using Groq."""

    portfolio_line = f"Portfolio: {MY_PORTFOLIO}" if MY_PORTFOLIO else ""

    prompt = f"""
Write a short, genuine cold outreach email from a final year engineering student 
to a startup for a job opportunity.

SENDER INFO:
- Name: {MY_NAME}
- LinkedIn: {MY_LINKEDIN}
- GitHub: {MY_GITHUB}
{portfolio_line}

COMPANY INFO:
- Company: {row_data['company_name']}
- Industry: {row_data['industry']}
- Stage: {row_data['stage']}
- Role being sought: {row_data['role_wanted']}
- Recent news about them: {row_data['recent_news']}

PERSONALIZATION:
- Why this company (student's genuine reason): {row_data['why_company']}
- Student's relevant angle/project: {row_data['your_angle']}

RECIPIENT:
- Name: {row_data['contact_name']}
- Role: {row_data['contact_role']}

EMAIL RULES:
1. Subject line first, then the email body
2. Keep it under 150 words total — founders and HRs don't read long emails
3. Open with one specific line about the company (use the recent news or why_company)
4. One sentence about who you are
5. One sentence about your most relevant project (use the angle)
6. One clear ask — a 15-minute call or to share your resume
7. Sign off with name, LinkedIn, GitHub
8. Sound human, not like a template. No buzzwords. No "I hope this email finds you well."
9. Format: start with "Subject: ..." on the first line, then blank line, then email body

Write the email now:
"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=400
    )
    return response.choices[0].message.content.strip()

# ─────────────────────────────────────────────
# GMAIL: SEND THE EMAIL
# ─────────────────────────────────────────────
def send_email(to_email: str, subject: str, body: str, company_name: str):
    """Send email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = MY_EMAIL
    msg["To"]      = to_email
    msg["Bcc"]     = MY_EMAIL  # always BCC yourself for records

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(MY_EMAIL, MY_GMAIL_PASS)
        server.sendmail(MY_EMAIL, [to_email, MY_EMAIL], msg.as_string())

    print(f"    ✉  Sent to {to_email} ({company_name})")
    logging.info(f"Email sent to {to_email} for {company_name}")

# ─────────────────────────────────────────────
# CSV LOG
# ─────────────────────────────────────────────
CSV_FILE = "outreach_log.csv"

def log_to_csv(row_data: dict, subject: str, body: str):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "company", "contact_name", "contact_email",
            "role", "subject", "email_body"
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date":          datetime.now().strftime("%Y-%m-%d %H:%M"),
            "company":       row_data["company_name"],
            "contact_name":  row_data["contact_name"],
            "contact_email": row_data["contact_email"],
            "role":          row_data["role_wanted"],
            "subject":       subject,
            "email_body":    body
        })

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def run_email_pipeline():
    print("=" * 55)
    print("  EMAIL PIPELINE — Starting")
    print("=" * 55)

    sheet = get_sheet()
    rows = sheet.get_all_values()
    data_rows = rows[1:]  # skip header

    sent_count = 0

    for i, row in enumerate(data_rows):
        actual_row = i + 2

        while len(row) < 14:
            row.append("")

        status       = row[COL["status"] - 1].strip().lower()
        company_name = row[COL["company_name"] - 1].strip()
        contact_email = row[COL["contact_email"] - 1].strip()

        # ONLY process rows you've manually marked "Approved"
        if status != "approved":
            continue

        if not contact_email:
            print(f"  ⚠  {company_name} — no email address, skipping")
            continue

        row_data = {
            "company_name":  company_name,
            "website":       row[COL["website"] - 1].strip(),
            "industry":      row[COL["industry"] - 1].strip(),
            "stage":         row[COL["stage"] - 1].strip(),
            "contact_name":  row[COL["contact_name"] - 1].strip(),
            "contact_role":  row[COL["contact_role"] - 1].strip(),
            "contact_email": contact_email,
            "role_wanted":   row[COL["role_wanted"] - 1].strip(),
            "recent_news":   row[COL["recent_news"] - 1].strip(),
            "why_company":   row[COL["why_company"] - 1].strip(),
            "your_angle":    row[COL["your_angle"] - 1].strip(),
        }

        print(f"\n  → Generating email for: {company_name}")

        # Generate email
        raw_output = generate_email(row_data)

        # Parse subject and body
        lines = raw_output.split("\n")
        subject = ""
        body_lines = []
        for j, line in enumerate(lines):
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
            else:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()

        if not subject:
            subject = f"Opportunity at {company_name} — {MY_NAME}"

        print(f"    Subject: {subject}")

        # Send it
        try:
            send_email(contact_email, subject, body, company_name)

            # Update sheet
            sheet.update_cell(actual_row, COL["status"],    "Sent")
            sheet.update_cell(actual_row, COL["date_sent"], datetime.now().strftime("%Y-%m-%d"))

            # Log to CSV
            log_to_csv(row_data, subject, body)
            sent_count += 1

        except Exception as e:
            print(f"    ✗ Failed to send: {e}")
            logging.error(f"Send failed for {company_name}: {e}")

    print("\n" + "=" * 55)
    print(f"  DONE — Emails sent: {sent_count}")
    print("=" * 55)

if __name__ == "__main__":
    run_email_pipeline()