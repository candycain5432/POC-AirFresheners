"""
Seed script: WIPES the database and fills it with realistic sample data.

    python seed.py            (locally, inside your virtualenv)
    docker compose run --rm web python seed.py   (in Docker)

What you get:
  * The Revival Car "Lazarus" with a story, photos and a build log
  * 5 completed installs, totalling $1,130 spent
  * A closed vote round whose winner (mid-range brake calipers, $650) is the
    active funding goal, with $310 on hand, so the bar reads "$340 to go"
  * An open vote round with 4 parts x 3 tiers and some votes already cast
  * Every product type, ~45 mock orders with freshener codes
  * A batch of admin codes, meet drops (past and upcoming), Garage members
    and a Car of the Month

Some freshener codes are printed at the end so you can try voting and the
Garage straight away.
"""
import os
import random
import shutil
from datetime import date, datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    BlindBagScent, BuildLogEntry, CarOfTheMonth, CarPhoto, CodeBatch, FreshenerCode, FundEntry,
    FundingGoal, GarageMember, Install, InstallPhoto, MeetDrop, Order, OrderItem, PartOption,
    PartTier, Product, RevivalCar, Vote, VoteRound,
)
from app.models._common import utcnow
from app.models.shop import BlindBagResult
from app.services.codes import create_codes, format_code, new_order_reference
from seed_images import make_placeholder

# A fixed random seed means the sample data looks the same every run
# (the freshener codes themselves still come from the secure generator).
rnd = random.Random(2026)


def dollars(amount):
    """Write prices naturally in this file: dollars(8) -> 800 cents."""
    return int(round(amount * 100))


def reset_database(app):
    print("Wiping database and uploads...")
    db.drop_all()
    db.create_all()
    upload_dir = app.config["UPLOAD_DIR"]
    shutil.rmtree(upload_dir, ignore_errors=True)
    os.makedirs(upload_dir, exist_ok=True)


# --------------------------------------------------------------------------
# The Revival Car
# --------------------------------------------------------------------------
def seed_car(upload_dir):
    car = RevivalCar(
        nickname="Lazarus",
        description="1980s two-door hatchback, pulled out of a hayfield after 14 years",
        acquired_on=date(2026, 3, 8),
        story=(
            "We found Lazarus sinking into a hayfield two hours north of the shop. The farmer said it "
            "had been parked there 'for a weekend' in 2012. Mice had moved into the headliner, the "
            "floor pans had more holes than metal, and the engine was seized solid.\n\n"
            "We paid $400 and a case of fresheners for it.\n\n"
            "Now every freshener you buy puts money into the build. You vote on which part goes in next, "
            "we buy it, install it, and film the whole thing - busted knuckles included. "
            "No sponsors, no shortcuts. Just a dead car, a lot of rust, and a community bringing it back."
        ),
    )
    db.session.add(car)
    photos = [
        ("As found", "Day one in the hayfield"),
        ("Driver side", "Surface rust and a sun-baked dash"),
        ("Engine bay", "Seized, but all there"),
        ("On the lift", "Floor pans: optimistic"),
    ]
    for i, (label, caption) in enumerate(photos):
        filename = make_placeholder(upload_dir, f"car_{i}.jpg", label, "Lazarus", seed=i)
        car.photos.append(CarPhoto(filename=filename, caption=caption, position=i))

    log = [
        (date(2026, 3, 8), "Dragged it home", "Winched out of the field, three flat tires, one very confused tow driver."),
        (date(2026, 3, 15), "Pressure wash and inventory", "Found a 1994 parking ticket and a family of mice. Evicted the mice."),
        (date(2026, 3, 29), "Engine un-seized", "Two weeks of penetrating oil down the plug holes. It turns by hand!"),
        (date(2026, 6, 14), "First start in 14 years", "Ran for 40 seconds on a can of fuel. We may have cried."),
        (date(2026, 9, 21), "Rolled out under its own power", "First trip around the block. Brakes are... a problem. Hence the vote."),
    ]
    for when, title, body in log:
        db.session.add(BuildLogEntry(happened_on=when, title=title, body=body))
    return car


