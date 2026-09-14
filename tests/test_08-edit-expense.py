"""
Tests for the "Edit Expense" feature (spec: .claude/specs/08-edit-expense.md).

These tests are derived strictly from the spec's Routes, Rules for
implementation, and Definition of Done sections, NOT from reading app.py's
edit_expense route logic. app.py / database/db.py were only consulted to
understand existing structure (how the Flask app + DB are wired up, the
users/expenses schema, and the GET/POST-on-one-view pattern already used by
/expenses/add), never to derive expected behavior for this feature.

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
from datetime import date

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


def _insert_expense(user_id, amount=50.00, category="Food", exp_date=None, description="Original description"):
    exp_date = exp_date or date.today().isoformat()
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, exp_date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _get_expense(expense_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row


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
        "amount": "77.25",
        "category": "Shopping",
        "date": date.today().isoformat(),
        "description": "Updated description",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- #
# Auth guard: GET/POST while logged out redirect to /login
# --------------------------------------------------------------------- #

def test_get_edit_expense_logged_out_redirects_to_login(client):
    user_id = None
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Owner", "owner@example.com", "hash"),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", ("owner@example.com",)).fetchone()["id"]
    conn.close()
    expense_id = _insert_expense(user_id)

    resp = client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
    assert resp.status_code == 302, "Unauthenticated GET should redirect, not render the form"
    assert "/login" in resp.headers.get("Location", ""), "Should redirect to the login page"


def test_post_edit_expense_logged_out_redirects_and_does_not_modify(client):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Owner", "owner@example.com", "hash"),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", ("owner@example.com",)).fetchone()["id"]
    conn.close()
    expense_id = _insert_expense(user_id, amount=50.00, category="Food", description="Original description")

    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(), follow_redirects=False)
    assert resp.status_code == 302, "Unauthenticated POST should redirect, not process the form"
    assert "/login" in resp.headers.get("Location", ""), "Should redirect to the login page"

    row = _get_expense(expense_id)
    assert row["amount"] == 50.00, "Expense should be unmodified for an unauthenticated request"
    assert row["category"] == "Food"
    assert row["description"] == "Original description"


# --------------------------------------------------------------------- #
# Happy path: GET shows pre-filled form
# --------------------------------------------------------------------- #

def test_get_edit_expense_own_expense_shows_prefilled_form(auth_client):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=64.50, category="Health", exp_date="2026-01-15", description="Doctor visit marker"
    )

    resp = auth_client.get(f"/expenses/{expense_id}/edit")
    assert resp.status_code == 200, "Logged-in GET for own expense should render the edit form"

    html = resp.data.decode()
    assert 'name="amount"' in html, "Form should contain an amount field"
    assert 'name="category"' in html, "Form should contain a category field"
    assert 'name="date"' in html, "Form should contain a date field"
    assert 'name="description"' in html, "Form should contain a description field"

    assert "64.5" in html or "64.50" in html, "Form should be pre-filled with the existing amount"
    assert "2026-01-15" in html, "Form should be pre-filled with the existing date"
    assert "Doctor visit marker" in html, "Form should be pre-filled with the existing description"

    for category in CATEGORIES:
        assert category in html, f"Category '{category}' from CATEGORIES should be offered in the form"


# --------------------------------------------------------------------- #
# Happy path: valid POST updates the existing row and redirects
# --------------------------------------------------------------------- #

def test_post_valid_edit_updates_existing_row_and_redirects_to_profile(auth_client):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=50.00, category="Food", exp_date="2026-01-01", description="Original description"
    )
    before_count = _expense_count()

    payload = valid_payload(amount="88.88", category="Bills", date="2026-02-02", description="Edited value marker")
    resp = auth_client.post(f"/expenses/{expense_id}/edit", data=payload, follow_redirects=False)

    assert resp.status_code == 302, "A valid submission should redirect (to /profile)"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile on success"
    assert _expense_count() == before_count, "Editing must not create a new row"

    row = _get_expense(expense_id)
    assert row is not None, "The original row should still exist (same id)"
    assert row["amount"] == 88.88, "Amount should be updated"
    assert row["category"] == "Bills", "Category should be updated"
    assert row["date"] == "2026-02-02", "Date should be updated"
    assert row["description"] == "Edited value marker", "Description should be updated"
    assert row["user_id"] == user_id, "The expense should still belong to the same user"


def test_updated_expense_appears_on_profile_page(auth_client):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(user_id, amount=10.00, category="Food", description="Old")

    payload = valid_payload(amount="250.00", category="Entertainment", description="Concert tickets marker")
    auth_client.post(f"/expenses/{expense_id}/edit", data=payload, follow_redirects=False)

    profile_resp = auth_client.get("/profile")
    assert profile_resp.status_code == 200
    html = profile_resp.data.decode()
    assert "Concert tickets marker" in html or "250.0" in html or "250" in html, (
        "The updated expense should appear in the profile page's recent expenses list"
    )

    conn = get_db()
    total = conn.execute(
        "SELECT SUM(amount) AS total FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["total"]
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    conn.close()

    assert count == 1, "Editing should not change the number of expenses for the user"
    assert total == pytest.approx(250.00), "The total should reflect the updated amount"


# --------------------------------------------------------------------- #
# Ownership: cannot GET/POST another user's expense; non-existent id
# --------------------------------------------------------------------- #

def _create_other_user_with_expense():
    # register() no-ops if the calling client already has a session, so use a
    # fresh, unauthenticated client to create the victim account.
    flask_app.config.update({"TESTING": True})
    fresh_client = flask_app.test_client()
    fresh_client.post(
        "/register",
        data={"name": "Victim", "email": "victim@example.com", "password": "password123"},
    )
    victim_id = _user_id_by_email("victim@example.com")
    expense_id = _insert_expense(
        victim_id, amount=999.00, category="Bills", description="Victim secret expense"
    )
    return victim_id, expense_id


def test_get_edit_expense_other_users_expense_redirects_to_profile_without_leaking_data(auth_client):
    victim_id, expense_id = _create_other_user_with_expense()

    resp = auth_client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
    assert resp.status_code == 302, "GET for another user's expense should redirect, not render"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"

    resp_followed = auth_client.get(f"/expenses/{expense_id}/edit", follow_redirects=True)
    assert b"Victim secret expense" not in resp_followed.data, (
        "The other user's expense data must never be exposed"
    )
    assert b"999" not in resp_followed.data, "The other user's amount must never be exposed"


def test_post_edit_expense_other_users_expense_redirects_and_does_not_modify(auth_client):
    victim_id, expense_id = _create_other_user_with_expense()

    payload = valid_payload(amount="1.00", category="Other", description="Hijacked!")
    resp = auth_client.post(f"/expenses/{expense_id}/edit", data=payload, follow_redirects=False)

    assert resp.status_code == 302, "POST for another user's expense should redirect, not update"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"

    row = _get_expense(expense_id)
    assert row["amount"] == 999.00, "Another user's expense must not be modified"
    assert row["category"] == "Bills"
    assert row["description"] == "Victim secret expense"
    assert row["user_id"] == victim_id, "Ownership of the expense must remain unchanged"


def test_get_edit_expense_nonexistent_id_redirects_to_profile(auth_client):
    resp = auth_client.get("/expenses/999999/edit", follow_redirects=False)
    assert resp.status_code == 302, "GET for a non-existent expense id should redirect"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"


def test_post_edit_expense_nonexistent_id_redirects_to_profile(auth_client):
    before = _expense_count()
    resp = auth_client.post("/expenses/999999/edit", data=valid_payload(), follow_redirects=False)
    assert resp.status_code == 302, "POST for a non-existent expense id should redirect"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"
    assert _expense_count() == before, "No row should be created or modified for a non-existent id"


# --------------------------------------------------------------------- #
# Validation errors: invalid/missing amount
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["", "-10", "-0.01", "not-a-number", "abc"],
    ids=["blank", "negative", "negative-decimal", "non-numeric", "letters"],
)
def test_post_invalid_amount_rerenders_with_error_and_does_not_modify_row(auth_client, bad_amount):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=50.00, category="Food", exp_date="2026-01-01", description="Original description"
    )

    resp = auth_client.post(
        f"/expenses/{expense_id}/edit", data=valid_payload(amount=bad_amount), follow_redirects=False
    )

    assert resp.status_code == 200, "Invalid amount should re-render the form, not redirect"
    assert 'name="amount"' in resp.data.decode(), "The edit-expense form should be re-rendered on error"

    row = _get_expense(expense_id)
    assert row["amount"] == 50.00, "Amount must remain unchanged on validation failure"
    assert row["category"] == "Food", "Category must remain unchanged on validation failure"
    assert row["date"] == "2026-01-01", "Date must remain unchanged on validation failure"
    assert row["description"] == "Original description", "Description must remain unchanged on validation failure"


# --------------------------------------------------------------------- #
# Validation errors: invalid category
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_category",
    ["", "NotARealCategory", "food", "<script>alert(1)</script>"],
    ids=["blank", "unknown", "wrong-case", "injection-like"],
)
def test_post_invalid_category_rerenders_with_error_and_does_not_modify_row(auth_client, bad_category):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=50.00, category="Food", exp_date="2026-01-01", description="Original description"
    )

    resp = auth_client.post(
        f"/expenses/{expense_id}/edit", data=valid_payload(category=bad_category), follow_redirects=False
    )

    assert resp.status_code == 200, "Invalid category should re-render the form, not redirect"
    assert 'name="amount"' in resp.data.decode(), "The edit-expense form should be re-rendered on error"

    row = _get_expense(expense_id)
    assert row["amount"] == 50.00, "Amount must remain unchanged on validation failure"
    assert row["category"] == "Food", "Category must remain unchanged on validation failure"
    assert row["date"] == "2026-01-01", "Date must remain unchanged on validation failure"
    assert row["description"] == "Original description", "Description must remain unchanged on validation failure"


# --------------------------------------------------------------------- #
# Validation errors: invalid date
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_date",
    ["", "not-a-date", "13/25/2026", "2026-13-40", "2026/09/12"],
    ids=["blank", "garbage", "us-format-invalid-month", "invalid-month-day", "wrong-separator"],
)
def test_post_invalid_date_rerenders_with_error_and_does_not_modify_row(auth_client, bad_date):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=50.00, category="Food", exp_date="2026-01-01", description="Original description"
    )

    resp = auth_client.post(
        f"/expenses/{expense_id}/edit", data=valid_payload(date=bad_date), follow_redirects=False
    )

    assert resp.status_code == 200, "Invalid date should re-render the form, not redirect"
    assert 'name="amount"' in resp.data.decode(), "The edit-expense form should be re-rendered on error"

    row = _get_expense(expense_id)
    assert row["amount"] == 50.00, "Amount must remain unchanged on validation failure"
    assert row["category"] == "Food", "Category must remain unchanged on validation failure"
    assert row["date"] == "2026-01-01", "Date must remain unchanged on validation failure"
    assert row["description"] == "Original description", "Description must remain unchanged on validation failure"


# --------------------------------------------------------------------- #
# Security: cannot overwrite another user's expense by guessing/spoofing
# --------------------------------------------------------------------- #

def test_post_cannot_overwrite_another_users_expense_by_guessing_id(client):
    # Victim account with an existing expense.
    client.post(
        "/register",
        data={"name": "Victim", "email": "victim@example.com", "password": "password123"},
    )
    victim_id = _user_id_by_email("victim@example.com")
    victim_expense_id = _insert_expense(
        victim_id, amount=300.00, category="Health", description="Victim expense to protect"
    )

    # Attacker registers, logs in as themselves, and tries to edit the victim's expense id.
    client.post(
        "/register",
        data={"name": "Attacker", "email": "attacker@example.com", "password": "password123"},
    )
    client.post("/login", data={"email": "attacker@example.com", "password": "password123"})

    payload = valid_payload(amount="1.00", category="Other", description="Overwritten by attacker")
    resp = client.post(f"/expenses/{victim_expense_id}/edit", data=payload, follow_redirects=False)

    assert resp.status_code == 302, "Attempt to edit another user's expense should redirect, not update"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"

    row = _get_expense(victim_expense_id)
    assert row["amount"] == 300.00, "Victim's expense must remain untouched"
    assert row["description"] == "Victim expense to protect", "Victim's expense must remain untouched"
    assert row["user_id"] == victim_id, "Ownership must remain with the victim"
