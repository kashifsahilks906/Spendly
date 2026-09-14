# Spec: Delete Expense

## Overview
This feature implements the final CRUD operation for expenses: deletion. It replaces the placeholder `/expenses/<id>/delete` route in `app.py` with a working POST-only route that removes an expense owned by the logged-in user, and adds a delete action to the profile page's recent activity list (with a confirmation prompt to guard against accidental clicks).

## Depends on
- Step 1 — Database setup (`expenses` table)
- Step 2 — Registration
- Step 3 — Login and Logout (session-based auth)
- Step 4 — Profile page (recent activity list this feature adds a delete action to)
- Step 7 — Add expense (expenses must exist to delete)
- Step 8 — Edit expense (same ownership-check pattern this route reuses)

## Routes
- `POST /expenses/<int:id>/delete` — deletes the expense with the given id if it belongs to the logged-in user, then redirects to `/profile`; if not logged in, redirects to `/login`; if the expense doesn't exist or belongs to another user, redirects to `/profile` without error (same not-found behavior as edit) — logged-in only

No GET handler — deletion must not be triggerable by a plain link/GET request.

## Database changes
No database changes. The `expenses` table (see `database/db.py`) already supports `DELETE FROM expenses WHERE id = ? AND user_id = ?`.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — in the "Recent activity" list (`profile-recent-row`), add a delete form/button next to the existing "Edit" link for each expense row; remove the placeholder note "Deleting expenses arrives in a later step."

## Files to change
- `app.py` — implement `delete_expense(id)`, changing its route decorator from GET to POST-only and adding the ownership-checked delete logic
- `templates/profile.html` — add the delete control to each recent activity row
- `static/css/style.css` — add styling for the new delete button/form if it needs to look distinct from `.profile-recent-edit` (only if the existing classes don't already cover it)

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a to this feature, but keep as standing rule)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Delete must be a `POST` request only, never a `GET` link, to avoid accidental or crawler-triggered deletion
- Always scope the delete query by both `id` and `user_id` so one user cannot delete another user's expense
- Add a client-side confirmation (e.g. `onsubmit="return confirm(...)"`) before the delete form submits, consistent with the inline-JS-per-template convention already used elsewhere in this project
- Follow the existing ownership-check pattern from `edit_expense` (fetch-then-check, redirect to profile if not found/not owned) rather than inventing a new pattern

## Definition of done
- [ ] Logging in, visiting `/profile`, and clicking "Delete" on an expense (after confirming) removes it and redirects back to `/profile`, and the expense no longer appears in the list or in the total/category stats
- [ ] Visiting `/expenses/<id>/delete` directly with a GET request (e.g. typing the URL in the browser) does not delete the expense (returns 405 or otherwise fails, not a deletion)
- [ ] Attempting to delete another user's expense id (by submitting a POST to `/expenses/<id>/delete` for an id not owned by the logged-in user) does not delete it and redirects to `/profile`
- [ ] Attempting to delete a non-existent expense id redirects to `/profile` without raising an error
- [ ] Visiting `/expenses/<id>/delete` while logged out redirects to `/login`
- [ ] The profile page's recent activity list shows a working delete action for every row, and the "Deleting expenses arrives in a later step" note is gone
