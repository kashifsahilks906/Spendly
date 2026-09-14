"""
Tests for the "Delete Expense" feature (spec: .claude/specs/09-delete-expense.md).

These tests are derived strictly from the spec's Routes, Rules for
implementation, and Definition of Done sections, NOT from reading app.py's
delete_expense route logic. app.py / database/db.py were only consulted to
understand existing structure (how the Flask app + DB are wired up, the
users/expenses schema, and the ownership-check pattern already used by
/expenses/<id>/edit), never to derive expected behavior for this feature.

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
from database.db import get_db  # noqa: E402


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


# --------------------------------------------------------------------- #
# Happy path: POST deletes own expense and redirects to /profile
# --------------------------------------------------------------------- #

def test_post_delete_expense_own_expense_removes_row_and_redirects_to_profile(auth_client):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=42.00, category="Food", description="Delete me marker"
    )
    before_count = _expense_count()

    resp = auth_client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    assert resp.status_code == 302, "A successful delete should redirect (to /profile)"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile on success"

    assert _expense_count() == before_count - 1, "The expense row should be removed from the DB"
    assert _get_expense(expense_id) is None, "The deleted expense should no longer exist"


def test_deleted_expense_no_longer_appears_on_profile_page(auth_client):
    user_id = _user_id_by_email("test@example.com")
    kept_id = _insert_expense(user_id, amount=10.00, category="Food", description="Kept expense marker")
    deleted_id = _insert_expense(
        user_id, amount=500.00, category="Bills", description="Doomed expense marker"
    )

    auth_client.post(f"/expenses/{deleted_id}/delete", follow_redirects=False)

    profile_resp = auth_client.get("/profile")
    assert profile_resp.status_code == 200
    html = profile_resp.data.decode()

    assert "Doomed expense marker" not in html, (
        "The deleted expense should no longer appear in the recent activity list"
    )
    assert "Kept expense marker" in html, "Non-deleted expenses should still appear"

    conn = get_db()
    total = conn.execute(
        "SELECT SUM(amount) AS total FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["total"]
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    conn.close()

    assert count == 1, "Only the kept expense should remain for the user"
    assert total == pytest.approx(10.00), "The total should no longer include the deleted expense's amount"


# --------------------------------------------------------------------- #
# No GET handler: GET must not trigger a deletion
# --------------------------------------------------------------------- #

def test_get_delete_expense_is_rejected_and_does_not_delete(auth_client):
    user_id = _user_id_by_email("test@example.com")
    expense_id = _insert_expense(
        user_id, amount=15.00, category="Food", description="Should survive a GET"
    )

    resp = auth_client.get(f"/expenses/{expense_id}/delete", follow_redirects=False)

    assert resp.status_code == 405, "GET to the delete route should be rejected (405), not perform a deletion"
    assert _get_expense(expense_id) is not None, "The expense must still exist after a rejected GET request"


# --------------------------------------------------------------------- #
# Ownership: cannot delete another user's expense
# --------------------------------------------------------------------- #

def test_post_delete_other_users_expense_does_not_delete_and_redirects_to_profile(auth_client):
    victim_id, expense_id = _create_other_user_with_expense()
    before_count = _expense_count()

    resp = auth_client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    assert resp.status_code == 302, "Attempting to delete another user's expense should redirect, not error"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"

    assert _expense_count() == before_count, "No row should be deleted"
    row = _get_expense(expense_id)
    assert row is not None, "The other user's expense must still exist"
    assert row["user_id"] == victim_id, "Ownership of the expense must remain unchanged"
    assert row["description"] == "Victim secret expense", "The other user's expense must be untouched"


# --------------------------------------------------------------------- #
# Non-existent id: redirects without error
# --------------------------------------------------------------------- #

def test_post_delete_nonexistent_id_redirects_to_profile_without_error(auth_client):
    before = _expense_count()

    resp = auth_client.post("/expenses/999999/delete", follow_redirects=False)

    assert resp.status_code == 302, "POST for a non-existent expense id should redirect, not error"
    assert "/profile" in resp.headers.get("Location", ""), "Should redirect to /profile"
    assert _expense_count() == before, "No row should be created or deleted for a non-existent id"


# --------------------------------------------------------------------- #
# Auth guard: logged-out request redirects to /login and deletes nothing
# --------------------------------------------------------------------- #

def test_post_delete_expense_logged_out_redirects_to_login_and_does_not_delete(client):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Owner", "owner@example.com", "hash"),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", ("owner@example.com",)).fetchone()["id"]
    conn.close()
    expense_id = _insert_expense(user_id, amount=20.00, category="Food", description="Untouched while logged out")
    before_count = _expense_count()

    resp = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    assert resp.status_code == 302, "Unauthenticated POST should redirect, not delete"
    assert "/login" in resp.headers.get("Location", ""), "Should redirect to the login page"

    assert _expense_count() == before_count, "No expense should be deleted for an unauthenticated request"
    assert _get_expense(expense_id) is not None, "The expense must still exist"


def test_get_delete_expense_logged_out_redirects_to_login(client):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Owner", "owner@example.com", "hash"),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", ("owner@example.com",)).fetchone()["id"]
    conn.close()
    expense_id = _insert_expense(user_id)

    resp = client.get(f"/expenses/{expense_id}/delete", follow_redirects=False)

    # Auth guard should be enforced before route-not-allowed logic; either way
    # this must not be a 200 render, and the resource must be untouched.
    assert resp.status_code in (302, 405), (
        "Unauthenticated GET should either redirect to /login or be rejected as method-not-allowed, "
        "never delete anything"
    )
    if resp.status_code == 302:
        assert "/login" in resp.headers.get("Location", ""), "Should redirect to the login page"
    assert _get_expense(expense_id) is not None, "The expense must still exist"
