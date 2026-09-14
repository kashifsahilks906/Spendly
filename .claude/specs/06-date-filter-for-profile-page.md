# Spec: Date Filter for Profile Page

## Overview
The `/profile` page (Step 04) shows every expense the logged-in user has ever
logged and computes its summary — total spent, expense count, per-category
breakdown, top category, recent activity — over that entire lifetime set. This
step adds a **date filter**: a small GET form at the top of the profile page
with a "from" date, a "to" date, and a few one-click presets (This month, Last
30 days, This year, All time). When a range is active the route scopes the
`expenses` query with an extra `AND date >= ? AND date <= ?` and every number on
the page — the stat cards, the category bars, the recent list — reflects only
expenses whose `date` falls inside that range. The selected range round-trips
through the URL query string (`?start=YYYY-MM-DD&end=YYYY-MM-DD`) so it is
bookmarkable and survives a refresh. Invalid or partial input falls back to "all
time" rather than erroring. No data is mutated — this stays a read-only page.

## Depends on
- Step 01 — Database Setup (`expenses` table with a `date` column, `get_db()`). Complete.
- Step 02 — Registration. Complete.
- Step 03 — Login and Logout (`session['user_id']`). Complete.
- Step 04 — Profile Page (`/profile` route, `profile.html`, `.profile-*` CSS, `pkr` filter). Complete.

## Routes
- `GET /profile` — **modified, not new.** Now also reads optional `start` and
  `end` query params (`YYYY-MM-DD`). When both are present and valid, all
  `expenses` reads and every derived summary are restricted to
  `date >= start AND date <= end`. Missing/invalid/reversed input is ignored and
  the page renders the full unfiltered set. Still redirects to `/login` without
  `session['user_id']`. — logged-in

No new routes.

## Database changes
No database changes. The existing `expenses.date` column (stored as an
ISO `YYYY-MM-DD` string by the seed data and by later add-expense steps) sorts
and compares lexicographically, so a `date >= ? AND date <= ?` range filter
works with plain string bind params. All reads stay scoped with
`WHERE user_id = ?`.

## Templates
- **Create:** None.
- **Modify:**
  - `templates/profile.html` — add a `<form method="get" action="{{ url_for('profile') }}">`
    filter bar directly under the account header (and above the stat cards /
    empty state). It contains:
    - two `<input type="date">` fields named `start` and `end`, pre-filled from
      the currently applied range (`value="{{ start or '' }}"`).
    - a submit button ("Apply").
    - preset links (plain `<a href>` to `/profile?start=…&end=…`) for
      This month, Last 30 days, This year, and All time (`/profile` with no
      query string).
    - when a range is active, a one-line summary such as
      "Showing 1–30 Sep 2026" with a "Clear" link back to `/profile`.
    - The existing empty-state block must also cover "no expenses **in this
      range**" — reword it so it is not a lie when the user has expenses but
      none in the selected dates.

## Files to change
- `app.py` — in the `profile` view:
  - Read `start = request.args.get("start", "").strip()` and
    `end = request.args.get("end", "").strip()`.
  - Validate each with `datetime.strptime(value, "%Y-%m-%d")`; if either fails
    to parse, treat the range as not set. If `start > end`, treat the range as
    not set (or swap — pick one and keep it simple; spec assumes "ignore").
  - Build the expenses query as a base string plus an optional
    `" AND date >= ? AND date <= ?"` fragment with the params appended to the
    bind tuple — never string-format the dates into the SQL.
  - Compute `total`, `count`, `categories`, `top_category`, `recent` from the
    filtered rows exactly as today.
  - Pass `start`, `end` (the applied, validated values or `None`) and a
    human-readable `range_label` to `render_template`.
- `static/css/style.css` — add additive `.profile-filter*` rules (form row,
  date inputs, preset links, active-range chip) using existing CSS variables
  and the spacing/border patterns already used by `.profile-card`. Do not edit
  existing `.profile-*` rules.

## Files to create
- `.claude/specs/06-date-filter-for-profile-page.md` (this file).

## New dependencies
No new dependencies. Date parsing/formatting uses the stdlib `datetime` already
imported in `app.py`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — the date range is passed as `?` bind params
  appended to the existing tuple; never f-string or `%`-format a date into SQL
- Passwords hashed with werkzeug (not touched here; never render `password_hash`)
- Use CSS variables — never hardcode hex values in `style.css`
- All templates extend `base.html` (`profile.html` already does)
- The filter form is `method="get"` only — it must not POST or mutate anything;
  no calls to the `/expenses/*` placeholder routes
- Never trust a `user_id` from the request — the query still filters on
  `session['user_id']` only; `start`/`end` are the only request-supplied inputs
  and are validated before use
- Invalid, missing, partial, or reversed `start`/`end` must degrade to the full
  unfiltered view — never a 400, a stack trace, or a half-applied filter
- Keep the change scoped to the `profile` view in `app.py`, `profile.html`, and
  additive CSS — do not touch other routes, templates, or existing CSS rules
- Preserve existing behaviour: sort order (`ORDER BY date DESC, id DESC`),
  the `pkr` filter on every amount, the 6-item `recent` slice, and the
  logged-out redirect all stay as they are
- Handle the "expenses exist but none in range" case explicitly with the empty
  state, not blank/`None`/zero-division output (the existing
  `pct = amt / total * 100 if total else 0` guard must remain)

## Definition of done
- [ ] `/profile` with no query string behaves exactly as before Step 06 (same
      totals, same category bars, same recent list for the seeded demo user)
- [ ] Visiting `/profile` logged out still redirects to `/login`, with or
      without `start`/`end` in the URL
- [ ] Entering a "from"/"to" range that covers only some of the demo user's
      seeded expenses updates the total, the expense count, the category
      breakdown, and the recent list to that subset, and the category amounts
      still sum to the displayed total
- [ ] The applied range is reflected back in the form fields and shown as a
      readable label with a working "Clear" link back to `/profile`
- [ ] The range is in the URL query string and survives a page refresh / can be
      bookmarked
- [ ] A range that matches none of the user's expenses shows the (reworded)
      empty state, not zeros, `None`, or a crash
- [ ] Garbage input (`?start=abc`, `?end=2026-13-99`, `start` set but `end`
      missing, `start` later than `end`) renders the full unfiltered page with
      no error
- [ ] The date values never appear inline in a SQL string — grep the diff for
      the query and confirm `?` placeholders and an appended bind tuple
- [ ] Every amount still renders as `PKR …`; the page contains no `₹` or `$`
- [ ] `profile.html` still extends `base.html`; only additive `.profile-filter*`
      CSS was added and no existing `.profile-*` rule or other route/template
      was changed
