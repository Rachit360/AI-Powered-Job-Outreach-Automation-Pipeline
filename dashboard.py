"""
dashboard.py — Generates a visual HTML dashboard
from your outreach_log.csv file
"""

import pandas as pd
import os
from datetime import datetime

def generate_dashboard():
    csv_file = "outreach_log.csv"
    
    if not os.path.isfile(csv_file):
        print("No outreach_log.csv found. Send some emails first.")
        return

    df = pd.read_csv(csv_file)

    total_sent = len(df)
    companies = df["company"].nunique() if "company" in df.columns else 0

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Job Outreach Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; min-width: 150px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card h2 {{ margin: 0; font-size: 36px; color: #4CAF50; }}
        .card p {{ margin: 5px 0 0; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background: #4CAF50; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        tr:last-child td {{ border-bottom: none; }}
    </style>
</head>
<body>
    <h1>Job Outreach Dashboard</h1>
    <p>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    <div class="stats">
        <div class="card"><h2>{total_sent}</h2><p>Emails Sent</p></div>
        <div class="card"><h2>{companies}</h2><p>Companies</p></div>
    </div>
    <h2>Outreach Log</h2>
    {df.to_html(index=False)}
</body>
</html>
"""

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard saved to: {os.path.abspath('dashboard.html')}")

    print("Dashboard generated — open dashboard.html in your browser")

if __name__ == "__main__":
    generate_dashboard()