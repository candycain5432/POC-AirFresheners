# Salvage & Scent — proof-of-concept site

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
| 2 | Home page and Revival Car page | ✅ done |
| 3 | Shop and mock checkout with code generation | ✅ done |
| 4 | Voting | ✅ done |
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
python -m flask --app app run --debug   # http://127.0.0.1:5000
```

If you are upgrading from an earlier stage, run `python seed.py` again. The
database gained new columns (`vote_round.closes_at`, `product.is_featured`) and
a new file name (`salvage_scent.db`).

Every new terminal needs `source .venv/bin/activate` again. If you see
`flask: command not found` or `No module named flask`, the virtualenv isn't
active.

`seed.py` prints a few unused freshener codes at the end. Keep them handy for
testing voting and the Garage.

Run the tests with `pytest -q`.

## Run it with Docker

```bash
cp .env.example .env               # then edit SECRET_KEY and ADMIN_PASSWORD_HASH
docker compose up -d --build       # http://localhost:8000
docker compose run --rm web python seed.py
```

The database and uploaded photos live in the `salvage_data` Docker volume, so they
survive rebuilds. `docker compose down -v` deletes them.

## Admin password

The admin password is never stored, only its hash:

```bash
python -m flask --app app hash-password
```

Paste the printed `ADMIN_PASSWORD_HASH='...'` line into `.env`. Keep the single
quotes, because the hash contains `$` characters.

## Settings (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs cookies and CSRF tokens. **Set it in production.** | dev value |
| `ADMIN_PASSWORD_HASH` | Hash of the admin password | empty (admin locked) |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///instance/salvage_scent.db` |
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
  security_headers.py  Content-Security-Policy and other strict browser headers
  services/            business rules as plain functions (routes stay thin)
    codes.py           secure code generation and lookup
    fund.py            raised / spent / on hand, and progress toward the current goal
    embeds.py          turns YouTube/TikTok links into safe embed URLs (others are rejected)
    cart.py            the cart, stored in the signed session cookie (prices always re-read from the DB)
    checkout.py        create_pending_order() and fulfill_order(): codes, blind bags, fund
    payments.py        MockPaymentProvider, and the notes for adding Stripe test mode
    qr.py              QR code PNGs (as data: URIs) via the `qrcode` library
    voting.py          open round, time left, results, casting votes, closing rounds
    rate_limit.py      locks out an IP after too many wrong codes
    catalog.py         featured products, lowest price, product photo paths
  routes/              one Flask blueprint per site section
    main.py            home page
    car.py             Revival Car page (profile, totals, installs, build log)
    shop.py            product list/detail, SVG placeholder photos, cart, checkout, confirmation
    vote.py            ballot (code + part/tier), results page, past rounds
    errors.py          friendly 404 / 413 / 500 pages
  templates/           Jinja templates (base.html layout, partials/ for the progress bar and video)
  static/css/style.css the whole look: mobile-first, dark garage theme, no framework
  static/fonts/        Barlow, Barlow Condensed, IBM Plex Mono (self-hosted, SIL Open Font License)
  static/img/          placeholder photos (hero, before/now, products) + noise.svg texture
  static/js/site.js    mobile menu + click-to-load videos (pages work without it)
seed.py                sample data (WIPES the database)
tools/make_placeholder_art.py   redraws the placeholder images in app/static/img/
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
- **Install videos load only when tapped.** The page shows a play button, and
  YouTube (privacy-enhanced domain) or TikTok is contacted only after a tap.
  Shorts and TikToks are shown in a vertical frame.
- **Content-Security-Policy** allows scripts and styles from this site only, and
  frames only from YouTube/TikTok. There is no inline JavaScript anywhere.
- **Checkout runs in two steps**, so a real payment provider can slot in later:
  1. `create_pending_order()` copies names and prices from the database (never
     from the cookie).
  2. A payment provider is called. The mock provider reports "paid" straight
     away; a Stripe one would redirect to Stripe and confirm later via a webhook.
  3. `fulfill_order()` does everything a sale earns in one database commit:
     codes, blind-bag reveals and the fund entry. It does nothing if the order
     is already paid, so a webhook firing twice is harmless. The steps for
     adding Stripe are in `app/services/payments.py`.
- **Order confirmation pages are private.** They show the voting codes, so only
  the browser that placed the order can open them (remembered in its session).
  Each code also gets a QR image that links to the vote page.
- **Voting:**
  - The ballot is "part + tier together": one choice per code per round.
  - The server checks that the round is open, the choice belongs to that round
    (no tampering), the code exists, and the code hasn't voted in this round.
    The database's unique constraint is the final guard against double votes.
  - A QR code links to `/vote/?code=...`, which fills in the code box.
- **Closing a round:**
  - A round closes itself the first time any page is viewed after its close
    time ("close on read", since there is no scheduler). The admin will also be
    able to close one by hand in stage 7.
  - The winner is the tier with the most votes; ties go to the cheaper tier.
  - The winner becomes the funding goal straight away if nothing is being
    funded. Otherwise it is **queued** ("Up next" on the progress card) and
    becomes active when the current part is installed.
- **Rate limiting** records wrong code guesses per IP in the database, so it
  works across several server processes.

## Design notes

The look is a clean vintage race program with some garage grit:

- **Colours:** an off-white page (`#f4f1ea`), near-black ink and one accent,
  racing red (`#d42a1f`). All colours are CSS variables at the top of
  `style.css`.
- **Contrast:** secondary grey text uses `--muted` (`#5f5952`), which passes
  WCAG AA (at least 4.5:1) on every light background. Dark sections use
  `--muted-on-dark` and `--accent-on-dark`. A test (`tests/test_redesign.py`)
  checks these ratios.
- **Checkered flags:** header and footer bands, the vote section, the
  "finish line" on progress bars, and chase reveals. All drawn in CSS.
- **Garage grit:**
  - "How it works" and "Latest install" are full-width near-black bands.
  - Section headers sit on a faint concrete texture (`static/img/noise.svg`).
  - Small labels are stamped parts tags: monospace capitals, a thin border and
    a punched hole.
- **Fonts:** Barlow Condensed (headings), Barlow (text) and IBM Plex Mono
  (labels, codes). All are stored in `app/static/fonts/`.
- **Mobile:** every page is checked at 375px wide. Tap targets are at least
  44px tall, there is no sideways scrolling, and text is 12px or larger.
- **No inline styles or scripts**, which keeps the strict Content-Security-Policy
  working.

## Photos to replace

Placeholder images are drawn by `tools/make_placeholder_art.py`. Overwrite them
with real photos using the **same file names**:

| File | Used on | Size |
|---|---|---|
| `app/static/img/lazarus-hero.jpg` | Home page hero | landscape, about 1600 x 1280 |
| `app/static/img/lazarus-before.jpg` | Revival Car: Before / Now slider | about 1600 x 1000 |
| `app/static/img/lazarus-now.jpg` | Revival Car: Before / Now slider | same angle and size as Before |
| `app/static/img/products/<slug>.jpg` | Shop and home | square, about 800 x 800 |

A product with no photo falls back to a drawn SVG placeholder automatically.

## Sample data

Everything in `seed.py` is fictional. The Revival Car is described generically,
and none of the data or images use carmaker names or logos. The install video
links point to a placeholder video and a placeholder TikTok URL. Swap in real
links from the admin panel.
