"""Tests for Step 06 — Date Filter for the Profile Page.

These tests are written from `.claude/specs/06-date-filter-for-profile-page.md`
(what the feature SHOULD do), not from the implementation.

The feature under test:
  * `GET /profile` optionally reads `start` / `end` query params (`YYYY-MM-DD`).
  * When both are present and valid (and `start <= end`) every number on the
    page — stat cards, category bars, recent list — is restricted to
    `date >= start AND date <= end`, scoped to `session['user_id']` only.
  * The applied range round-trips through the URL query string, pre-fills the
    date inputs, and shows a human-readable label + a "Clear" link.
  * Missing / invalid / partial / reversed input degrades to the full
    unfiltered page with HTTP 200 — never an error.
  * A range that matches nothing shows the reworded empty state.
  * The page is read-only (GET form, no data mutated) and renders money as
    `PKR …` (no `₹` / `$`).
"""

import re
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

import database.db as _db

# ---------------------------------------------------------------------------#
# Isolate the DB *before* importing app.py, whose module body calls          #
# init_db() + seed_db() at import time. Pointing DB_PATH at a throwaway file  #
# keeps the real project database (and the shipped seed data) out of the     #
# test run entirely.                                                         #
# ---------------------------------------------------------------------------#
import os
import tempfile

_IMPORT_TIME_DIR = tempfile.mkdtemp(prefix="spendly_step06_import_")
_db.DB_PATH = os.path.join(_IMPORT_TIME_DIR, "import_time.db")

from app import app as flask_app  # noqa: E402
from database.db import get_db, init_db  # noqa: E402


PROFILE_URL = "/profile"
LOGIN_URL = "/login"

RUPEE = "₹"

MONTH_ABBRS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

SEED_USER = {
    "name": "Ranger",
    "email": "ranger@spendly.com",
    "password": "password123",
}
OTHER_USER = {
    "name": "Otheruser",
    "email": "other@spendly.com",
    "password": "password123",
}

# (date, category, amount, description) — fixed dates so range maths is exact.
SEED_EXPENSES = [
    ("2026-01-10", "Food", 100.00, "Jan food"),
    ("2026-01-20", "Transport", 50.00, "Jan bus"),
    ("2026-02-15", "Food", 200.00, "Feb food"),
    ("2026-03-05", "Bills", 300.00, "Mar bills"),
    ("2026-03-25", "Health", 40.00, "Mar pharmacy"),
    ("2026-06-01", "Shopping", 500.00, "Jun shoes"),
    ("2026-09-09", "Entertainment", 25.00, "Sep movie"),
]

# Lifetime totals for SEED_USER.
FULL_TOTAL_STR = "PKR 1,215.00"   # 100+50+200+300+40+500+25
FULL_COUNT = 7

# Range 2026-01-01 .. 2026-02-28 covers exactly the first three expenses.
JANFEB = {"start": "2026-01-01", "end": "2026-02-28"}
JANFEB_TOTAL_STR = "PKR 350.00"   # 100 + 50 + 200
JANFEB_COUNT = 3
JANFEB_FOOD_STR = "PKR 300.00"    # 100 + 200
JANFEB_TRANSPORT_STR = "PKR 50.00"

# A range matching none of SEED_USER's expenses.
EMPTY_RANGE = {"start": "2000-01-01", "end": "2000-12-31"}


# ---------------------------------------------------------------------------#
# Helpers                                                                    #
# ---------------------------------------------------------------------------#
def _seed():
    """Insert SEED_USER (with known expenses) and a second user whose expenses
    sit inside the same date window, to prove per-user scoping."""
    conn = get_db()
    uid = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (SEED_USER["name"], SEED_USER["email"],
         generate_password_hash(SEED_USER["password"])),
    ).lastrowid
    for d, cat, amt, desc in SEED_EXPENSES:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, amt, cat, d, desc),
        )

    oid = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (OTHER_USER["name"], OTHER_USER["email"],
         generate_password_hash(OTHER_USER["password"])),
    ).lastrowid
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (oid, 9999.00, "Food", "2026-01-15", "OTHER USER FOOD"),
    )
    conn.commit()
    conn.close()
    return uid


