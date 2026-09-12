"""
Tests for the "Add Expense" feature (spec: .claude/specs/07-add-expense.md).

These tests are derived strictly from the spec's Definition of Done and
Rules for implementation, NOT from reading app.py's add_expense route logic.
app.py / database/db.py were only consulted to understand existing structure
(how the Flask app + DB are wired up, the users/expenses schema, and the
GET/POST-on-one-view pattern used by /login and /register), never to derive
expected behavior for this feature.

DB isolation strategy
----------------------
app.py runs `init_db()` + `seed_db()` against `database.db.DB_PATH` at
*import time*. To guarantee the real `expense_tracker.db` file on disk is
never touched by this suite, we monkeypatch `database.db.DB_PATH` to a
throwaway temp file BEFORE importing `app` (module-level code below, which
pytest executes once during collection). Tables are wiped before each test
via an autouse fixture so tests stay independent despite sharing one file.
"""

import os
import tempfile
from datetime import date, timedelta

import pytest

import database.db as db_module

# --- Redirect DB_PATH to a temp file BEFORE importing app -----------------
_tmp_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_tmp_fd)
db_module.DB_PATH = _TEST_DB_PATH

from app import app as flask_app  # noqa: E402  (must import after DB_PATH patch)
from database.db import get_db, CATEGORIES  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_tables():
    """Wipe users/expenses before every test so tests don't leak state."""
    conn = get_db()
    conn.execute("DELETE FROM expenses")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    yield


@pytest.fixture
def client():
    flask_app.config.update({"TESTING": True})
    return flask_app.test_client()


def _register_and_login(client, name="Test User", email="test@example.com", password="password123"):
    client.post("/register", data={"name": name, "email": email, "password": password})
    resp = client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False
    )
    assert resp.status_code == 302, "Setup failed: login did not succeed"
    return resp


def _user_id_by_email(email):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"] if row else None


def _expense_count():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    conn.close()
    return n


@pytest.fixture
def auth_client(client):
    """Logged-in client for user test@example.com."""
    _register_and_login(client)
    return client


def valid_payload(**overrides):
    payload = {
        "amount": "42.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Test lunch",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- #
# 1. GET while logged out redirects to /login
# --------------------------------------------------------------------- #

def test_get_add_expense_logged_out_redirects_to_login(client):
    resp = client.get("/expenses/add", follow_redirects=False)
    assert resp.status_code == 302, "Unauthenticated GET should redirect, not render the form"
    assert "/login" in resp.headers.get("Location", ""), "Should redirect to the login page"


# --------------------------------------------------------------------- #
# 2. GET while logged in renders the form
# --------------------------------------------------------------------- #

def test_get_add_expense_logged_in_renders_form(auth_client):
    resp = auth_client.get("/expenses/add")
    assert resp.status_code == 200, "Logged-in GET should render the add-expense form"

    html = resp.data.decode()
    assert 'name="amount"' in html, "Form should contain an amount field"
    assert 'name="category"' in html, "Form should contain a category field"
    assert 'name="date"' in html, "Form should contain a date field"
    assert 'name="description"' in html, "Form should contain a description field"

    for category in CATEGORIES:
        assert category in html, f"Category '{category}' from CATEGORIES should be offered in the form"


# --------------------------------------------------------------------- #
# 3. POST while logged out redirects to /login and does not insert
# --------------------------------------------------------------------- #

def test_post_add_expense_logged_out_redirects_and_does_not_insert(client):
    before = _expense_count()
    resp = client.post("/expenses/add", data=valid_payload(), follow_redirects=False)
    assert resp.status_code == 302, "Unauthenticated POST should redirect, not process the form"
    assert "/login" in resp.headers.get("Location", ""), "Should redirect to the login page"
    assert _expense_count() == before, "No expense should be inserted for an unauthenticated request"


# --------------------------------------------------------------------- #
# 4 & 5. Valid POST creates the row for the current user, redirects to
#         /profile, and the new expense shows up in profile data
# --------------------------------------------------------------------- #

def test_post_valid_expense_creates_row_and_redirects_to_profile(auth_client):
    user_id = _user_id_by_email("test@example.com")
    before = _expense_count()

    payload = valid_payload(amount="99.99", category="Shopping", description="New shoes for spec test")
    resp = auth_client.post("/expenses/add", data=payload, follow_redirects=False)

    assert resp.status_code == 302, "A valid submission should redirect (to /profile)"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile on success"
    assert _expense_count() == before + 1, "Exactly one new expense row should be inserted"

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    ).fetchone()
    conn.close()

    assert row is not None, "The inserted expense should belong to the logged-in user"
    assert row["amount"] == 99.99, "Inserted amount should match the submitted amount"
    assert row["category"] == "Shopping", "Inserted category should match the submitted category"
    assert row["date"] == payload["date"], "Inserted date should match the submitted date"
    assert row["description"] == "New shoes for spec test", "Inserted description should match submission"


