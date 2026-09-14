# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask-based expense tracker ("Spendly") built incrementally as a step-by-step learning project. Large parts of the app are intentionally unimplemented placeholders (see `app.py`) — routes like `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, and `/expenses/<id>/delete` return literal "coming in Step N" strings, and `database/db.py` is a stub with only a docstring describing the functions to write (`get_db()`, `init_db()`, `seed_db()`). Don't assume backend functionality exists just because a route or template references it — check `app.py` and `database/db.py` first.

## Commands

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python app.py                 # runs on http://localhost:5001, debug=True
pytest                        # run tests (pytest-flask installed, no tests written yet)
```

There is no build step, linter, or frontend bundler — templates are Jinja2, styling is a single plain CSS file, and JS is vanilla (no framework, no npm).

## Architecture

- **`app.py`** — single-file Flask app; all routes live here (no blueprints). Fully working routes (`/`, `/register`, `/login`, `/terms`, `/privacy`) just render templates. Placeholder routes return plain strings and are meant to be filled in by students.
- **`database/`** — `db.py` is currently a stub (get_db/init_db/seed_db not yet implemented); `__init__.py` is empty.
- **`templates/`** — Jinja2 templates. `base.html` is the shared layout: navbar, `{% block content %}`, and a footer with Terms/Privacy links. Page templates (`landing.html`, `login.html`, `register.html`, `terms.html`, `privacy.html`) extend it via `{% extends "base.html" %}` and fill `title`, `content`, and optionally `scripts` blocks.
- **`static/css/style.css`** — single stylesheet for the entire site (no per-page CSS files); all pages share this theme (fonts: DM Serif Display + DM Sans, loaded from Google Fonts in `base.html`).
- **`static/js/main.js`** — currently just a placeholder comment; page-specific JS (e.g. the landing page's "how it works" modal) is inlined in the template's `{% block scripts %}` instead of this file.

## Working style on this repo

Changes here tend to be scoped narrowly (e.g. "only touch the hero section", "do not modify anything else on the page") — treat instructions about limiting the blast radius of an edit literally, and don't refactor or touch unrelated templates/CSS/routes while completing a task.
