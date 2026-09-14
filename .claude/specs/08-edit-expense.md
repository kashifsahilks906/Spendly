# Spec: Edit Expense

## Overview
This feature replaces the `/expenses/<id>/edit` placeholder with a working form that lets a logged-in user modify an existing expense they own (amount, category, date, description). It reuses the same form layout and validation rules introduced for Add Expense, pre-filled with the expense's current values, and builds on the `expenses` table already created in `database/db.py`.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`)
- Step 2 — Registration
- Step 3 — Login and Logout (session-based auth)
- Step 4 — Profile page (destination page after editing an expense, and where the edit entry point will live)
- Step 7 — Add Expense (validation pattern and form styling this feature mirrors)

## Routes
- `GET /expenses/<id>/edit` — render the edit form pre-filled with the expense's current values — logged-in only, and only if the expense belongs to the current user
- `POST /expenses/<id>/edit` — validate and update the expense, then redirect to `/profile` — logged-in only, and only if the expense belongs to the current user

Both methods are handled by the same `/expenses/<id>/edit` view function, matching the existing pattern used by `/expenses/add`.

## Database changes
No database changes. The `expenses` table already has the required columns (`user_id`, `amount`, `category`, `date`, `description`), as defined in `database/db.py`.

## Templates
- **Create:** `templates/edit_expense.html` — same field set and markup pattern as `templates/add_expense.html` (amount, category select populated from `CATEGORIES`, date, optional description), but pre-filled with the existing expense's values and posting to `url_for('edit_expense', id=expense.id)`. Extends `base.html`.
- **Modify:** `templates/profile.html` — add an "Edit" link/button next to each expense row in the recent expenses list, pointing to `url_for('edit_expense', id=expense.id)` (minimal, scoped addition only).

## Files to change
- `app.py` — replace the `edit_expense` placeholder route with the real `GET`/`POST` implementation
- `templates/profile.html` — add an edit link/button per expense row (minimal, scoped addition only)

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not applicable to this feature, but keep existing auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Require `session.get('user_id')` before allowing access to either method, redirecting to `/login` otherwise (mirror the pattern used in `/profile` and `/expenses/add`)
- Look up the expense by `id` AND `user_id` together in the same query — if no row matches (wrong id, or belongs to another user), do not leak existence; redirect to `/profile` rather than rendering the form or a 404 with details
- Validate on the server exactly as in Add Expense: amount must be a positive number, category must be one of `CATEGORIES`, date must be a valid `YYYY-MM-DD` string; re-render the form with an `error` message on failure instead of raising
- Update using the authenticated `session['user_id']` as part of the `WHERE` clause, never trusting a `user_id` from the form
- Do not touch `/expenses/<id>/delete` — out of scope for this step
- Do not modify `database/db.py`, `database/__init__.py`, or unrelated templates/routes
- Do not modify the `/expenses/add` route or `templates/add_expense.html` beyond what's needed (none expected)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that belongs to another user redirects to `/profile` (does not show the form or expense data)
- [ ] Visiting `/expenses/<id>/edit` for a non-existent id redirects to `/profile`
- [ ] Visiting `/expenses/<id>/edit` for the current user's own expense shows a form pre-filled with its current amount, category, date, and description
- [ ] Submitting the form with valid data updates the existing row (not a new row) and redirects to `/profile`
- [ ] The updated values appear in the profile page's recent expenses list and totals
- [ ] Submitting with a missing/invalid amount (blank, negative, non-numeric) re-renders the form with an error and does not modify the row
- [ ] Submitting with an invalid category re-renders the form with an error and does not modify the row
- [ ] Submitting with an invalid date re-renders the form with an error and does not modify the row
- [ ] A logged-in user cannot edit or overwrite another user's expense by guessing its id
