# Spec: Add Expense

## Overview
This feature replaces the `/expenses/add` placeholder with a working form that lets a logged-in user record a new expense (amount, category, date, description). It builds directly on the existing `expenses` table (already created in `database/db.py`) and the profile page's spending summary, which currently has no way for users to actually add data of their own beyond the seeded demo rows.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`)
- Step 2 — Registration
- Step 3 — Login and Logout (session-based auth)
- Step 4 — Profile page (destination page after adding an expense)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the new expense, then redirect to `/profile` — logged-in only

Both methods are handled by the same `/expenses/add` view function, matching the existing pattern used by `/register` and `/login`.

## Database changes
No database changes. The `expenses` table already has the required columns (`user_id`, `amount`, `category`, `date`, `description`), as defined in `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category (select, populated from `CATEGORIES` in `database/db.py`), date (defaulting to today), description (optional). Extends `base.html`, follows the same error/success messaging pattern as `register.html`/`login.html`.
- **Modify:** None required. `base.html` nav already links only to Profile/Analytics/Logout; an "Add Expense" entry point can live on the profile page itself (e.g., a button/link near the expense summary) — if added, `templates/profile.html` gets a single small link/button pointing to `url_for('add_expense')`. No other structural changes.

## Files to change
- `app.py` — replace the `add_expense` placeholder route with the real `GET`/`POST` implementation
- `templates/profile.html` — add a link/button to `/expenses/add` (minimal, scoped addition only)

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not applicable to this feature, but keep existing auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Require `session.get('user_id')` before allowing access to either method, redirecting to `/login` otherwise (mirror the pattern used in `/profile`)
- Validate on the server: amount must be a positive number, category must be one of `CATEGORIES`, date must be a valid `YYYY-MM-DD` string; re-render the form with an `error` message on failure instead of raising
- Insert using the authenticated `session['user_id']`, never a value from the form, as the `user_id`
- Do not touch `/expenses/<id>/edit` or `/expenses/<id>/delete` placeholders — out of scope for this step
- Do not modify `database/db.py`, `database/__init__.py`, or unrelated templates/routes

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with amount, category, date, and description fields
- [ ] Submitting the form with valid data creates a new row in `expenses` for the current user and redirects to `/profile`
- [ ] The newly added expense appears in the profile page's recent expenses list and totals
- [ ] Submitting with a missing/invalid amount (blank, negative, non-numeric) re-renders the form with an error and does not insert a row
- [ ] Submitting with an invalid category re-renders the form with an error and does not insert a row
- [ ] Submitting with an invalid date re-renders the form with an error and does not insert a row
- [ ] A logged-in user cannot cause an expense to be recorded under a different `user_id` (form has no user_id field, or any submitted value is ignored)
