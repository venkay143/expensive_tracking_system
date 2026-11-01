
import sqlite3
import hashlib
import secrets
import hmac
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px


# -------------------- CONFIGURATION --------------------

DB = Path(__file__).parent / "expenses.db"

CATEGORIES = [
    "Food", "Transport", "Shopping", "Bills", "Education",
    "Health", "Entertainment", "Travel", "Other"
]

st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💸",
    layout="wide"
)


# -------------------- DATABASE CONNECTION --------------------

def connect():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        200000
    ).hex()
    return f"{salt}${hashed}"


def verify_password(password, stored_hash):
    try:
        salt, saved_hash = stored_hash.split("$")
        check_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200000
        ).hex()
        return hmac.compare_digest(check_hash, saved_hash)
    except (ValueError, AttributeError):
        return False


def init_db():
    with connect() as c:

        # Expenses table
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                payment_method TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                user_id INTEGER
            )
        """)

        # Upgrade an existing expenses table if needed
        columns = [
            row["name"]
            for row in c.execute("PRAGMA table_info(expenses)").fetchall()
        ]

        if "user_id" not in columns:
            c.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER")

        # Users table
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
        """)

        # Create default admin if one does not exist
        admin = c.execute(
            "SELECT id FROM users WHERE username = ?",
            ("admin",)
        ).fetchone()

        if admin is None:
            c.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", hash_password("Admin@123"), "admin")
            )

        c.commit()


# -------------------- USER AUTHENTICATION --------------------

def register_user(username, password):
    username = username.strip()

    if len(username) < 3:
        return False, "Username must contain at least 3 characters."

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    try:
        with connect() as c:
            c.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hash_password(password), "user")
            )
            c.commit()

        return True, "Registration successful! You can now log in."

    except sqlite3.IntegrityError:
        return False, "This username already exists."


def login_user(username, password):
    with connect() as c:
        user = c.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),)
        ).fetchone()

    if user and verify_password(password, user["password"]):
        return dict(user)

    return None


def logout():
    for key in ["logged_in", "user_id", "username", "role"]:
        st.session_state.pop(key, None)

    st.rerun()


# -------------------- EXPENSE FUNCTIONS --------------------

def load_data(user_id, role):
    with connect() as c:
        if role == "admin":
            rows = c.execute("""
                SELECT expenses.*, users.username
                FROM expenses
                LEFT JOIN users ON expenses.user_id = users.id
                ORDER BY expense_date DESC, expenses.id DESC
            """).fetchall()
        else:
            rows = c.execute("""
                SELECT * FROM expenses
                WHERE user_id = ?
                ORDER BY expense_date DESC, id DESC
            """, (user_id,)).fetchall()

    d = pd.DataFrame([dict(r) for r in rows])

    if not d.empty:
        d["expense_date"] = pd.to_datetime(d["expense_date"])
        d["month"] = d["expense_date"].dt.to_period("M").astype(str)

    return d


def money(n):
    return f"₹{n:,.2f}"


