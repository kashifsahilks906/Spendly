# Spec: Registration

## Overview
Wire up the `/register` route so new users can actually create an account. The `register.html` template already has a working POST form (name, email, password) pointing at `/register`; this step adds the server-side handling that validates the input, hashes the password, and inserts a row into `users`. On success, the page shows a success message and then redirects the user to `/login` — registration does **not** log the user in automatically; they sign in separately afterward. This is the first step in the Spendly roadmap that makes the app stateful for a real visitor rather than just serving static/demo content, and every later step (login, profile, expense CRUD) depends on users being able to sign up first.

## Depends on
Step 01 — Database Setup (`users` table and `get_db()` must exist). Already complete.

## Routes
- `GET /register` — render the registration form (already exists, unchanged) — public
- `POST /register` — validate input, create the user, re-render `register.html` with a success message, then redirect to `/login` (no session is established) — public

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) from `database/db.py` already supports this feature.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — add a `{% if success %}<div class="auth-success">{{ success }}</div>{% endif %}` block (mirrors the existing `{% if error %}` block) shown above the form; when `success` is set, include a small inline script in `{% block scripts %}` that redirects to `/login` after a short delay (e.g. `setTimeout(() => window.location.href = "{{ url_for('login') }}", 2000)`). Add `{{ error }}`-driven validation messaging for specific failure cases (duplicate email, password too short) if not already generic enough. Form fields themselves are unchanged.

## Files to change
- `app.py` — implement `POST /register` handling: read form fields, validate, hash password, insert user, re-render `register.html` with a `success` message
- `static/css/style.css` — add `--success`/`--success-light` CSS variables and a `.auth-success` class analogous to the existing `--danger`/`--danger-light`/`.auth-error`

## Files to create
None.

## New dependencies
No new dependencies. No session/auth library is needed for this step since registration does not log the user in.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Re-render `register.html` with an `error` message on validation failure (duplicate email, missing fields, short password) instead of raising a raw exception
- On success, re-render `register.html` with a `success` message and redirect to `/login` client-side (via inline JS) after a short delay — do not use a server-side `redirect()` immediately, since the message must be visible first
- Do not set `session`/log the user in as part of registration — that belongs to the login step

## Definition of done
- [ ] Submitting the register form with a new name/email/password creates a row in `users` with a hashed (not plaintext) password
- [ ] On success, `register.html` re-renders showing a visible success message, then redirects to `/login` after a short delay
- [ ] Submitting with an email that already exists in `users` re-renders `register.html` with a visible error and does not insert a duplicate row
- [ ] Submitting with a missing field (empty name/email/password) re-renders `register.html` with a visible error and does not insert a row
- [ ] No `session` is established as part of registration (registration and login remain separate steps)
- [ ] Resubmitting the form before the redirect fires does not silently overwrite/duplicate data beyond the normal duplicate-email validation above
