# Spendly — Expense Tracker

A Flask-based expense tracker built as a **learning project for using Claude Code**. The goal wasn't just to build an expense tracker — it was to learn how to work with Claude Code itself: specs, feature branches, custom slash commands, subagents, code review pipelines, and MCP servers, all built up incrementally, step by step.

## What it does

Spendly lets a user register, log in, and track personal expenses:

- **Auth** — register, login, logout (hashed passwords via Werkzeug)
- **Profile dashboard** — total spend, expense count, category breakdown, top category, recent expenses, and a date-range filter with quick presets (this month, last 30 days, this year)
- **Expenses** — add, edit, and delete expenses (amount, category, date, description), scoped per user
- **Analytics** — placeholder page reserved for a future step (charts/insights)
- **Static pages** — Terms and Privacy

Data is stored in SQLite (`expense_tracker.db`), auto-initialized and seeded with a demo user (`demo@spendly.com` / `demo123`) on first run.

## Why this project exists

This repo is a hands-on sandbox for learning Claude Code workflows rather than a production app. Notable artifacts from that process live alongside the code:

- **`.claude/specs/`** — a spec file per feature (registration, login/logout, profile, expense CRUD, database setup), written before implementation
- **`.claude/commands/`** — custom slash commands (`/create-spec`, `/code-review-feature`, `/test-feature`, `/seed-user`, `/seed-expense`, `/ship-feature`) that drive the create → implement → review → test → ship loop
- **`.claude/agents/`** — project-specific subagents for quality review, security review, and test writing/running against the Spendly codebase
- **`Claude_Docs/`** — notes on setting up MCP servers (SQLite, GitHub, Figma) and other Claude Code workflows used while building this

## Commands

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python app.py                 # runs on http://localhost:5001, debug=True
pytest                         # run tests
```

## Stack

- Flask 3 (single-file app, no blueprints)
- SQLite (raw `sqlite3`, no ORM)
- Jinja2 templates, plain CSS, vanilla JS (no frontend framework/bundler)
- pytest / pytest-flask for testing
- gunicorn for deployment (see `Procfile`)

## Architecture

- **`app.py`** — all routes: auth (`/register`, `/login`, `/logout`), profile/dashboard, expense CRUD (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`), analytics, and static pages
- **`database/db.py`** — `get_db()` / `init_db()` / `seed_db()` and the `CATEGORIES` list
- **`templates/`** — Jinja2 templates extending `base.html` (navbar, `{% block content %}`, footer)
- **`static/css/style.css`** — single stylesheet for the whole site
- **`static/js/main.js`** — shared JS; page-specific JS is inlined in templates via `{% block scripts %}`
- **`tests/`** — pytest test suite per feature