def add_expense(user_id, d, title, category, amount, method, notes):
    with connect() as c:
        c.execute("""
            INSERT INTO expenses
            (expense_date, title, category, amount,
             payment_method, notes, created_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            d.isoformat(),
            title.strip(),
            category,
            float(amount),
            method,
            notes.strip(),
            datetime.now().isoformat(timespec="seconds"),
            user_id
        ))
        c.commit()


def update_expense(i, user_id, role, d, title, category,
                   amount, method, notes):

    with connect() as c:
        if role == "admin":
            c.execute("""
                UPDATE expenses
                SET expense_date=?, title=?, category=?, amount=?,
                    payment_method=?, notes=?
                WHERE id=?
            """, (
                d.isoformat(), title.strip(), category,
                float(amount), method, notes.strip(), int(i)
            ))
        else:
            c.execute("""
                UPDATE expenses
                SET expense_date=?, title=?, category=?, amount=?,
                    payment_method=?, notes=?
                WHERE id=? AND user_id=?
            """, (
                d.isoformat(), title.strip(), category,
                float(amount), method, notes.strip(), int(i), user_id
            ))

        c.commit()


def delete_expense(i, user_id, role):
    with connect() as c:
        if role == "admin":
            c.execute(
                "DELETE FROM expenses WHERE id=?",
                (int(i),)
            )
        else:
            c.execute(
                "DELETE FROM expenses WHERE id=? AND user_id=?",
                (int(i), user_id)
            )

        c.commit()


# -------------------- INITIALIZE APPLICATION --------------------

init_db()


# -------------------- LOGIN PAGE --------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


def show_login_page():

    st.title("💸 Expense Tracker")
    st.caption("Manage your expenses easily and securely.")

    st.markdown("---")

    left, middle, right = st.columns([1, 2, 1])

    with middle:

        login_tab, register_tab = st.tabs(
            ["🔐 Login", "📝 Register"]
        )

        with login_tab:
            st.subheader("Welcome Back")

            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input(
                    "Password",
                    type="password"
                )

                submitted = st.form_submit_button(
                    "Login",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    if not username or not password:
                        st.error("Please enter username and password.")
                    else:
                        user = login_user(username, password)

                        if user:
                            st.session_state.logged_in = True
                            st.session_state.user_id = user["id"]
                            st.session_state.username = user["username"]
                            st.session_state.role = user["role"]

                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")

        with register_tab:
            st.subheader("Create a New Account")

            with st.form("register_form"):
                new_username = st.text_input("Choose Username")
                new_password = st.text_input(
                    "Choose Password",
                    type="password"
                )
                confirm_password = st.text_input(
                    "Confirm Password",
                    type="password"
                )

                registered = st.form_submit_button(
                    "Register",
                    type="primary",
                    use_container_width=True
                )

                if registered:
                    if not new_username or not new_password:
                        st.error("Please fill in all fields.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        success, message = register_user(
                            new_username,
                            new_password
                        )

                        if success:
                            st.success(message)
                        else:
                            st.error(message)

    st.markdown("---")
    st.caption("Expense Tracker | Python • Streamlit • SQLite")


if not st.session_state.logged_in:
    show_login_page()
    st.stop()


# -------------------- LOGGED-IN USER DETAILS --------------------

user_id = st.session_state.user_id
username = st.session_state.username
role = st.session_state.role

df = load_data(user_id, role)


# -------------------- SIDEBAR NAVIGATION --------------------

st.title("💸 Expense Tracker")

with st.sidebar:

    st.title("Account")
    st.write(f"Welcome, **{username}**")

    if role == "admin":
        st.success("Administrator")
    else:
        st.info("User Account")

    if st.button("Logout", use_container_width=True):
        logout()

    st.divider()

    st.header("Menu")

    if role == "admin":
        pages = ["Admin Dashboard", "All Expenses"]
    else:
        pages = [
            "Dashboard",
            "Add Expense",
            "Manage Expenses",
            "Reports"
        ]

    page = st.radio("Navigate", pages)

    st.divider()
    st.caption("USS Lab Mini Project")
    st.caption("Python • Streamlit • SQLite")


# -------------------- ADMIN DASHBOARD --------------------

if page == "Admin Dashboard":

    st.subheader("🛡️ Admin Dashboard")

    with connect() as c:
        total_users = c.execute(
            "SELECT COUNT(*) FROM users WHERE role='user'"
        ).fetchone()[0]

        total_expenses = c.execute(
            "SELECT COUNT(*) FROM expenses"
        ).fetchone()[0]

        total_amount = c.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses"
        ).fetchone()[0]

    a, b, c = st.columns(3)

    a.metric("Registered Users", total_users)
    b.metric("Total Transactions", total_expenses)
    c.metric("Total Expenses", money(total_amount))

    st.markdown("### Registered Users")

    with connect() as c:
        users = c.execute("""
            SELECT id, username, role
            FROM users
            ORDER BY id
        """).fetchall()

    users_df = pd.DataFrame([dict(u) for u in users])

    if not users_df.empty:
        st.dataframe(
            users_df,
            use_container_width=True,
            hide_index=True
        )

    st.markdown("### Recent Expenses")

    if not df.empty:
        columns = [
            "username", "expense_date", "title",
            "category", "amount", "payment_method"
        ]

        view = df[[x for x in columns if x in df.columns]].head(10).copy()
        view["expense_date"] = view["expense_date"].dt.strftime("%Y-%m-%d")

        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No expenses have been recorded yet.")


# -------------------- ADMIN ALL EXPENSES --------------------

elif page == "All Expenses":

    st.subheader("All Users' Expenses")

    if df.empty:
        st.info("No expenses available.")
    else:
        view = df.copy()
        view["expense_date"] = view["expense_date"].dt.strftime("%Y-%m-%d")

        columns = [
            "id", "username", "expense_date", "title",
            "category", "amount", "payment_method", "notes"
        ]

        st.dataframe(
            view[[x for x in columns if x in view.columns]],
            use_container_width=True,
            hide_index=True
        )

        st.metric(
            "Total Expenses",
            money(df["amount"].sum())
        )

        st.download_button(
            "Download All Expenses",
            df.drop(columns=["month"], errors="ignore").to_csv(
                index=False
            ).encode("utf-8"),
            "all_expenses.csv",
            "text/csv"
        )


# -------------------- USER DASHBOARD --------------------

elif page == "Dashboard":

    st.subheader("Spending at a glance")

    now = pd.Timestamp(date.today())

    month_df = (
        df[df["expense_date"] >= now.replace(day=1)]
        if not df.empty else df
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Spent this month",
        money(month_df["amount"].sum())
        if not month_df.empty else "₹0.00"
    )

    b.metric(
        "All-time spending",
        money(df["amount"].sum())
        if not df.empty else "₹0.00"
    )

    c.metric("Transactions", len(df))

    d.metric(
        "Average expense",
        money(df["amount"].mean())
        if not df.empty else "₹0.00"
    )

    left, right = st.columns(2)

    with left:
        st.markdown("#### Spending by category")

        if not df.empty:
            st.bar_chart(
                df.groupby("category")["amount"]
                .sum()
                .sort_values(ascending=False)
            )
        else:
            st.info("Add an expense to see your chart.")

    with right:
        st.markdown("#### Monthly spending trend")

        if not df.empty:
            st.line_chart(
                df.groupby("month")["amount"]
                .sum()
                .sort_index()
            )
        else:
            st.info("Your monthly trend will appear here.")

    # -------------------- INTERACTIVE EXPENSE CHARTS --------------------
    st.divider()
    st.subheader("📊 Expense Analytics")

    if not df.empty:
        category_data = (
            df.groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )
        monthly_data = (
            df.groupby("month", as_index=False)["amount"]
            .sum()
            .sort_values("month")
        )
        payment_data = (
            df.groupby("payment_method", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )

        chart_left, chart_right = st.columns(2)

        with chart_left:
            st.markdown("#### Category-wise Spending")
            pie_fig = px.pie(
                category_data,
                names="category",
                values="amount",
                hole=0.35,
                title="Expense Distribution by Category"
            )
            pie_fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="%{label}<br>Amount: ₹%{value:,.2f}<br>Share: %{percent}<extra></extra>"
            )
            st.plotly_chart(pie_fig, use_container_width=True)

        with chart_right:
            st.markdown("#### Monthly Expense Comparison")
            bar_fig = px.bar(
                monthly_data,
                x="month",
                y="amount",
                text_auto=".2s",
                title="Total Spending per Month",
                labels={"month": "Month", "amount": "Amount (₹)"}
            )
            bar_fig.update_layout(xaxis_title="Month", yaxis_title="Amount (₹)")
            st.plotly_chart(bar_fig, use_container_width=True)

        chart_left, chart_right = st.columns(2)

        with chart_left:
            st.markdown("#### Payment Method Distribution")
            donut_fig = px.pie(
                payment_data,
                names="payment_method",
                values="amount",
                hole=0.55,
                title="Spending by Payment Method"
            )
            donut_fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="%{label}<br>Amount: ₹%{value:,.2f}<br>Share: %{percent}<extra></extra>"
            )
            st.plotly_chart(donut_fig, use_container_width=True)

        with chart_right:
            st.markdown("#### Monthly Spending Trend")
            line_fig = px.line(
                monthly_data,
                x="month",
                y="amount",
                markers=True,
                title="How Your Spending Changes Over Time",
                labels={"month": "Month", "amount": "Amount (₹)"}
            )
            line_fig.update_layout(xaxis_title="Month", yaxis_title="Amount (₹)")
            st.plotly_chart(line_fig, use_container_width=True)
    else:
        st.info("Add expenses to view pie charts and spending graphs.")

    st.markdown("#### Recent expenses")

    if not df.empty:
        view = df.head(8)[
            ["expense_date", "title", "category",
             "amount", "payment_method"]
        ].copy()

        view["expense_date"] = view["expense_date"].dt.strftime(
            "%Y-%m-%d"
        )

        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Choose Add Expense from the sidebar to get started.")


# -------------------- ADD EXPENSE --------------------

elif page == "Add Expense":

    st.subheader("Add a new expense")

    with st.form("add_form", clear_on_submit=True):

        x, y = st.columns(2)

        with x:
            d = st.date_input("Date", date.today())
            title = st.text_input(
                "Expense title",
                placeholder="e.g. Lunch"
            )
            category = st.selectbox("Category", CATEGORIES)

        with y:
            amount = st.number_input(
                "Amount (₹)",
                min_value=0.0,
                value=0.0,
                step=10.0
            )

            method = st.selectbox(
                "Payment method",
                ["Cash", "UPI", "Card", "Bank Transfer", "Other"]
            )

            notes = st.text_input("Notes (optional)")

        submitted = st.form_submit_button(
            "Save expense",
            type="primary",
            use_container_width=True
        )

        if submitted:

            if not title.strip():
                st.error("Enter an expense title.")

            elif amount <= 0:
                st.error("Amount must be greater than zero.")

            else:
                add_expense(
                    user_id, d, title, category,
                    amount, method, notes
                )

                st.success("Expense saved.")
                st.rerun()


# -------------------- MANAGE EXPENSES --------------------

elif page == "Manage Expenses":

    st.subheader("Manage transactions")

    if df.empty:
        st.info("No expenses yet.")

    else:
        x, y = st.columns(2)

        search = x.text_input("Search title or notes")

        category_filter = y.selectbox(
            "Category filter",
            ["All categories"] + CATEGORIES
        )

        f = df.copy()

        if search.strip():
            q = search.strip().lower()

            f = f[
                f["title"].str.lower().str.contains(q, na=False)
                |
                f["notes"].fillna("").str.lower().str.contains(q, na=False)
            ]

        if category_filter != "All categories":
            f = f[f["category"] == category_filter]

        view = f[
            ["id", "expense_date", "title", "category",
             "amount", "payment_method", "notes"]
        ].copy()

        view["expense_date"] = view["expense_date"].dt.strftime(
            "%Y-%m-%d"
        )

        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True
        )

        if not f.empty:

            st.markdown("#### Edit or delete")

            ids = f["id"].astype(int).tolist()

            chosen = st.selectbox(
                "Choose transaction",
                ids,
                format_func=lambda i: (
                    f"#{i} — "
                    f"{f.loc[f['id'] == i, 'title'].iloc[0]}"
                )
            )

            row = df.loc[df["id"] == chosen].iloc[0]

            tab1, tab2 = st.tabs(["Edit", "Delete"])

            with tab1:

                with st.form("edit_form"):

                    x, y = st.columns(2)

                    with x:
                        nd = st.date_input(
                            "Date",
                            row["expense_date"].date()
                        )

                        nt = st.text_input(
                            "Title",
                            str(row["title"])
                        )

                        oldcat = str(row["category"])

                        nc = st.selectbox(
                            "Category",
                            CATEGORIES,
                            index=(
                                CATEGORIES.index(oldcat)
                                if oldcat in CATEGORIES else 0
                            )
                        )

                    with y:
                        na = st.number_input(
                            "Amount (₹)",
                            min_value=0.01,
                            value=float(row["amount"]),
                            step=10.0
                        )

                        methods = [
                            "Cash", "UPI", "Card",
                            "Bank Transfer", "Other"
                        ]

                        oldmethod = str(row["payment_method"])

                        nm = st.selectbox(
                            "Payment method",
                            methods,
                            index=(
                                methods.index(oldmethod)
                                if oldmethod in methods else 0
                            )
                        )

                        nn = st.text_input(
                            "Notes",
                            str(row["notes"] or "")
                        )

                    if st.form_submit_button(
                        "Update expense",
                        type="primary"
                    ):

                        if not nt.strip():
                            st.error("Title cannot be empty.")

                        else:
                            update_expense(
                                chosen, user_id, role,
                                nd, nt, nc, na, nm, nn
                            )

                            st.success("Updated.")
                            st.rerun()

            with tab2:

                st.warning(
                    f"Delete '{row['title']}' for "
                    f"{money(float(row['amount']))}?"
                )

                if st.button(
                    "Delete selected expense",
                    type="primary"
                ):

                    delete_expense(chosen, user_id, role)

                    st.success("Deleted.")
                    st.rerun()


# -------------------- REPORTS --------------------

elif page == "Reports":

    st.subheader("Reports and CSV export")

    if df.empty:
        st.info("Add expenses to create reports.")

    else:
        mn = df["expense_date"].min().date()
        mx = df["expense_date"].max().date()

        x, y = st.columns(2)

        start = x.date_input("From date", mn)
        end = y.date_input("To date", mx)

        if start > end:
            st.error("From date must not be after To date.")

        else:
            report = df[
                (df["expense_date"].dt.date >= start)
                &
                (df["expense_date"].dt.date <= end)
            ]

            st.metric(
                "Total in selected period",
                money(report["amount"].sum())
            )

            if not report.empty:

                st.markdown("#### Category summary")

                st.dataframe(
                    report.groupby(
                        "category",
                        as_index=False
                    )["amount"]
                    .sum()
                    .sort_values("amount", ascending=False),
                    use_container_width=True,
                    hide_index=True
                )

                st.markdown("#### Transactions")

                st.dataframe(
                    report[
                        ["expense_date", "title", "category",
                         "amount", "payment_method", "notes"]
                    ],
                    use_container_width=True,
                    hide_index=True
                )

            else:
                st.info("No expenses in this date range.")

    st.divider()

    st.markdown("#### Download your backup")

    export = load_data(user_id, role)

    if not export.empty:

        csv = export.drop(
            columns=["month", "username"],
            errors="ignore"
        ).to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download expenses as CSV",
            csv,
            "expense_tracker_backup.csv",
            "text/csv"
        )

    else:
        st.caption("Add expenses to enable CSV export.")


# -------------------- FOOTER --------------------

st.divider()

st.caption(
    "Expense Tracker • Python + Streamlit + SQLite"
)
