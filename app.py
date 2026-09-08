import os
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

@app.template_filter("pkr")
def pkr(amount):
    try:
        return f"PKR {float(amount):,.2f}"
    except (TypeError, ValueError):
        return "PKR 0.00"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="Please fill in all fields.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return render_template("register.html", error="An account with this email already exists.")

    password_hash = generate_password_hash(password)
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    conn.close()

    return render_template("register.html", success="Account created! Redirecting to login...")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Please fill in all fields.")

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

def _active_range(args):
    """Parse ?start / ?end query args into (start_iso, end_iso, label).

    Returns (None, None, None) unless both values parse as YYYY-MM-DD and
    start <= end, so malformed, partial or reversed input falls back to the
    unfiltered view rather than erroring or half-applying a filter.
    """
    def _parse_date(value):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    start_date = _parse_date(args.get("start", ""))
    end_date = _parse_date(args.get("end", ""))
    if not (start_date and end_date and start_date <= end_date):
        return None, None, None

    label = f'{start_date:%d %b %Y} – {end_date:%d %b %Y}'
    return start_date.isoformat(), end_date.isoformat(), label


def _date_presets(today):
    """One-click date ranges for the profile filter bar."""
    if today.month == 12:
        month_end = today.replace(day=31)
    else:
        # first day of next month, minus one day
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return [
        {"label": "This month", "start": today.replace(day=1).isoformat(), "end": month_end.isoformat()},
        {"label": "Last 30 days", "start": (today - timedelta(days=29)).isoformat(), "end": today.isoformat()},
        {"label": "This year", "start": date(today.year, 1, 1).isoformat(), "end": date(today.year, 12, 31).isoformat()},
    ]


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    if user is None:                      # stale session -> force re-login
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    start, end, range_label = _active_range(request.args)

    query = "SELECT amount, category, date, description FROM expenses WHERE user_id = ?"
    params = [session["user_id"]]
    if start and end:
        # expenses.date is a zero-padded YYYY-MM-DD string, so this lexicographic
        # compare via bind params is an inclusive calendar-date range.
        query += " AND date >= ? AND date <= ?"
        params += [start, end]
    query += " ORDER BY date DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    total = sum(r["amount"] for r in rows)
    count = len(rows)

    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]
    categories = sorted(
        (
            {
                "name": name,
                "amount": amt,
                "pct": round(amt / total * 100) if total else 0,
            }
            for name, amt in by_cat.items()
        ),
        key=lambda c: c["amount"],
        reverse=True,
    )
    top_category = categories[0]["name"] if categories else None

    member_since = None
    if user["created_at"]:
        try:
            member_since = datetime.strptime(
                user["created_at"], "%Y-%m-%d %H:%M:%S"
            ).strftime("%B %Y")
        except ValueError:
            member_since = user["created_at"][:10]

    presets = _date_presets(date.today())

    return render_template(
        "profile.html",
        user=user,
        member_since=member_since,
        total=total,
        count=count,
        categories=categories,
        top_category=top_category,
        recent=rows[:6],
        start=start,
        end=end,
        range_label=range_label,
        presets=presets,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
