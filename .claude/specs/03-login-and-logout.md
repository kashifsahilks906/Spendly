# Spec: Login and Logout

## Overview
Wire up `/login` and `/logout` so a registered user can actually authenticate and end their session. `login.html` already has a working POST form (email, password) pointing at `/login`; this step adds the server-side handling that looks up the user, verifies the password hash, and establishes a Flask session. `/logout` clears that session and returns the user to the landing page. This is the first step that introduces the concept of a "logged-in" request — every later step (profile, expense CRUD) depends on `session['user_id']` being available to identify the current user and to gate access to routes that should not be reachable while logged out.

## Depends on
- Step 01 — Database Setup (`users` table and `get_db()`). Already complete.
- Step 02 — Registration (users must be able to create an account before they can log in). Already complete.

## Routes
- `GET /login` — render the login form (already exists, unchanged) — public
- `POST /login` — validate credentials, establish session, redirect to `/profile` on success, re-render `login.html` with an error on failure — public
- `GET /logout` — clear the session, redirect to `/` — logged-in (no-op / redirects to `/login` if not logged in)

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) from `database/db.py` already supports this feature.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — add a `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` block above the form (mirrors the pattern already used in `register.html`) shown when credentials are invalid. Form fields and action are unchanged.
  - `templates/base.html` — navbar currently always shows "Sign in" / "Get started" links. Update the `nav-links` block to conditionally show "Sign in"/"Get started" when logged out, and a "Logout" link (plus a placeholder profile link, since `/profile` isn't built yet) when `session.get('user_id')` is present.

## Files to change
- `app.py` — implement `POST /login` (read form fields, look up user by email, verify password with `check_password_hash`, set `session['user_id']` and `session['user_name']` on success, redirect to `/profile`; re-render `login.html` with an error on missing fields or invalid credentials) and implement `GET /logout` (clear the session, redirect to `/`). Set `app.secret_key` (from an environment variable, falling back to a hardcoded dev-only value) since sessions require it.
- `templates/login.html` — add error message block.
- `templates/base.html` — conditional navbar based on session state.

## Files to create
None.

## New dependencies
No new dependencies. Flask's built-in `session` (client-side signed cookie) is sufficient — no `flask-login` or server-side session store needed at this stage.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use Flask's built-in `session` object for auth state (`session['user_id']`); do not build a custom cookie/token scheme
- Give the same generic error message ("Invalid email or password.") for both "no such user" and "wrong password" cases — do not reveal which one failed
- `/logout` must work via a simple `GET` link (no form/CSRF handling introduced at this stage, consistent with the rest of the app)
- Do not implement `/profile` itself in this step — it can stay a placeholder string route; `POST /login` should still redirect there per the routes above

## Definition of done
- [ ] Submitting the login form with a valid, existing email/password combination establishes a session and redirects to `/profile`
- [ ] Submitting the login form with a non-existent email re-renders `login.html` with a visible, generic error and does not establish a session
- [ ] Submitting the login form with a valid email but wrong password re-renders `login.html` with the same generic error and does not establish a session
- [ ] Submitting the login form with a missing field re-renders `login.html` with a visible error
- [ ] After logging in, the navbar shows a "Logout" option instead of "Sign in" / "Get started"
- [ ] Visiting `/logout` while logged in clears the session and redirects to `/`; the navbar reverts to the logged-out state
- [ ] Visiting `/logout` while logged out does not error (redirects to `/` or `/login` gracefully)
