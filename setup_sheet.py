"""
setup_sheet.py — One-time setup script
Run this ONCE to create your Google Sheet with the correct
column headers and a sample row so you know exactly what to fill.
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SHEET_NAME = os.getenv("SHEET_NAME", "Job Outreach Tracker")
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def setup():
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)

    # Create new sheet
    try:
        spreadsheet = client.create(SHEET_NAME)
        print(f"✓ Created new sheet: {SHEET_NAME}")
    except Exception as e:
        print(f"Sheet may already exist, opening it: {e}")
        spreadsheet = client.open(SHEET_NAME)

    sheet = spreadsheet.sheet1

    # Set headers
    headers = [
        "Company Name",      # A — you fill
        "Website",           # B — you fill
        "Industry",          # C — you fill
        "Stage",             # D — you fill (Seed / Series A / Bootstrapped etc.)
        "Contact Name",      # E — you fill
        "Contact Role",      # F — you fill (HR / Founder / CTO)
        "Contact Email",     # G — you fill
        "Role Wanted",       # H — you fill (SDE / ML Engineer / Backend)
        "Recent News",       # I — AUTO FILLED by auto_research.py
        "Why This Company",  # J — GROQ FILLED by auto_research.py
        "Your Angle",        # K — GROQ FILLED by auto_research.py
        "Status",            # L — you set to "Approved" to trigger sending
        "Date Sent",         # M — AUTO FILLED by generate_emails.py
        "Reply Received",    # N — you manually update (Yes / No / Interview)
    ]
    sheet.insert_row(headers, 1)

    # Sample row so you can see the format
    sample = [
        "Zepto",
        "zepto.com",
        "Quick Commerce",
        "Series D",
        "Rahul Mehta",
        "HR Manager",
        "rahul@zepto.com",
        "Backend Engineer",
        "",   # auto-filled
        "",   # groq-filled
        "",   # groq-filled
        "",   # leave blank — set to "Approved" when ready to send
        "",   # auto-filled
        "",   # you fill manually
    ]
    sheet.append_row(sample)

    # Share the sheet with yourself (so you can view it in browser)
    your_email = os.getenv("MY_EMAIL")
    if your_email:
        spreadsheet.share(your_email, perm_type="user", role="writer")
        print(f"✓ Sheet shared with {your_email}")

    print(f"\n✓ Setup complete!")
    print(f"  Sheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")
    print(f"\n  Next steps:")
    print(f"  1. Fill in rows with company data (columns A-H)")
    print(f"  2. Run: python auto_research.py   ← fills columns I, J, K automatically")
    print(f"  3. Review the sheet, set Status = 'Approved' for rows you're happy with")
    print(f"  4. Run: python generate_emails.py ← sends emails for Approved rows")

if __name__ == "__main__":
    setup()