def seed_installs(upload_dir):
    """Past completed installs. Each had a funding goal that is now 'installed'."""
    installs = [
        # part, tier, cost, date, video, notes
        ("Battery & cables", "budget", 95, date(2026, 4, 12),
         "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
         "Fresh battery and new terminals. The old cables crumbled when we touched them."),
        ("Fuel pump & lines", "mid", 210, date(2026, 5, 20),
         "https://www.youtube.com/shorts/aqz-KE-bpKQ",
         "Tank was full of varnish. New pump, new lines, new filter."),
        ("Radiator", "mid", 260, date(2026, 7, 2),
         "https://www.tiktok.com/@example/video/7300000000000000001",
         "Aluminium radiator swap. No more coolant fountain."),
        ("Tires (set of 4)", "budget", 380, date(2026, 8, 30),
         "https://youtu.be/aqz-KE-bpKQ",
         "Budget tires, but round and holding air - a big step up."),
        ("Ignition refresh", "mid", 185, date(2026, 10, 4),
         "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
         "Plugs, wires, coil and cap. Idles smooth for the first time."),
    ]
    for i, (part, tier, cost, when, video, notes) in enumerate(installs):
        goal = FundingGoal(part_name=part, tier=tier, goal_cents=dollars(cost), status="installed",
                           created_at=datetime.combine(when - timedelta(days=30), datetime.min.time()))
        install = Install(part_name=part, tier=tier, cost_cents=dollars(cost), installed_on=when,
                          video_url=video, notes=notes, goal=goal)
        db.session.add(install)
        for kind in ("before", "after"):
            fn = make_placeholder(upload_dir, f"install_{i}_{kind}.jpg", part, kind.upper(),
                                  accent=(120, 120, 120) if kind == "before" else (194, 87, 26), seed=10 + i)
            install.photos.append(InstallPhoto(kind=kind, filename=fn))
    return sum(dollars(row[2]) for row in installs)


# --------------------------------------------------------------------------
# Shop
# --------------------------------------------------------------------------
# Sample catalogue data lives at module level so other scripts (for example
# tools/make_placeholder_art.py, which draws one photo per product) can reuse it.

# meet name, date, location, exclusive scent, scent notes, quantity made, sold out?, colour
MEETS = [
    ("Spring Thaw Swap Meet", date(2026, 4, 25), "County Fairgrounds, Lot C", "Thaw Out",
     "Wet asphalt, cut grass and a hint of two-stroke.", 60, True, "#6f8f5a"),
    ("Summer Night Cruise", date(2026, 7, 18), "Riverside Diner parking lot", "Neon Nights",
     "Cherry soda, warm vinyl and late-night fries.", 80, True, "#b0306a"),
    ("Harvest Hoods Meet", date(2026, 10, 11), "Old Mill car park", "Harvest Hood",
     "Apple cider, woodsmoke and a warm engine bay.", 100, True, "#a8562a"),
    ("Frost Fest Cars & Coffee", date(2026, 12, 6), "Hilltop Coffee Roasters", "Cold Start",
     "Frosted pine, espresso and cold steel.", 120, False, "#4f7f99"),
    ("New Year Rust Run", date(2027, 1, 3), "Lakeside Industrial Park", "Rust Run",
     "Leather, clove and a little bit of gasoline (the nice kind).", 120, False, "#8a5a3b"),
]

