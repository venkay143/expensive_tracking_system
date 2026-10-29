# Expense Tracker — USS Lab Mini Project

## Features
- Dashboard: monthly and all-time spending, average, transaction count
- Add, edit, delete, search and filter expenses
- Categories and payment methods
- Category and monthly trend charts
- Date-range reports and CSV export
- SQLite database

## Run locally
1. Install Python 3.10+.
2. In this folder run `pip install -r requirements.txt`.
3. Run `streamlit run app.py`.
4. Open the local URL printed in the terminal.

## Deploy
1. Upload `app.py`, `requirements.txt`, and `README.md` to a GitHub repository.
2. Sign in at https://share.streamlit.io/ with GitHub.
3. Choose Create app, select your repository and branch, and set main file path to `app.py`.
4. Deploy and share the generated URL.

## Important database note
This starter uses a local SQLite file. On cloud hosts, local files may not be durable across restarts or rebuilds. For persistent online data, connect a hosted database such as Supabase/Postgres. Keep CSV backups for your demonstration.

## Demo steps
1. Add three sample expenses.
2. Show dashboard totals and charts.
3. Edit a record and delete another.
4. Open Reports and download CSV.

Understand the CRUD operations and SQL table before presenting the project.
