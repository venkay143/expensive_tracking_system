import sqlite3
from datetime import date, datetime
from pathlib import Path
import pandas as pd
import streamlit as st

DB = Path(__file__).parent / "expenses.db"
CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Education", "Health", "Entertainment", "Travel", "Other"]
st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="wide")

def connect():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL, title TEXT NOT NULL, category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0), payment_method TEXT NOT NULL,
            notes TEXT DEFAULT '', created_at TEXT NOT NULL)""")
        c.commit()

def load_data():
    with connect() as c:
        rows = c.execute("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC").fetchall()
    d = pd.DataFrame([dict(r) for r in rows])
    if not d.empty:
        d["expense_date"] = pd.to_datetime(d["expense_date"])
        d["month"] = d["expense_date"].dt.to_period("M").astype(str)
    return d

def money(n):
    return f"₹{n:,.2f}"

def add_expense(d, title, category, amount, method, notes):
    with connect() as c:
        c.execute("INSERT INTO expenses (expense_date,title,category,amount,payment_method,notes,created_at) VALUES (?,?,?,?,?,?,?)",
                  (d.isoformat(), title.strip(), category, float(amount), method, notes.strip(), datetime.now().isoformat(timespec="seconds")))
        c.commit()

def update_expense(i, d, title, category, amount, method, notes):
    with connect() as c:
        c.execute("UPDATE expenses SET expense_date=?,title=?,category=?,amount=?,payment_method=?,notes=? WHERE id=?",
                  (d.isoformat(), title.strip(), category, float(amount), method, notes.strip(), int(i)))
        c.commit()

def delete_expense(i):
    with connect() as c:
        c.execute("DELETE FROM expenses WHERE id=?", (int(i),))
        c.commit()

init_db()
st.title("💸 Expense Tracker")
st.caption("Track spending, understand patterns, and export your records.")
with st.sidebar:
    st.header("Menu")
    page = st.radio("Navigate", ["Dashboard", "Add Expense", "Manage Expenses", "Reports"])
    st.divider()
    st.caption("USS Lab Mini Project")
    st.caption("Python • Streamlit • SQLite")

df = load_data()
if page == "Dashboard":
    st.subheader("Spending at a glance")
    now = pd.Timestamp(date.today())
    month_df = df[df["expense_date"] >= now.replace(day=1)] if not df.empty else df
    a, b, c, d = st.columns(4)
    a.metric("Spent this month", money(month_df["amount"].sum()) if not month_df.empty else "₹0.00")
    b.metric("All-time spending", money(df["amount"].sum()) if not df.empty else "₹0.00")
    c.metric("Transactions", len(df))
    d.metric("Average expense", money(df["amount"].mean()) if not df.empty else "₹0.00")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Spending by category")
        if not df.empty:
            st.bar_chart(df.groupby("category")["amount"].sum().sort_values(ascending=False))
        else:
            st.info("Add an expense to see your chart.")
    with right:
        st.markdown("#### Monthly spending trend")
        if not df.empty:
            st.line_chart(df.groupby("month")["amount"].sum().sort_index())
        else:
            st.info("Your monthly trend will appear here.")
    st.markdown("#### Recent expenses")
    if not df.empty:
        view = df.head(8)[["expense_date","title","category","amount","payment_method"]].copy()
        view["expense_date"] = view["expense_date"].dt.strftime("%Y-%m-%d")
        st.dataframe(view, use_container_width=True, hide_index=True)
    else:
        st.info("Choose **Add Expense** from the sidebar to get started.")

elif page == "Add Expense":
    st.subheader("Add a new expense")
    with st.form("add_form", clear_on_submit=True):
        x, y = st.columns(2)
        with x:
            d = st.date_input("Date", date.today())
            title = st.text_input("Expense title", placeholder="e.g. Lunch")
            category = st.selectbox("Category", CATEGORIES)
        with y:
            amount = st.number_input("Amount (₹)", min_value=0.0, value=0.0, step=10.0)
            method = st.selectbox("Payment method", ["Cash","UPI","Card","Bank Transfer","Other"])
            notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Save expense", type="primary", use_container_width=True)
        if submitted:
            if not title.strip():
                st.error("Enter an expense title.")
            elif amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                add_expense(d, title, category, amount, method, notes)
                st.success("Expense saved.")
                st.rerun()

elif page == "Manage Expenses":
    st.subheader("Manage transactions")
    if df.empty:
        st.info("No expenses yet.")
    else:
        x, y = st.columns(2)
        search = x.text_input("Search title or notes")
        category_filter = y.selectbox("Category filter", ["All categories"] + CATEGORIES)
        f = df.copy()
        if search.strip():
            q = search.strip().lower()
            f = f[f["title"].str.lower().str.contains(q, na=False) | f["notes"].fillna("").str.lower().str.contains(q, na=False)]
        if category_filter != "All categories":
            f = f[f["category"] == category_filter]
        view = f[["id","expense_date","title","category","amount","payment_method","notes"]].copy()
        view["expense_date"] = view["expense_date"].dt.strftime("%Y-%m-%d")
        st.dataframe(view, use_container_width=True, hide_index=True)
        if not f.empty:
            st.markdown("#### Edit or delete")
            ids = f["id"].astype(int).tolist()
            chosen = st.selectbox("Choose transaction", ids, format_func=lambda i: f"#{i} — {f.loc[f['id']==i,'title'].iloc[0]}")
            row = df.loc[df["id"] == chosen].iloc[0]
            tab1, tab2 = st.tabs(["Edit", "Delete"])
            with tab1:
                with st.form("edit_form"):
                    x, y = st.columns(2)
                    with x:
                        nd = st.date_input("Date", row["expense_date"].date())
                        nt = st.text_input("Title", str(row["title"]))
                        oldcat = str(row["category"])
                        nc = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(oldcat) if oldcat in CATEGORIES else 0)
                    with y:
                        na = st.number_input("Amount (₹)", min_value=0.01, value=float(row["amount"]), step=10.0)
                        methods = ["Cash","UPI","Card","Bank Transfer","Other"]
                        oldmethod = str(row["payment_method"])
                        nm = st.selectbox("Payment method", methods, index=methods.index(oldmethod) if oldmethod in methods else 0)
                        nn = st.text_input("Notes", str(row["notes"] or ""))
                    if st.form_submit_button("Update expense", type="primary"):
                        if not nt.strip():
                            st.error("Title cannot be empty.")
                        else:
                            update_expense(chosen, nd, nt, nc, na, nm, nn)
                            st.success("Updated.")
                            st.rerun()
            with tab2:
                st.warning(f"Delete '{row['title']}' for {money(float(row['amount']))}?")
                if st.button("Delete selected expense", type="primary"):
                    delete_expense(chosen)
                    st.success("Deleted.")
                    st.rerun()

elif page == "Reports":
    st.subheader("Reports and CSV export")
    if df.empty:
        st.info("Add expenses to create reports.")
    else:
        mn, mx = df["expense_date"].min().date(), df["expense_date"].max().date()
        x, y = st.columns(2)
        start = x.date_input("From date", mn)
        end = y.date_input("To date", mx)
        if start > end:
            st.error("From date must not be after To date.")
        else:
            report = df[(df["expense_date"].dt.date >= start) & (df["expense_date"].dt.date <= end)]
            st.metric("Total in selected period", money(report["amount"].sum()))
            if not report.empty:
                st.markdown("#### Category summary")
                st.dataframe(report.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False), use_container_width=True, hide_index=True)
                st.markdown("#### Transactions")
                st.dataframe(report[["expense_date","title","category","amount","payment_method","notes"]], use_container_width=True, hide_index=True)
            else:
                st.info("No expenses in this date range.")
    st.divider()
    st.markdown("#### Download backup")
    export = load_data()
    if not export.empty:
        csv = export.drop(columns=["month"], errors="ignore").to_csv(index=False).encode("utf-8")
        st.download_button("Download all expenses as CSV", csv, "expense_tracker_backup.csv", "text/csv")
    else:
        st.caption("Add expenses to enable CSV export.")

st.divider()
st.caption("Expense Tracker • Python + Streamlit + SQLite")
