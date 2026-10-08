# Recipe Box

A shared recipe box in the spirit of Paprika. It imports recipes from **web links**, **PDFs**, and **screenshots or photos**, and lets you review every import before saving it.

**Anyone can read every recipe without an account.** An account is needed to add one or to join the conversation under it, and only the person who uploaded a recipe can edit or delete it. Each account has a profile page listing what they've uploaded, and you can follow the cooks whose recipes you want to see.

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

To click around with something in the box, add a few demo accounts and recipes:

```bash
cd backend && .venv/bin/python manage.py seed_demo
```

It prints the usernames and the shared (fake) password it used. `--reset` recreates them. For an admin account of your own, use `manage.py createsuperuser`, or just sign up on the site.

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

## Accounts, profiles and following

- **Reading is open.** Recipes, profiles, tags and the landing page need no account.
- **Uploading needs one.** Adding a recipe, importing, commenting, liking and following all ask you to sign in first. Editing and deleting a recipe are limited to its owner.
- **Comments** sit under each recipe, oldest first, and you can reply to one. Anyone can read them. Their author can rewrite or remove their own, and a recipe's owner can remove one left on their recipe, so nobody has to live with what someone else wrote on their page. Deleting a comment takes its replies with it.
- **Threads are one level deep.** Replying to a reply joins the same thread and prefills an `@name` rather than nesting further, which keeps a long conversation readable on a phone.
- **Profiles** live at `/u/<username>` and list everything that person has uploaded, with a display name, a short bio and a photo.
- **The landing page** shows the newest recipes from the people you follow, then what's popular across the whole box — most viewed and liked, with a like counting for ten views. A view is counted once per browser session, and looking at your own recipe doesn't count.
- **Deleting an account** is under Edit profile → Delete account, and asks for the password again. It removes the user and everything they made for good: recipes with their photos and files, profile and photo, likes and follows. Their comments on other people's recipes stay, with the author cleared, and show as **[deleted]** like on Reddit; only the recipe's owner can remove those. Like counts on other people's recipes are corrected (`DELETE /api/users/me/` with `{"password": …}`).
- **Terms and privacy.** `/terms` and `/privacy` hold the Terms of Service and Privacy Policy, linked from every page's footer. Signing up requires ticking "I'm at least 13 and agree…", and the time is saved as `Profile.terms_accepted_at`. Before launch, fill in the operator name, contact email, mailing address and governing state at the top of `frontend/src/pages/LegalPage.tsx`.
- Signing in uses a Django session cookie, so writes carry a CSRF token. In development the dev server's origin (`http://localhost:5173`) is trusted automatically; in production the app and the React build share one origin.

## Using recipes

- Search across titles, ingredients, tags, notes, and sources.
- Filter by tag, by the recipes you've liked, or by your own, and sort by newest, popular, most liked, most viewed, title, or rating.
- Scale ingredients ½× to 3×. Fractions, ranges, gram amounts in parentheses, and unit plurals are handled.
- Tap ingredients to cross them off, and tap a step to mark your place.
- "Keep screen on" uses the Wake Lock API.
- In the editor, lines starting with `#` become section headings ("# For the frosting").

## Tests

```bash
cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python manage.py test recipes
cd frontend && npm run lint && npm run build
```

The backend tests generate their own sample screenshots and PDFs, including a two-column card, a scanned PDF, and two overlapping phone screenshots. They cover parsing, layout, the Claude request and fallback (mocked), the API, and accounts: who can read, who can upload, profiles, following, likes, comments, view counts, and the CSRF checks on signing in.

## Project layout

```
backend/
  config/                 Django settings & URLs
  accounts/
    models.py             Profile, Follow
    views.py, urls.py     sign up/in/out, profiles, following (/api/auth/…, /api/users/…)
  recipes/
    models.py             Recipe, Tag, Like, Comment, Attachment
    permissions.py        public to read, owner to change
    views.py, urls.py     REST API (/api/recipes, /api/import/...)
    importers/
      url.py              link & bookmarklet imports (schema.org → text fallback)
      fetch.py            HTTP fetching with size limits, timeouts, private-address guard
      files.py            PDF / image imports, multi-screenshot merging
      pdf.py, ocr.py      text-layer extraction, OCR (Apple Vision / Tesseract)
      layout.py           reading order from positioned text (columns, rows)
      text_parser.py      rule-based recipe parser
      llm.py              optional Claude extraction
    management/commands/  seed_demo
    tests/
frontend/src/
  auth.ts                 who's signed in (context + hook)
  pages/                  Home, Recipe, Profile, Sign in/up, Editor (also the import review), Import, Capture
  components/             cards, avatar, like button, comments, rating, tag input, file drop, source preview, bookmarklet
  lib/                    scaling, formatting
```