def _expense_row_count():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    conn.close()
    return n


def _active_range_segment(text):
    """Return the text shown between 'Showing' and the 'Clear' link."""
    assert "Showing" in text, "expected an active-range label starting with 'Showing'"
    assert "Clear" in text, "expected a 'Clear' link next to the active-range label"
    return text.split("Showing", 1)[1].split("Clear", 1)[0]


# ---------------------------------------------------------------------------#
# Fixtures                                                                   #
# ---------------------------------------------------------------------------#
@pytest.fixture
def _db_path(tmp_path, monkeypatch):
    """Fresh, isolated SQLite file per test with the schema created."""
    path = tmp_path / "spendly.db"
    monkeypatch.setattr(_db, "DB_PATH", str(path))
    init_db()
    yield str(path)


@pytest.fixture
def app(_db_path):
    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded(app):
    """Seed the isolated DB; returns SEED_USER's id."""
    return _seed()


@pytest.fixture
def auth_client(client, seeded):
    """A test client already logged in as SEED_USER, with data seeded."""
    resp = client.post(
        LOGIN_URL,
        data={"email": SEED_USER["email"], "password": SEED_USER["password"]},
    )
    assert resp.status_code == 302, "seed user login should redirect on success"
    return client


# ---------------------------------------------------------------------------#
# 1. Auth guard                                                              #
# ---------------------------------------------------------------------------#
def test_profile_with_range_params_logged_out_redirects_to_login(client, seeded):
    """Spec: still redirects to /login without session['user_id'], with or
    without start/end in the URL."""
    resp = client.get(PROFILE_URL, query_string=JANFEB)
    assert resp.status_code == 302, "logged-out /profile?start=&end= must redirect"
    assert "/login" in resp.headers["Location"], resp.headers["Location"]

    followed = client.get(PROFILE_URL, query_string=JANFEB, follow_redirects=True)
    assert followed.status_code == 200
    body = followed.get_data(as_text=True).lower()
    assert "sign in" in body or "login" in body, "should land on the login page"
    # No seeded expense data may leak on the way to login.
    assert "OTHER USER FOOD" not in followed.get_data(as_text=True)


# ---------------------------------------------------------------------------#
# 2. Baseline — no query string behaves as before Step 06                    #
# ---------------------------------------------------------------------------#
def test_profile_no_query_string_shows_full_lifetime_summary(auth_client):
    """Spec / DoD: /profile with no query string behaves exactly as before —
    every one of the logged-in user's expenses is counted."""
    resp = auth_client.get(PROFILE_URL)
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert FULL_TOTAL_STR in text, "lifetime total should be shown"
    assert 'profile-stat-value">7<' in text, "lifetime expense count should be 7"

    # Six most-recent descriptions render; the 7th (oldest) is outside the
    # preserved 6-item recent slice.
    for desc in ("Sep movie", "Jun shoes", "Mar pharmacy",
                 "Mar bills", "Feb food", "Jan bus"):
        assert desc in text, f"expected recent item {desc!r}"
    assert "Jan food" not in text, "6-item recent slice must be preserved"

    # Every seeded category appears in the lifetime breakdown.
    for cat in ("Food", "Transport", "Bills", "Health",
                "Shopping", "Entertainment"):
        assert cat in text, f"expected category {cat!r} in lifetime breakdown"

    # No active-range chrome when no range is applied.
    assert "Showing" not in text
    assert "OTHER USER FOOD" not in text, "another user's expense must not leak"