# slug, name, kind, description, price ($), fresheners per unit, colour
PRODUCTS = [
    ("burnt-clutch", "Burnt Clutch", "regular",
     "Smoked vanilla, cedar and a whisper of tobacco. Smells like a hard launch.", 8, 1, "#c2571a"),
    ("fresh-primer", "Fresh Primer", "regular",
     "Clean cotton and bright citrus. A blank-slate scent for a blank-slate panel.", 8, 1, "#9aa0a6"),
    ("barn-find", "Barn Find", "regular",
     "Sweet hay, old cedar boards and worn leather. Our tribute to Lazarus.", 8, 1, "#a3772c"),
    ("cherry-bomb", "Cherry Bomb", "regular",
     "Black cherry and almond. Loud, sweet, a little obnoxious - like a glasspack.", 8, 1, "#8f1d2c"),
    ("night-shift", "Night Shift", "regular",
     "Cool bergamot, amber and dark musk for the late-night garage sessions.", 8, 1, "#2f4a63"),
    ("starter-kit-3-pack", "Starter Kit 3-Pack", "bundle",
     "Burnt Clutch, Fresh Primer and Cherry Bomb in one bag. Three fresheners = three codes = three votes.",
     20, 3, "#d98236"),
    ("custom-car-freshie", "Custom Car Freshie", "custom",
     "Hand-cut in the shape of YOUR car, painted to match, in the scent of your choice. "
     "Describe your car when you order and we'll send a proof.", 14, 1, "#5c7a3a"),
    ("blind-bag-chase", "Blind Bag Chase", "blind",
     "Mystery scent in a sealed parts bag. About 1 in 10 is a rare chase freshener. "
     "Revealed the moment your order completes.", 6, 1, "#444038"),
]

# Shown in the "featured" row on the home page.
FEATURED_SLUGS = {"burnt-clutch", "cherry-bomb", "starter-kit-3-pack", "blind-bag-chase"}


def meet_slug(scent_name):
    """'Cold Start' -> 'meet-cold-start'."""
    return "meet-" + scent_name.lower().replace(" ", "-")


def seed_meets():
    rows = []
    for name, when, where, scent, desc, qty, sold_out, _colour in MEETS:
        m = MeetDrop(meet_name=name, meet_date=when, location=where, scent_name=scent,
                     scent_description=desc, quantity=qty, sold_out=sold_out)
        db.session.add(m)
        rows.append(m)
    db.session.flush()
    return rows


def seed_products(meets):
    rows = {}
    for i, (slug, name, kind, desc, price, per_unit, colour) in enumerate(PRODUCTS):
        p = Product(slug=slug, name=name, kind=kind, scent_description=desc, price_cents=dollars(price),
                    fresheners_per_unit=per_unit, accent_color=colour, position=i,
                    is_featured=slug in FEATURED_SLUGS)
        db.session.add(p)
        rows[slug] = p

    # One meet-exclusive product per meet drop. Past meets are sold out.
    for j, (meet, row) in enumerate(zip(meets, MEETS)):
        slug = meet_slug(meet.scent_name)
        p = Product(slug=slug, name=f"{meet.scent_name} (Meet Exclusive)", kind="meet",
                    scent_description=f"{meet.scent_description} Only made for {meet.meet_name}.",
                    price_cents=dollars(10), accent_color=row[-1], position=20 + j,
                    sold_out=meet.sold_out, meet_drop_id=meet.id)
        db.session.add(p)
        rows[slug] = p

    scents = [
        ("Shop Rag", "Clean laundry with a hint of WD-whatever.", False),
        ("Hot Brakes", "Spiced cinnamon and warm metal.", False),
        ("Detail Day", "Coconut wax and fresh microfibre.", False),
        ("Diner Coffee", "Bottomless drip coffee and pie crust.", False),
        ("Pine Pit Stop", "Classic pine, but with an attitude.", False),
        ("Gold Leaf (Chase)", "Rare! Gold-flaked freshener, honey and oud.", True),
        ("Patina (Chase)", "Rare! Hand-rusted finish, sandalwood and iron.", True),
    ]
    for name, desc, chase in scents:
        db.session.add(BlindBagScent(name=name, description=desc, is_chase=chase))
    db.session.flush()
    return rows


FIRST = ["Jake", "Maria", "Dev", "Tasha", "Luis", "Kim", "Andre", "Becca", "Omar", "Priya", "Cody", "Hana",
         "Marcus", "Jo", "Tyrell", "Sam", "Nina", "Eli", "Rosa", "Grant"]