def test_new_expense_appears_on_profile_page(auth_client):
    payload = valid_payload(amount="123.45", category="Bills", description="Water bill unique marker")
    auth_client.post("/expenses/add", data=payload, follow_redirects=False)

    profile_resp = auth_client.get("/profile")
    assert profile_resp.status_code == 200

    html = profile_resp.data.decode()
    assert "Water bill unique marker" in html or "123.45" in html or "123" in html, (
        "The newly added expense should appear in the profile page's recent expenses/totals"
    )

    conn = get_db()
    user_id = _user_id_by_email("test@example.com")
    total = conn.execute(
        "SELECT SUM(amount) AS total FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["total"]
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    conn.close()

    assert count == 1, "The user should now have exactly one recorded expense"
    assert total == pytest.approx(123.45), "The total should reflect the newly added expense"


# --------------------------------------------------------------------- #
# 6. Missing/invalid amount: blank, negative, non-numeric
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["", "-10", "-0.01", "not-a-number", "abc"],
    ids=["blank", "negative", "negative-decimal", "non-numeric", "letters"],
)
def test_post_invalid_amount_rerenders_with_error_and_does_not_insert(auth_client, bad_amount):
    before = _expense_count()
    resp = auth_client.post("/expenses/add", data=valid_payload(amount=bad_amount), follow_redirects=False)

    assert resp.status_code == 200, "Invalid amount should re-render the form, not redirect"
    assert 'name="amount"' in resp.data.decode(), "The add-expense form should be re-rendered on error"
    assert _expense_count() == before, "No row should be inserted when the amount is invalid"


# --------------------------------------------------------------------- #
# 7. Invalid category
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_category",
    ["", "NotARealCategory", "food", "<script>alert(1)</script>"],
    ids=["blank", "unknown", "wrong-case", "injection-like"],
)
def test_post_invalid_category_rerenders_with_error_and_does_not_insert(auth_client, bad_category):
    before = _expense_count()
    resp = auth_client.post(
        "/expenses/add", data=valid_payload(category=bad_category), follow_redirects=False
    )

    assert resp.status_code == 200, "Invalid category should re-render the form, not redirect"
    assert 'name="amount"' in resp.data.decode(), "The add-expense form should be re-rendered on error"
    assert _expense_count() == before, "No row should be inserted when the category is invalid"


# --------------------------------------------------------------------- #
# 8. Invalid date
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_date",
    ["", "not-a-date", "13/25/2026", "2026-13-40", "2026/09/12"],
    ids=["blank", "garbage", "us-format-invalid-month", "invalid-month-day", "wrong-separator"],
)
def test_post_invalid_date_rerenders_with_error_and_does_not_insert(auth_client, bad_date):
    before = _expense_count()
    resp = auth_client.post("/expenses/add", data=valid_payload(date=bad_date), follow_redirects=False)

    assert resp.status_code == 200, "Invalid date should re-render the form, not redirect"
    assert 'name="amount"' in resp.data.decode(), "The add-expense form should be re-rendered on error"
    assert _expense_count() == before, "No row should be inserted when the date is invalid"


# --------------------------------------------------------------------- #
# 9. Cannot record an expense under a different user_id
# --------------------------------------------------------------------- #

def test_post_ignores_submitted_user_id_and_uses_session_user(client):
    # Victim account whose id an attacker will try to spoof.
    client.post(
        "/register",
        data={"name": "Victim", "email": "victim@example.com", "password": "password123"},
    )
    victim_id = _user_id_by_email("victim@example.com")

    # Attacker registers, logs in as themselves.
    client.post(
        "/register",
        data={"name": "Attacker", "email": "attacker@example.com", "password": "password123"},
    )
    client.post("/login", data={"email": "attacker@example.com", "password": "password123"})
    attacker_id = _user_id_by_email("attacker@example.com")

    assert victim_id != attacker_id, "Test setup requires two distinct users"

    payload = valid_payload(user_id=str(victim_id), amount="55.00", description="Spoof attempt")
    resp = client.post("/expenses/add", data=payload, follow_redirects=False)
    assert resp.status_code == 302, "Valid data should still succeed even with an extraneous user_id field"

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE description = ?", ("Spoof attempt",)
    ).fetchone()
    victim_rows = conn.execute(
        "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (victim_id,)
    ).fetchone()["n"]
    conn.close()

    assert row is not None, "The expense should still be inserted"
    assert row["user_id"] == attacker_id, (
        "The expense must be recorded under the authenticated session user, "
        "never a user_id value taken from the submitted form"
    )
    assert victim_rows == 0, "The victim account must not receive an expense it never submitted"
