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
| 5 | The Garage | ✅ done |
| 6 | Meet drops | ✅ done |
| 7 | Admin panel | ✅ done |

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

## Stripe test mode (optional)

By default checkout uses a **mock** payment that "succeeds" instantly. To try
a real payment flow, switch to **Stripe Checkout in test mode**. Buyers are
sent to Stripe's hosted test checkout page, and no real money ever moves.

1. Get test API keys. Either use a [Stripe sandbox](https://docs.stripe.com/sandboxes)
   from the Dashboard, or skip sign-up with the Stripe CLI: `stripe sandbox create`.
   A **restricted key** (`rk_test_...`) with write access to *Checkout Sessions*
   is safest. A secret key (`sk_test_...`) also works.
2. Set these in `.env`, or `export` them in your shell:
   ```bash
   PAYMENT_PROVIDER=stripe
   STRIPE_SECRET_KEY=rk_test_...
   ```
3. Forward Stripe's webhooks to the app. This is the reliable way an order gets
   fulfilled, because it works even if the buyer closes the tab after paying:
   ```bash
   stripe listen --forward-to localhost:5000/shop/stripe/webhook
   ```
   Copy the `whsec_...` it prints into `STRIPE_WEBHOOK_SECRET`, then restart the app.
4. Check out with card **4242 4242 4242 4242**, any future expiry date and any CVC.
   Other [test cards](https://docs.stripe.com/testing) simulate declines and 3-D Secure.

How it works:

- The app **refuses to start with a live key** (`sk_live_...`), so a real card
  can never be charged by mistake.
- Checkout creates a *pending* order, then a Checkout Session using the prices
  copied onto that order. The cart is kept until payment is confirmed, so
  cancelling on Stripe's page loses nothing.
- An order counts only once Stripe says its session is **paid, for this order,
  for this exact amount**. The app checks this in two places, and both call
  `fulfill_order()`, which claims the order atomically, so codes and fund money
  are never doubled:
  - the signed webhook (`checkout.session.completed` /
    `async_payment_succeeded`);
  - the buyer's return page, which asks Stripe directly so codes show
    immediately.
- Expired or failed sessions mark the pending order `failed`.
- Before going anywhere near live mode, keep the webhook (it's required for
  delayed payment methods) and work through Stripe's
  [go-live checklist](https://docs.stripe.com/get-started/checklist/go-live).

## Admin password

The admin password is never stored, only its hash:

```bash
python -m flask --app app hash-password
```

Paste the printed `ADMIN_PASSWORD_HASH='...'` line into `.env`. Keep the single
quotes, because the hash contains `$` characters. Restart the app, then go to
**`/admin`**. Without a hash, admin login is switched off.

If you run locally without a `.env` loader, set it in your shell instead:
`export ADMIN_PASSWORD_HASH='scrypt:...'` before `python -m flask --app app run`.

## The admin panel (`/admin`)

| Section | What it does |
|---|---|
| Dashboard | Money raised / spent / in the kitty, the current goal, the open vote, the next meet, recent orders |
| Codes | Make a batch of codes (up to 500) for fresheners sold in person. Each batch has a **printable tag sheet** (QR code + code, cut along the dashed lines), a **CSV**, and a **ZIP of QR images** (one PNG per code) |
| Vote rounds | Create a draft, add parts and their budget / mid-range / high-end tiers, then **open** it with a close time (your local time). Extend the close time or **close it now**. The winner becomes the funding goal (or "Up next") |
| Installs | Log a finished install: part, tier, real cost, date, YouTube/TikTok link, before/after photos. Tick "completes the current goal" to move the progress bar on to the next part. Edit installs later (e.g. to add the real video) |
| Meets | Add meets (optionally selling the exclusive scent online), mark sold out / back in stock (the shop follows), delete |
| Garage | Hide or unhide cars instantly, and pick the Car of the Month |
| Fund | The ledger, plus manual adjustments (cash sales, donations, or negative corrections) |

**Security:**
- Only the password hash is stored.
- 5 wrong passwords from one IP in 15 minutes locks that IP out.
- The admin is logged out after 2 hours of inactivity (`ADMIN_SESSION_MINUTES`).
- Every admin form has CSRF protection.
- Admin pages are sent with `Cache-Control: no-store` and
  `X-Robots-Tag: noindex`, so they aren't cached or indexed by search engines.

## Settings (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs cookies and CSRF tokens. **Set it in production.** | dev value |
| `ADMIN_PASSWORD_HASH` | Hash of the admin password | empty (admin locked) |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///instance/salvage_scent.db` |
| `INSTANCE_DIR` | Folder for database + uploads | `./instance` (`/data` in Docker) |
| `CODE_ATTEMPT_LIMIT` / `CODE_ATTEMPT_WINDOW_MINUTES` | Wrong-code lockout | 10 per 15 min |
| `ADMIN_LOGIN_ATTEMPT_LIMIT` | Wrong admin passwords allowed per IP per window | 5 |
| `ADMIN_SESSION_MINUTES` | Idle minutes before the admin is logged out | 120 |
| `TRUST_PROXY` | Set `1` behind nginx/a PaaS so real visitor IPs are used | `0` |
| `SHOP_TIMEZONE` | Your local time zone; decides which meets are "upcoming" today | `America/New_York` |
| `SESSION_COOKIE_SECURE` | Set `1` when served over HTTPS | `0` |
| `PAYMENT_PROVIDER` | `mock` or `stripe` (test mode only) | `mock` |
| `STRIPE_SECRET_KEY` | Stripe **test** key (`rk_test_...` / `sk_test_...`). Live keys are refused | empty |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `/shop/stripe/webhook` (`whsec_...`) | empty (webhook off) |
| `STRIPE_CURRENCY` | Checkout currency | `usd` |

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
    payments.py        MockPaymentProvider and StripePaymentProvider (Checkout, test mode only)
    qr.py              QR code PNGs (as data: URIs) via the `qrcode` library
    voting.py          open round, time left, results, casting votes, closing rounds
    rate_limit.py      locks out an IP after too many wrong codes
    garage.py          Garage profiles: code-as-key, save/delete, Car of the Month
    uploads.py         safe photo uploads (validate, resize, strip EXIF/GPS, random names)
    meets.py           upcoming/past meets, status, "in 3 weeks", .ics calendar files
    clock.py           local time (SHOP_TIMEZONE) <-> UTC stored in the database
    installs.py        logging installs: photos, video check, completing the current goal
    admin_auth.py      admin password check (hash only) and idle timeout
    catalog.py         featured products, lowest price, product photo paths
  routes/              one Flask blueprint per site section
    main.py            home page
    car.py             Revival Car page (profile, totals, installs, build log)
    shop.py            product list/detail, SVG placeholder photos, cart, checkout, confirmation,
                       Stripe return page and signed Stripe webhook
    vote.py            ballot (code + part/tier), results page, past rounds
    garage.py          Garage grid, car pages, join with a code, edit, delete
    meets.py           meet drops page + "Add to calendar" (.ics) downloads
    admin/             the admin panel: one file per section (auth, dashboard,
                       codes, rounds, installs, meets, garage, fund) + forms.py
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
     away. The Stripe one redirects to Stripe Checkout and confirms later (see
     "Stripe test mode" above).
  3. `fulfill_order()` does everything a sale earns in one database commit:
     codes, blind-bag reveals and the fund entry. It does nothing if the order
     is already paid, so a webhook firing twice is harmless.
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
- **The Garage:**
  - There are no accounts: a freshener code is the key. After a correct code
    (rate-limited), its id is kept in the signed session cookie, and that
    browser can create or edit that code's **one** profile.
  - The code is never shown on public pages. "Forget my code on this device"
    clears it.
  - Hidden profiles (admin moderation, stage 7) disappear from the grid, their
    page and Car of the Month.
- **Photo uploads** (`services/uploads.py`):
  - Limited to 5 MB per request.
  - Opened with Pillow to prove they are real JPEG, PNG or WebP files.
    Absurd dimensions are refused before decoding ("decompression bombs").
  - Rotated upright, shrunk to 1600px, and re-saved as a new JPEG under a
    random name. This also strips all EXIF data, including GPS location.
- **Meet drops:**
  - Meets from today on are "upcoming" (the soonest one is featured as
    "Next up"); earlier ones are "past". "Today" is the shop's local date
    (`SHOP_TIMEZONE`), not the server's.
  - Each meet shows one status: **Sold out**, **On sale now** (with a buy
    button), **At the meet only** (no online product), **A few left online**,
    or **Meet over**.
  - Marking a meet sold out also blocks its exclusive product from the cart.
  - "Add to calendar" downloads a standard `.ics` file that works with Apple,
    Google and Outlook calendars.
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