# ---------------------------------------------------------------------------#
# 3. Happy path — a range restricts every derived number                     #
# ---------------------------------------------------------------------------#
def test_range_restricts_total_count_categories_and_recent(auth_client):
    """DoD: a range covering only some expenses updates total, count, category
    breakdown and recent list to that subset."""
    resp = auth_client.get(PROFILE_URL, query_string=JANFEB)
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert JANFEB_TOTAL_STR in text, "total must reflect only in-range expenses"
    assert FULL_TOTAL_STR not in text, "lifetime total must not be shown"
    assert f'profile-stat-value">{JANFEB_COUNT}<' in text, "count must be the subset size"

    # In-range recent descriptions present; out-of-range ones gone.
    for desc in ("Jan food", "Jan bus", "Feb food"):
        assert desc in text, f"expected in-range recent item {desc!r}"
    for desc in ("Mar bills", "Mar pharmacy", "Jun shoes", "Sep movie"):
        assert desc not in text, f"out-of-range item {desc!r} must be excluded"

    # Category breakdown restricted to categories seen in range.
    assert "Food" in text and "Transport" in text
    for cat in ("Bills", "Health", "Shopping", "Entertainment"):
        assert cat not in text, f"out-of-range category {cat!r} must be excluded"


def test_category_amounts_sum_to_displayed_total_when_filtered(auth_client):
    """DoD: the category amounts still sum to the displayed total."""
    resp = auth_client.get(PROFILE_URL, query_string=JANFEB)
    text = resp.get_data(as_text=True)

    # The two in-range category subtotals (300 + 50) sum to the displayed total.
    assert JANFEB_FOOD_STR in text, "Food (in-range) subtotal should be PKR 300.00"
    assert JANFEB_TRANSPORT_STR in text, "Transport (in-range) subtotal should be PKR 50.00"
    assert JANFEB_TOTAL_STR in text, "displayed total should be PKR 350.00"


def test_single_day_inclusive_range_returns_that_days_expense(auth_client):
    """Spec: filter is `date >= start AND date <= end` — both bounds inclusive."""
    resp = auth_client.get(
        PROFILE_URL, query_string={"start": "2026-03-05", "end": "2026-03-05"}
    )
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'profile-stat-value">1<' in text, "exactly one expense on 2026-03-05"
    assert "PKR 300.00" in text, "the 2026-03-05 Bills expense (300) should be counted"
    assert "Mar bills" in text
    assert "Jan bus" not in text and "Feb food" not in text


# ---------------------------------------------------------------------------#
# 4. Round-trip: pre-filled inputs, readable label, Clear link              #
# ---------------------------------------------------------------------------#
def test_applied_range_prefills_inputs_and_shows_label_and_clear_link(auth_client):
    """DoD: the applied range is reflected back in the form fields and shown as
    a readable label with a working 'Clear' link back to /profile."""
    resp = auth_client.get(PROFILE_URL, query_string=JANFEB)
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'name="start"' in text and 'name="end"' in text, "GET filter inputs present"
    assert 'value="2026-01-01"' in text, "'start' input pre-filled with applied value"
    assert 'value="2026-02-28"' in text, "'end' input pre-filled with applied value"

    assert "Showing" in text, "an active-range label should be shown"
    assert "Clear" in text, "a Clear link should be shown"
    assert 'href="/profile"' in text, "Clear must link back to /profile with no query"


def test_range_label_is_human_readable_not_raw_iso(auth_client):
    """Spec: a *human-readable* range label such as 'Showing 1–30 Sep 2026' —
    not the raw ISO params, not None."""
    resp = auth_client.get(PROFILE_URL, query_string=JANFEB)
    seg = _active_range_segment(resp.get_data(as_text=True))

    assert "2026" in seg, "the label should contain the year"
    assert any(m in seg for m in MONTH_ABBRS), "the label should name the month(s)"
    assert "2026-01-01" not in seg and "2026-02-28" not in seg, \
        "label must be humanised, not the raw ISO query params"
    assert "None" not in seg


def test_clear_link_returns_unfiltered_page(auth_client):
    """DoD: the 'Clear' link (back to /profile) restores the full view."""
    filtered = auth_client.get(PROFILE_URL, query_string=JANFEB)
    assert "Showing" in filtered.get_data(as_text=True)

    cleared = auth_client.get(PROFILE_URL)  # what Clear points at
    text = cleared.get_data(as_text=True)
    assert cleared.status_code == 200
    assert FULL_TOTAL_STR in text
    assert 'profile-stat-value">7<' in text
    assert "Showing" not in text


