# Recipe Box

A personal recipe manager in the spirit of Paprika. It imports recipes from **web links**, **PDFs**, and **screenshots or photos**, and lets you review every import before saving it.

- **Backend:** Django 6 + Django REST Framework, SQLite (`backend/db.sqlite3`)
- **Frontend:** React 19 + TypeScript + Vite

## Quick start

```bash
./dev.sh
```

This creates the Python virtualenv and installs packages on the first run. It then migrates the database and starts both servers: the API on http://127.0.0.1:8000 and the app on http://localhost:5173 (opened for you). Press Ctrl+C to stop both.

To run the servers yourself:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000

# second terminal
cd frontend && npm install && npm run dev
```

Vite proxies `/api` and `/media` to Django, so the browser only talks to one origin.

## Importing recipes

Every import opens in the editor first, so you can check it before saving. PDF and screenshot imports show the original next to the editor. The original files are kept with the recipe under "Original files".

| Source | How it's read |
| --- | --- |
| **Link** | The page is fetched once and its [schema.org Recipe](https://schema.org/Recipe) data is read with [recipe-scrapers](https://github.com/hhursev/recipe-scrapers). Most recipe sites publish this data for search engines, so these imports are usually exact. Pages without it are reduced to their main text and parsed. |
| **Bookmarklet** | For sites that block server requests (some return 402/403). Drag "Save to Recipe Box" from the Import page to your bookmarks bar, then click it on a recipe page. Your own browser sends the page it already loaded. |
| **PDF** | PDFs with a real text layer (saved from a browser or recipe app) are read with text positions, so two-column layouts come out in order. Scanned pages go through OCR. |
| **Screenshots / photos** | OCR, with layout reconstruction for multi-column recipe cards. You can add several screenshots of one recipe at once: overlapping lines are removed and phone chrome (status bar, URL bar, "Jump to Recipe", ratings) is filtered out. Paste a screenshot with ⌘V, or drop in a HEIC photo. |

### Two parsing engines

- **Built-in (default, free, offline):** OCR uses Apple's Vision framework on macOS, with nothing to install. On Linux, install `tesseract` instead. A rule-based parser then finds the title, times, servings, ingredient and step sections, sub-headings, notes, and nutrition.
- **Claude (optional, more accurate on messy layouts):** add an API key and PDFs, screenshots, and pages without recipe data are sent to Claude instead. It returns structured JSON. If Claude fails for any reason, the import falls back to the built-in parser. Link imports with schema.org data never use Claude.

```bash
cp backend/.env.example backend/.env
# then set ANTHROPIC_API_KEY=sk-ant-... in backend/.env and restart the backend
```

Settings in `backend/.env`:
- `RECIPE_LLM`: `auto` (use Claude when a key is set), `on`, or `off`.
- `RECIPE_LLM_MODEL`: defaults to `claude-opus-5`.
- `RECIPE_LLM_EFFORT`: defaults to `low`, which is plenty for transcription.

A typical import costs a few cents.

## Using recipes

- Search across titles, ingredients, tags, notes, and sources.
- Filter by tag or favorites, and sort by newest, title, rating, or recently edited.
- Scale ingredients ½× to 3×. Fractions, ranges, gram amounts in parentheses, and unit plurals are handled.
- Tap ingredients to cross them off, and tap a step to mark your place.
- "Keep screen on" uses the Wake Lock API.
- In the editor, lines starting with `#` become section headings ("# For the frosting").

## Tests

```bash
cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python manage.py test recipes
cd frontend && npm run lint && npm run build
```

The backend tests generate their own sample screenshots and PDFs, including a two-column card, a scanned PDF, and two overlapping phone screenshots. They cover parsing, layout, the Claude request and fallback (mocked), and the API.

## Project layout

```
backend/
  config/                 Django settings & URLs
  recipes/
    models.py             Recipe, Tag, Attachment
    views.py, urls.py     REST API (/api/recipes, /api/import/...)
    importers/
      url.py              link & bookmarklet imports (schema.org → text fallback)
      fetch.py            HTTP fetching with size limits, timeouts, private-address guard
      files.py            PDF / image imports, multi-screenshot merging
      pdf.py, ocr.py      text-layer extraction, OCR (Apple Vision / Tesseract)
      layout.py           reading order from positioned text (columns, rows)
      text_parser.py      rule-based recipe parser
      llm.py              optional Claude extraction
    tests/
frontend/src/
  pages/                  Library, Recipe, Editor (also the import review), Import, Capture
  components/             cards, rating, tag input, file drop, source preview, bookmarklet
  lib/                    scaling, formatting
```

## Deploying to EC2 + RDS

[`deploy.sh`](deploy.sh) sets up an EC2 instance the same way as Filler-Local: nginx serves the React build and proxies `/api` to gunicorn (systemd), and Django uses **PostgreSQL on RDS** with IAM auth. RDS doesn't offer SQLite, so production uses Postgres; locally the app still uses SQLite unless `DB_HOST` is set.

From your Mac, copy the folder up and run the script on the instance (Ubuntu AMIs use `ubuntu@` instead of `ec2-user@`):

```bash
rsync -az --delete --exclude .venv --exclude node_modules --exclude dist --exclude db.sqlite3 --exclude media --exclude .env ~/Desktop/recipe-box/recipe/ ec2-user@<instance>:recipe/
```

To check the database connection before deploying (the instance's IAM role, security groups, the `rds_iam` grant, and whether the database exists), run the preflight on the instance:

```bash
ssh -t ec2-user@<instance> 'sudo ~/recipe/check-db.sh <rds-endpoint>'
```

Then deploy:

```bash
ssh -t ec2-user@<instance> 'sudo ~/recipe/deploy.sh'
```

The first run asks for:
- a domain (optional)
- the RDS endpoint, database name, and user
- IAM or password database auth
- a site username and password
- an Anthropic key (optional)

It then installs everything, creates the database if needed, migrates, and starts the site. If you give a domain it offers a free Let's Encrypt certificate. To redeploy, run the same two commands again. Settings, the database, and uploads are kept.

AWS setup it expects:
- **Instance security group:** 80 and 443 open.
- **RDS security group:** allows 5432 from the instance's security group.
- **IAM auth:**
  - An instance role with `rds-db:connect` on the database user.
  - `GRANT rds_iam TO <user>;` run once in the database.

The whole site sits behind a username and password (nginx basic auth), because the app has no accounts yet. Without a domain the site is plain HTTP, so point a domain at it and turn on HTTPS.

Useful commands on the instance:
- Settings: `sudo /srv/recipe-box/deploy.sh --reconfigure`
- Logs: `journalctl -u recipe-box -f`
- Uploads live in `/var/lib/recipe-box/media`, outside the code directory.

Link fetching refuses private and link-local addresses, which includes the EC2 metadata service. If other people will import through the server, see the notes on site terms below.

## A note on site terms

Link imports fetch one page per request, when you ask, and send a normal browser User-Agent (change it with `RECIPE_FETCH_USER_AGENT`). The app doesn't crawl, and it doesn't try to get past bot challenges. When a site blocks the server, the bookmarklet uses the page your browser already loaded.

Recipes are saved with their source link, author, and site name. For a personal recipe box this is the same model Paprika and similar apps use. Turning it into a shared or commercial service changes the picture: many large recipe publishers' terms prohibit automated access, and photos and write-ups are copyrighted even when ingredient lists aren't.
