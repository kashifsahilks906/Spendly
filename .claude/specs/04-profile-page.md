# Spec: Profile Page

## Overview
Turn the `/profile` placeholder into a real, logged-in-only page that shows the
current user who they are and a lightweight snapshot of their spending. After
Step 03 a user can sign in and the navbar already links to "Profile", but the
route still returns the literal string `"Profile page — coming in Step 4"`. This
step builds the account page: it reads `session['user_id']`, loads that user's
row from `users`, loads their `expenses` rows, and renders a `profile.html`
template that displays name, email, join date, and a small summary (total spent,
number of expenses, a per-category breakdown). Expense add/edit/delete are still
future steps (07–09), so this page is read-only — no forms that mutate data.
It also establishes the "you must be logged in to see this" pattern that every
later authenticated page will reuse. All monetary amounts render as
`PKR 1,234.00` via a shared `pkr` Jinja filter registered in `app.py`; the page
never outputs a `₹` or `$` character.

## Depends on
- Step 01 — Database Setup (`users` + `expenses` tables, `get_db()`). Already complete.
- Step 02 — Registration (users can create an account). Already complete.
- Step 03 — Login and Logout (`session['user_id']` / `session['user_name']` are set on login; navbar already has a Profile link). Already complete.

## Routes
- `GET /profile` — load the logged-in user and their expenses, render `profile.html`; redirect to `/login` if there is no `session['user_id']` — logged-in

No other new routes.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email`,
`password_hash`, `created_at`) and `expenses` table (`id`, `user_id`, `amount`,
`category`, `date`, `description`, `created_at`) from `database/db.py` already
provide everything this page needs. All reads are scoped with
`WHERE user_id = ?`.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`. Sections:
    - Account header: user's name (display font), email, and "Member since
      {{ created_at }}" formatted as a readable date.
    - Summary row: three stat cards — total spent, number of expenses, top
      category (or a friendly empty state when the user has no expenses yet).
    - Category breakdown: a simple list of category → amount (and/or count),
      sorted by amount descending, rendered from data the route passes in.
    - A short read-only note that adding expenses arrives in a later step (no
      "Add expense" button yet — that route is still a placeholder).
- **Modify:**
  - None required. `base.html` already renders the Profile/Logout links when
    `session.get('user_id')` is set (added in Step 03).

## Files to change
- `app.py` — implement `GET /profile`:
  - If `session.get('user_id')` is missing, `redirect(url_for('login'))`.
  - `get_db()`, `SELECT * FROM users WHERE id = ?` with the session user id;
    if the row is missing (stale session), `session.clear()` and redirect to
    `/login`.
  - `SELECT amount, category, date, description FROM expenses WHERE user_id = ?
    ORDER BY date DESC`.
  - Compute in Python: total spent, expense count, per-category totals
    (sorted by amount desc), and top category.
  - `conn.close()`, then `render_template("profile.html", ...)` passing the
    user, the summary numbers, and the category breakdown.
- `static/css/style.css` — add profile-page styles (`.profile-*`, stat cards,
  category list) using existing CSS variables only. Reuse the card / spacing
  patterns already used by the auth pages where possible.

## Files to create
- `templates/profile.html`
- `.claude/specs/04-profile-page.md` (this file)

## New dependencies
No new dependencies. Date formatting can use Python's stdlib (`datetime`) in the
route or a Jinja filter/`strftime` in the template.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — every `expenses`/`users` read filtered by the
  session user id via `?` placeholders, never string interpolation
- Passwords hashed with werkzeug (not touched here; never render
  `password_hash` in the template)
- Use CSS variables — never hardcode hex values in `style.css`
- All templates extend `base.html`
- Gate the route on `session.get('user_id')`; unauthenticated visitors are
  redirected to `/login`, not shown a partial page or an error
- Never trust a `user_id` from the request — only ever use `session['user_id']`
- This page is read-only: no `<form>` that writes data, no calls to the
  `/expenses/*` placeholder routes
- Keep the change scoped to `app.py` (`/profile` only), the new `profile.html`,
  and additive CSS — do not modify other routes, templates, or existing CSS rules
- Handle the empty state (user with zero expenses) explicitly rather than
  rendering empty/`None` totals
- Format all money as `PKR 1,234.00` through the `pkr` template filter; never
  output `₹` or `$`

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as the seeded demo user (`demo@spendly.com` / `demo123`) and
      visiting `/profile` shows that user's name, email, and a "member since" date
- [ ] The summary shows the correct total spent and expense count for the seeded
      demo user (8 expenses) and a plausible top category
- [ ] The category breakdown lists each category the user has expenses in, sorted
      by amount descending, with amounts that sum to the displayed total
- [ ] A user with no expenses sees a friendly empty state, not blank/`None` values
      or a crash
- [ ] The rendered page never contains the user's `password_hash`
- [ ] Every amount on the page is shown as `PKR …`; the page contains no `₹` or
      `$` character
- [ ] Tampering with the session is not possible via the URL — there is no
      `user_id` query/route param; the page always reflects the session user
- [ ] The page extends `base.html`, uses only existing CSS variables, and no
      other template/route/CSS rule was changed