## Deploying to EC2 + RDS

[`deploy.sh`](deploy.sh) sets up an EC2 instance the same way as Filler-Local: nginx serves the React build and proxies `/api` to gunicorn (systemd), and Django uses **PostgreSQL on RDS** with IAM auth. RDS doesn't offer SQLite, so production uses Postgres; locally the app still uses SQLite unless `DB_HOST` is set.

`deploy.sh` always deploys the latest `main` from GitHub (`waltersIT/recipe-box`): every run pulls `main`, and if `main`'s copy of `deploy.sh` differs from the one you started, it re-runs itself as `main`'s copy. Local changes aren't deployed until they're pushed. (Ubuntu AMIs use `ubuntu@` instead of `ec2-user@`.)

To check the database connection before the first deploy (the instance's IAM role, security groups, the `rds_iam` grant, and whether the database exists), run the preflight on the instance:

```bash
ssh -t ec2-user@<instance> 'curl -fsSL https://raw.githubusercontent.com/waltersIT/recipe-box/main/recipe/check-db.sh -o check-db.sh && sudo bash check-db.sh <rds-endpoint>'
```

First deploy on a new instance:

```bash
ssh -t ec2-user@<instance> 'curl -fsSL https://raw.githubusercontent.com/waltersIT/recipe-box/main/recipe/deploy.sh -o deploy.sh && sudo bash deploy.sh'
```

After that, push to `main` and redeploy with:

```bash
ssh -t ec2-user@<instance> 'sudo /srv/recipe-box/deploy.sh'
```

The first run asks for:
- a domain (optional)
- the RDS endpoint, database name, and user
- IAM or password database auth
- whether to put the whole site behind one shared password (off by default)
- an Anthropic key (optional)

It then installs everything, creates the database if needed, migrates, and starts the site. If you give a domain it offers a free Let's Encrypt certificate. Redeploys pull `main` again and rebuild. Settings, the database, and uploads are kept.

AWS setup it expects:
- **Instance security group:** 80 and 443 open.
- **RDS security group:** allows 5432 from the instance's security group.
- **IAM auth:**
  - An instance role with `rds-db:connect` on the database user.
  - `GRANT rds_iam TO <user>;` run once in the database.

The site is open to the web by default: anyone can read recipes, and an account is needed to add one. `deploy.sh` still offers one shared nginx password over the whole site if you'd rather nobody sees it at all. Without a domain the site is plain HTTP, so point a domain at it and turn on HTTPS before anyone signs in over it.

Useful commands on the instance:
- Settings: `sudo /srv/recipe-box/deploy.sh --reconfigure`
- An admin account: `sudo -u recipebox /srv/recipe-box/backend/.venv/bin/python /srv/recipe-box/backend/manage.py createsuperuser`
- Logs: `journalctl -u recipe-box -f`
- Uploads live in `/var/lib/recipe-box/media`, outside the code directory.
- The git checkout of `main` lives in `/srv/recipe-box-src`, and `/srv/recipe-box` is synced from its `recipe/` folder.

Link fetching refuses private and link-local addresses, which includes the EC2 metadata service. If other people will import through the server, see the notes on site terms below.

## A note on site terms

Link imports fetch one page per request, when you ask, and send a normal browser User-Agent (change it with `RECIPE_FETCH_USER_AGENT`). The app doesn't crawl, and it doesn't try to get past bot challenges. When a site blocks the server, the bookmarklet uses the page your browser already loaded.

Recipes are saved with their source link, author, and site name. For a personal recipe box this is the same model Paprika and similar apps use. A site where accounts upload recipes for anyone to read is a different picture: many large recipe publishers' terms prohibit automated access, and photos and write-ups are copyrighted even when ingredient lists aren't. Imports are limited to signed-in accounts, which at least ties every upload to someone, but if you open this up publicly the copies of other sites' pages are yours to answer for.