# ---------------------------------------------------------------------------#
# 5. Bookmarkable via URL query string                                       #
# ---------------------------------------------------------------------------#
def test_range_is_bookmarkable_and_survives_refresh(auth_client):
    """DoD: the range lives in the URL query string and survives a refresh /
    can be bookmarked."""
    first = auth_client.get(PROFILE_URL + "?start=2026-01-01&end=2026-02-28")
    second = auth_client.get(PROFILE_URL + "?start=2026-01-01&end=2026-02-28")

    for resp in (first, second):
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert JANFEB_TOTAL_STR in text, "same URL -> same filtered total"
        assert f'profile-stat-value">{JANFEB_COUNT}<' in text
        assert 'value="2026-01-01"' in text and 'value="2026-02-28"' in text


def test_preset_links_are_query_string_urls(auth_client):
    """Spec: preset links are plain <a href> to /profile?start=…&end=… (so the
    range is a bookmarkable URL) plus an 'All time' link back to /profile."""
    text = auth_client.get(PROFILE_URL).get_data(as_text=True)
    assert "/profile?start=" in text, "presets should link to query-string URLs"
    assert 'href="/profile"' in text, "an 'All time' link back to /profile"
    assert "All time" in text


# ---------------------------------------------------------------------------#
# 6. Empty-in-range — reworded empty state, no zeros / None / crash          #
# ---------------------------------------------------------------------------#
def test_range_matching_no_expenses_shows_reworded_empty_state(auth_client):
    """DoD: a range that matches none of the user's expenses shows the
    (reworded) empty state, not zeros, None, or a crash."""
    resp = auth_client.get(PROFILE_URL, query_string=EMPTY_RANGE)
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200, "empty range must not error"
    assert "No expenses" in text, "an empty state should be shown"
    assert "range" in text.lower(), "empty state should be reworded for the range case"
    assert "No expenses yet" not in text, \
        "must not claim the user has never logged an expense — they have"

    # No broken/zeroed summary leaking through.
    assert "PKR 0.00" not in text
    assert ">None<" not in text
    assert "Traceback" not in text
    # The range chrome is still offered so the user can widen / clear it.
    assert "Showing" in text and "Clear" in text


# ---------------------------------------------------------------------------#
# 7. Validation degradation — bad input -> full unfiltered page, HTTP 200    #
# ---------------------------------------------------------------------------#
@pytest.mark.parametrize(
    "query_string, label",
    [
        ({"start": "abc"}, "non-date start"),
        ({"start": "2026-01-01", "end": "2026-13-99"}, "impossible end date"),
        ({"end": "2026-02-28"}, "end only, start missing"),
        ({"start": "2026-01-01"}, "start only, end missing"),
        ({"start": "2026-03-01", "end": "2026-01-01"}, "reversed range (start > end)"),
        ({"start": "01/01/2026", "end": "28/02/2026"}, "wrong date format"),
        ({"start": "2026-01-01' OR '1'='1", "end": "2026-12-31"}, "SQL-ish injection"),
        ({"start": "", "end": ""}, "blank params"),
    ],
)
def test_invalid_or_partial_range_degrades_to_full_page(auth_client, query_string, label):
    """DoD: garbage / partial / reversed input renders the full unfiltered page
    with no error and no half-applied filter."""
    resp = auth_client.get(PROFILE_URL, query_string=query_string)
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200, f"{label}: expected HTTP 200"
    assert FULL_TOTAL_STR in text, f"{label}: expected the full lifetime total"
    assert 'profile-stat-value">7<' in text, f"{label}: expected the full count of 7"
    assert "Showing" not in text, f"{label}: no active-range label (filter not applied)"
    assert "No expenses in this range" not in text, f"{label}: range must be ignored"
    assert "Traceback" not in text, f"{label}: no stack trace"


