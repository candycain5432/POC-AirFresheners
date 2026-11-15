# Rust & Revival — proof-of-concept site

Handmade aroma-bead car fresheners. Every sale funds the rebuild of a junk
project car ("the Revival Car"), buyers vote on the next part with the code
on their freshener, and every install is filmed.

> **Proof of concept: no real purchases are processed.**

Stack: Python 3.13, Flask, SQLite (via Flask-SQLAlchemy), Jinja templates,
plain CSS and a little vanilla JS. No frontend framework.

## Build progress

| Stage | What | Status |
|---|---|---|
| 1 | Project skeleton, database models, seed data | ✅ done |
| 2 | Home page and Revival Car page | ⏳ |
| 3 | Shop and mock checkout with code generation | ⏳ |
| 4 | Voting | ⏳ |
| 5 | The Garage | ⏳ |
| 6 | Meet drops | ⏳ |
| 7 | Admin panel | ⏳ |

## Run it locally

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional locally; defaults work for development
python seed.py                     # WIPES and fills the database with sample data
flask --app app run --debug        # http://127.0.0.1:5000
```

`seed.py` prints a few unused freshener codes at the end. Keep them handy for
testing voting and the Garage.

Run the tests with `pytest -q`.

## Run it with Docker

```bash
cp .env.example .env               # then edit SECRET_KEY and ADMIN_PASSWORD_HASH
docker compose up -d --build       # http://localhost:8000
docker compose run --rm web python seed.py
```

The database and uploaded photos live in the `rr_data` Docker volume, so they
survive rebuilds. `docker compose down -v` deletes them.

## Admin password

The admin password is never stored, only its hash:

```bash
flask --app app hash-password
```

Paste the printed `ADMIN_PASSWORD_HASH='...'` line into `.env`. Keep the single
quotes, because the hash contains `$` characters.

## Settings (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs cookies and CSRF tokens. **Set it in production.** | dev value |
| `ADMIN_PASSWORD_HASH` | Hash of the admin password | empty (admin locked) |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///instance/rust_revival.db` |
| `INSTANCE_DIR` | Folder for database + uploads | `./instance` (`/data` in Docker) |
| `CODE_ATTEMPT_LIMIT` / `CODE_ATTEMPT_WINDOW_MINUTES` | Wrong-code lockout | 10 per 15 min |
| `TRUST_PROXY` | Set `1` behind nginx/a PaaS so real visitor IPs are used | `0` |
| `SESSION_COOKIE_SECURE` | Set `1` when served over HTTPS | `0` |

## Project structure

```
app/
  __init__.py          create_app(): builds the Flask app and wires everything together
  config.py            settings, read from environment variables
  extensions.py        shared db (SQLAlchemy) and csrf objects
  cli.py               `flask hash-password`
  template_helpers.py  Jinja filters: money, nice_date, code
  models/              database tables, one file per area
    car.py             Revival Car, photos, build log, installs, funding goals, fund ledger
    shop.py            products, blind-bag scents, orders, order items
    codes.py           freshener codes and admin code batches
    voting.py          rounds -> part options -> tiers, and votes
    garage.py          member cars, Car of the Month
    meets.py           meet drops
    security.py        failed-attempt log for rate limiting
  services/            business rules as plain functions (routes stay thin)
    codes.py           secure code generation and lookup
  routes/              one Flask blueprint per site section
  templates/           Jinja templates
  static/              CSS and JS
seed.py                sample data (WIPES the database)
seed_images.py         draws placeholder photos with Pillow
tests/                 pytest smoke tests
```

### Key ideas

- **Money is stored in whole cents** (`800` = $8.00) to avoid rounding errors.
- **The fund:** every dollar in is a `FundEntry` row (a mock sale, or a manual
  admin adjustment). Every dollar out is an `Install` row.
  - Money on hand = total raised − total spent.
  - The progress bar compares money on hand with the active `FundingGoal`, which
    is the winner of the last closed vote round.
- **Freshener codes** are 10 characters from `23456789ABCDEFGHJKMNPQRSTUVWXYZ`,
  with no O/0 or I/1/L look-alikes. They are made with Python's `secrets` module
  and shown as `K7PX-M3QD-WR`. Each physical freshener gets one code, so a
  3-pack gives three votes.
- **One vote per code per round** is enforced by a database unique constraint,
  not just by app code.
- **Rate limiting** records wrong code guesses per IP in the database, so it
  works across several server processes.

## Sample data

Everything in `seed.py` is fictional. The Revival Car is described generically,
and none of the data or images use carmaker names or logos. The install video
links point to a placeholder video and a placeholder TikTok URL. Swap in real
links from the admin panel.