LAST = ["Alvarez", "Brooks", "Chen", "Dubois", "Evans", "Fischer", "Garcia", "Hughes", "Ibrahim", "Jensen",
        "Kowalski", "Lopez", "Morales", "Nguyen", "Okafor", "Patel", "Reyes", "Silva", "Turner", "Walsh"]
CUSTOM_NOTES = [
    "Lifted 90s pickup, forest green, roof rack",
    "Little white hatchback with a red racing stripe",
    "Matte black wagon, steelies, slammed",
    "Two-tone blue and white van, surfboard on top",
]


def seed_orders(products, blind_scents):
    """~45 mock orders spread between March and mid-November 2026."""
    # Past meet exclusives were sold online before they sold out, so any product can appear.
    weights = {"regular": 6, "bundle": 3, "custom": 1, "blind": 3, "meet": 1}
    start = datetime(2026, 3, 10, 12, 0)
    total = 0
    all_codes = []
    for n in range(45):
        when = start + timedelta(days=n * 5.5, hours=rnd.randint(0, 10))
        first, last = rnd.choice(FIRST), rnd.choice(LAST)
        order = Order(reference=new_order_reference(), customer_name=f"{first} {last}",
                      customer_email=f"{first.lower()}.{last.lower()}@example.com",
                      total_cents=0, status="paid", payment_provider="mock",
                      payment_reference=f"mock_{n:04d}", created_at=when)
        db.session.add(order)
        lines = rnd.choice([1, 1, 1, 2, 2, 3])
        chosen = rnd.sample(list(products.values()), k=len(products))
        chosen = [p for p in chosen if rnd.random() < weights[p.kind] / 6][:lines] or [products["burnt-clutch"]]
        for product in chosen:
            qty = 1 if product.kind in ("custom", "bundle") else rnd.choice([1, 1, 2])
            item = OrderItem(product=product, product_name=product.name, unit_price_cents=product.price_cents,
                             quantity=qty,
                             custom_note=rnd.choice(CUSTOM_NOTES) if product.kind == "custom" else "")
            order.items.append(item)
            # One code per physical freshener (a 3-pack = 3 codes).
            codes = create_codes(qty * product.fresheners_per_unit, order_item=item)
            for c in codes:
                c.created_at = when
            all_codes.extend(codes)
            if product.kind == "blind":
                for _ in range(qty):
                    chase = rnd.random() < 0.1
                    pool = [s for s in blind_scents if s.is_chase == chase]
                    item.blind_results.append(BlindBagResult(scent=rnd.choice(pool)))
        order.total_cents = sum(i.unit_price_cents * i.quantity for i in order.items)
        total += order.total_cents
        db.session.flush()
        db.session.add(FundEntry(amount_cents=order.total_cents, source="order", order_id=order.id,
                                 note=f"Order {order.reference}", created_at=when))
    return total, all_codes


# --------------------------------------------------------------------------
# Voting
# --------------------------------------------------------------------------
def add_option(round_, name, desc, tiers, position):
    option = PartOption(name=name, description=desc, position=position)
    round_.options.append(option)
    for level, tier_desc, price in tiers:
        option.tiers.append(PartTier(level=level, description=tier_desc, goal_cents=dollars(price)))
    return option


def seed_votes(round_, codes, weighted_tiers, share):
    """Let a share of the given codes vote, choosing tiers by weight."""
    tiers, weights = zip(*weighted_tiers)
    for code in codes:
        if rnd.random() < share:
            tier = rnd.choices(tiers, weights=weights)[0]
            db.session.add(Vote(round=round_, tier_id=tier.id, code_id=code.id,
                                created_at=round_.opened_at + timedelta(hours=rnd.randint(1, 200))))