# ---------------------------------------------------------------------------#
# 8. Per-user scoping — the range filter never leaks another user            #
# ---------------------------------------------------------------------------#
def test_range_filter_does_not_leak_other_users_expenses(auth_client):
    """Spec: all reads stay scoped with WHERE user_id = ? (session user only);
    start/end are the only request-supplied inputs."""
    # OTHER_USER has a 9,999.00 Food expense dated 2026-01-15 — inside JANFEB.
    filtered = auth_client.get(PROFILE_URL, query_string=JANFEB).get_data(as_text=True)
    assert JANFEB_TOTAL_STR in filtered, "total must be the seed user's in-range sum only"
    assert "9,999" not in filtered, "another user's amount must not appear"
    assert "OTHER USER FOOD" not in filtered, "another user's expense must not appear"

    unfiltered = auth_client.get(PROFILE_URL).get_data(as_text=True)
    assert FULL_TOTAL_STR in unfiltered
    assert "OTHER USER FOOD" not in unfiltered


def test_other_user_sees_only_their_own_in_range_data(client, seeded):
    """Cross-check: logging in as the *other* user and applying the same range
    shows that user's single expense, never the seed user's."""
    client.post(
        LOGIN_URL,
        data={"email": OTHER_USER["email"], "password": OTHER_USER["password"]},
    )
    text = client.get(PROFILE_URL, query_string=JANFEB).get_data(as_text=True)
    assert text.count("OTHER USER FOOD") >= 1
    assert "PKR 9,999.00" in text
    assert 'profile-stat-value">1<' in text
    for desc in ("Jan food", "Jan bus", "Feb food"):
        assert desc not in text, f"seed user's {desc!r} must not leak to other user"


# ---------------------------------------------------------------------------#
# 9. Currency rendering — PKR only, never ₹ or $                             #
# ---------------------------------------------------------------------------#
@pytest.mark.parametrize(
    "query_string, expect_amounts, label",
    [
        (None, True, "unfiltered"),
        (JANFEB, True, "filtered subset"),
        (EMPTY_RANGE, False, "empty range"),
    ],
)
def test_no_rupee_or_dollar_symbols_on_page(auth_client, query_string, expect_amounts, label):
    """DoD: every amount renders as 'PKR …'; the page contains no ₹ and no $."""
    resp = auth_client.get(PROFILE_URL, query_string=query_string or {})
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert RUPEE not in text, f"{label}: rupee sign must not appear"
    assert not re.search(r"\$\s?\d", text), \
        f"{label}: no dollar-formatted amount may appear"
    if expect_amounts:
        assert "PKR " in text, f"{label}: amounts should render with the PKR prefix"


# ---------------------------------------------------------------------------#
# 10. Read-only — GET form, nothing mutated                                  #
# ---------------------------------------------------------------------------#
def test_filter_form_is_get_and_no_data_is_mutated(auth_client):
    """Spec: the filter form is method='get' only and must not mutate anything."""
    before = _expense_row_count()

    pages = [
        auth_client.get(PROFILE_URL),
        auth_client.get(PROFILE_URL, query_string=JANFEB),
        auth_client.get(PROFILE_URL, query_string=EMPTY_RANGE),
        auth_client.get(PROFILE_URL, query_string={"start": "abc"}),
    ]
    for resp in pages:
        assert resp.status_code == 200

    after = _expense_row_count()
    assert after == before == len(SEED_EXPENSES) + 1, "no rows added/removed by GETs"

    text = auth_client.get(PROFILE_URL, query_string=JANFEB).get_data(as_text=True)
    assert 'method="get"' in text.lower(), "filter form must be method=get"
    assert 'method="post"' not in text.lower(), "profile page must not POST anything"


def test_range_filter_uses_parameterised_queries_safely(auth_client):
    """Rule: the date range is passed as ? bind params — an injection-shaped
    value must neither filter nor break the page nor corrupt the DB."""
    before = _expense_row_count()
    resp = auth_client.get(
        PROFILE_URL,
        query_string={"start": "2026-01-01'; DROP TABLE expenses;--", "end": "2026-12-31"},
    )
    assert resp.status_code == 200
    assert FULL_TOTAL_STR in resp.get_data(as_text=True), "bad value ignored -> full page"

    # Table still intact and untouched.
    assert _expense_row_count() == before
    conn = get_db()
    try:
        conn.execute("SELECT 1 FROM expenses LIMIT 1")
    except sqlite3.Error as exc:  # pragma: no cover - defensive
        pytest.fail(f"expenses table was harmed: {exc}")
    finally:
        conn.close()