def seed_voting(codes):
    # Closed round: its winner is the current funding goal.
    closed = VoteRound(title="Round 6: Stopping Power",
                       description="Lazarus moves now. Stopping is another matter. What's first?",
                       status="closed", opened_at=datetime(2026, 10, 5),
                       closes_at=datetime(2026, 10, 19), closed_at=datetime(2026, 10, 19))
    db.session.add(closed)
    brakes = add_option(closed, "Brake calipers", "Front calipers are seized. Pads are fossilised.", [
        ("budget", "Remanufactured calipers + basic pads", 280),
        ("mid", "New calipers, ceramic pads, braided lines", 650),
        ("high", "Big-brake kit with slotted rotors", 1400),
    ], 0)
    susp = add_option(closed, "Suspension", "It bounces. A lot.", [
        ("budget", "Used shocks from the junkyard", 160),
        ("mid", "New gas shocks all round", 480),
        ("high", "Adjustable coilovers", 1200),
    ], 1)
    interior = add_option(closed, "Interior clean-out", "The mice left. The smell didn't.", [
        ("budget", "Deep clean and ozone treatment", 90),
        ("mid", "New carpet kit", 320),
        ("high", "Full re-trim, carpet and headliner", 950),
    ], 2)
    db.session.flush()
    early_codes = [c for c in codes if c.created_at < datetime(2026, 10, 19)]
    seed_votes(closed, early_codes, [
        (brakes.tiers[0], 14), (brakes.tiers[1], 30), (brakes.tiers[2], 9),
        (susp.tiers[0], 4), (susp.tiers[1], 9), (susp.tiers[2], 7),
        (interior.tiers[0], 6), (interior.tiers[1], 3), (interior.tiers[2], 2),
    ], share=0.55)
    winner = brakes.tiers[1]  # mid-range calipers, as weighted above
    closed.winning_tier_id = winner.id
    goal = FundingGoal(part_name=brakes.name, tier=winner.level, goal_cents=winner.goal_cents,
                       status="active", tier_id=winner.id, created_at=closed.closed_at)
    db.session.add(goal)

    # Open round: what comes after the brakes.
    current = VoteRound(title="Round 7: What's After the Brakes?",
                        description="Once Lazarus can stop, what should we fund next? One vote per freshener code.",
                        status="open", opened_at=datetime(2026, 11, 1),
                        # Relative to "now" so the countdown always has time left after seeding.
                        closes_at=(utcnow() + timedelta(days=5)).replace(minute=0, second=0, microsecond=0))
    db.session.add(current)
    seats = add_option(current, "Seats", "The driver's seat is mostly springs and regret.", [
        ("budget", "Junkyard seats, re-covered", 180),
        ("mid", "Reclaimed bucket seats", 420),
        ("high", "New sport buckets with harness bar", 900),
    ], 0)
    exhaust = add_option(current, "Exhaust", "Currently ends just behind the front seats.", [
        ("budget", "Universal muffler and pipe", 150),
        ("mid", "Stainless cat-back", 380),
        ("high", "Full stainless system, custom bent", 750),
    ], 1)
    lights = add_option(current, "Headlights", "One works. Sometimes.", [
        ("budget", "New sealed beams", 60),
        ("mid", "Glass housings with modern bulbs", 140),
        ("high", "Projector conversion", 320),
    ], 2)
    wheel = add_option(current, "Steering wheel", "Cracked, sticky and slightly chewed.", [
        ("budget", "Wheel wrap and refurb", 45),
        ("mid", "Aftermarket leather wheel", 120),
        ("high", "Quick-release wheel and hub", 280),
    ], 3)
    db.session.flush()
    seed_votes(current, codes, [
        (seats.tiers[0], 8), (seats.tiers[1], 18), (seats.tiers[2], 6),
        (exhaust.tiers[0], 5), (exhaust.tiers[1], 14), (exhaust.tiers[2], 10),
        (lights.tiers[0], 3), (lights.tiers[1], 7), (lights.tiers[2], 4),
        (wheel.tiers[0], 2), (wheel.tiers[1], 5), (wheel.tiers[2], 6),
    ], share=0.4)
    return goal


# --------------------------------------------------------------------------
# Garage
# --------------------------------------------------------------------------
def seed_garage(codes, upload_dir):
    members = [
        ("Tasha R.", "Patina Pete", "1970s pickup, original paint (what's left of it). Daily driven, never washed."),
        ("Dev C.", "The Toaster", "Boxy 90s wagon. 312k miles. Will outlive us all."),
        ("Maria G.", "Little Red", "Tiny red hatchback with a big turbo and bigger dreams."),
        ("Omar I.", "Grandpa's Sedan", "Inherited it, restored it, refuse to sell it."),
        ("Becca W.", "Swamp Thing", "Lifted 4x4 that lives in the mud. Freshener mandatory."),
        ("Luis M.", "Midnight", "Slammed coupe, black on black. Every weekend at the meet."),
        ("Kim N.", "Sunny", "Yellow convertible project. Top doesn't go up. Never will."),
        ("Jake H.", "Rust Bucket Jr.", "Inspired by Lazarus. Bought my own field find in June."),
    ]
    rows = []
    owners = rnd.sample(codes, len(members))
    for i, ((owner, car_name, desc), code) in enumerate(zip(members, owners)):
        fn = make_placeholder(upload_dir, f"garage_{i}.jpg", car_name, owner, seed=100 + i,
                              accent=rnd.choice([(194, 87, 26), (90, 110, 60), (60, 80, 110), (140, 40, 50)]))
        m = GarageMember(code_id=code.id, owner_name=owner, car_name=car_name, description=desc,
                         photo_filename=fn, created_at=datetime(2026, 6, 1) + timedelta(days=i * 17))
        db.session.add(m)
        rows.append(m)
    db.session.flush()
    db.session.add(CarOfTheMonth(member_id=rows[0].id, month="2026-11",
                                 blurb="Fifty years of sun, salt and zero fear. Pete is the soul of the Garage."))
    return [m.code_id for m in rows]


def main():
    app = create_app()
    with app.app_context():
        reset_database(app)
        upload_dir = app.config["UPLOAD_DIR"]

        seed_car(upload_dir)
        spent = seed_installs(upload_dir)
        meets = seed_meets()
        products = seed_products(meets)
        blind_scents = BlindBagScent.query.all()
        order_total, codes = seed_orders(products, blind_scents)

        # Make "money on hand" = $310 so the bar shows $340 to go on the $650 goal.
        # The difference is booked as cash sales from meet tables (admin code batches).
        target_raised = spent + dollars(310)
        cash = target_raised - order_total
        db.session.add(FundEntry(amount_cents=cash, source="manual",
                                 note="Cash sales at meets, March to October", created_at=datetime(2026, 10, 31)))

        batch = CodeBatch(label="Harvest Hoods Meet table stock", created_at=datetime(2026, 10, 9))
        db.session.add(batch)
        batch_codes = create_codes(20, batch=batch)
        db.session.flush()

        seed_voting(codes + batch_codes[:10])
        garage_code_ids = seed_garage(codes, upload_dir)
        db.session.commit()

        # ---- Print a summary and some codes to try ----
        voted_ids = {v.code_id for v in Vote.query.join(VoteRound).filter(VoteRound.status == "open")}
        fresh = [c for c in FreshenerCode.query.all() if c.id not in voted_ids and c.id not in garage_code_ids]
        print("Done!")
        print(f"  Orders: {Order.query.count()}  Codes: {FreshenerCode.query.count()}  "
              f"Votes: {Vote.query.count()}  Garage members: {GarageMember.query.count()}")
        print(f"  Raised: ${target_raised / 100:,.2f}  Spent: ${spent / 100:,.2f}  "
              f"On hand: ${(target_raised - spent) / 100:,.2f}")
        print("\nUnused codes to try (no vote this round, no Garage profile):")
        for c in fresh[:5]:
            print("   ", format_code(c.code))


if __name__ == "__main__":
    main()
