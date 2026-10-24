"""Generate fake, HubSpot-shaped CRM exports and a billing export, with known planted defects.

Everything here is fictional. The generator first builds a CLEAN data set (no check should
fire on it), then plants a fixed number of defects on records that haven't been touched
yet, and writes every planted defect to data/defects_manifest.json. The tests use that
manifest to prove the checks find exactly what was planted.
"""

import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from chc.db import SCHEMA, write_csv

# ---------------------------------------------------------------------------------------
# Fixed vocabulary for the fake data
# ---------------------------------------------------------------------------------------

OWNERS = [
    ("OWN-01", "Maya Chen", "SMB", True),
    ("OWN-02", "Jordan Price", "SMB", True),
    ("OWN-03", "Leo Alvarez", "SMB", True),
    ("OWN-04", "Priya Nair", "SMB", True),
    ("OWN-05", "Elena Park", "Mid-Market", True),
    ("OWN-06", "Marcus Webb", "Mid-Market", True),
    ("OWN-07", "Hannah Cole", "Mid-Market", True),
    ("OWN-08", "Diego Romero", "Partners", True),
    ("OWN-09", "Tessa Lund", "Partners", True),
    ("OWN-10", "Rachel Stone", "SMB", False),  # left the company
    ("OWN-11", "Victor Hale", "Mid-Market", False),  # left the company
]

NAME_PREFIXES = [
    "Harbor",
    "Maple",
    "Copper",
    "Tidal",
    "Willow",
    "Ember",
    "Summit",
    "Lumen",
    "Cedar",
    "Saffron",
    "Indigo",
    "Pebble",
    "Bramble",
    "Marigold",
    "Orchard",
    "Driftwood",
    "Sable",
    "Wren",
    "Clover",
    "Basil",
    "Quarry",
    "Fable",
    "Hearth",
    "Northbeam",
    "Larkspur",
    "Kestrel",
    "Moonrise",
    "Riverstone",
    "Goldfinch",
    "Thistle",
    "Alder",
    "Brightwater",
]

# industry -> words used to finish a company name
INDUSTRIES = {
    "Apparel": ["Threads", "Outfitters", "Apparel", "Supply Co."],
    "Home goods": ["Home", "Living", "Goods"],
    "Beauty": ["Beauty", "Botanicals", "Skin"],
    "Outdoor gear": ["Outdoors", "Gear", "Trail Co."],
    "Food & beverage": ["Coffee Co.", "Pantry", "Provisions"],
    "Pet supplies": ["Pet Co.", "Paws", "Pet Supply"],
}

FIRST_NAMES = [
    "Ana",
    "Ben",
    "Chloe",
    "Dev",
    "Erin",
    "Felix",
    "Grace",
    "Hugo",
    "Iris",
    "Jon",
    "Kai",
    "Lena",
    "Mateo",
    "Nora",
    "Omar",
    "Paula",
    "Quinn",
    "Rosa",
    "Sean",
    "Tara",
    "Uma",
    "Vince",
    "Wendy",
    "Xavi",
    "Yara",
    "Zane",
    "Alma",
    "Bruno",
    "Carla",
    "Dario",
    "Elsa",
    "Gabe",
]
LAST_NAMES = [
    "Ruiz",
    "Kim",
    "Patel",
    "Novak",
    "Silva",
    "Moreau",
    "Okafor",
    "Lindqvist",
    "Haddad",
    "Tanaka",
    "Byrne",
    "Costa",
    "Fischer",
    "Mendez",
    "Osei",
    "Varga",
    "Walsh",
    "Yilmaz",
    "Abbott",
    "Duarte",
    "Ferreira",
    "Gallo",
    "Ibarra",
    "Jensen",
]

# Plans: monthly list price per storefront. Mid-Market buys bigger plans.
PLANS = {"Launch": 199, "Growth": 499, "Scale": 1200}
TEAM_PLANS = {
    "SMB": ["Launch", "Growth"],
    "Mid-Market": ["Growth", "Scale"],
    "Partners": ["Launch", "Growth", "Scale"],
}

# HubSpot "original source" -> the canonical UTM pair a clean contact carries.
SOURCE_UTMS = {
    "PAID_SEARCH": [("google", "cpc"), ("bing", "cpc")],
    "PAID_SOCIAL": [("facebook", "paid_social"), ("linkedin", "paid_social")],
    "EMAIL_MARKETING": [("newsletter", "email")],
    "REFERRALS": [("partner", "referral")],
    "OFFLINE": [("webinar", "event")],
    "ORGANIC_SEARCH": [(None, None)],
    "DIRECT_TRAFFIC": [(None, None)],
}
CAMPAIGNS = [
    "q1-affiliate-launch",
    "creator-program-webinar",
    "spring-ecom-guide",
    "partner-roi-calculator",
    "holiday-readiness",
]
CHANNEL_FOR_SOURCE = {
    "PAID_SEARCH": "paid_search",
    "PAID_SOCIAL": "paid_social",
    "EMAIL_MARKETING": "email",
    "REFERRALS": "referral",
    "OFFLINE": "event",
    "ORGANIC_SEARCH": "organic_search",
    "DIRECT_TRAFFIC": "direct",
}

# Messy spellings people type into UTM tags; used for planted H09 defects and touchpoints.
MESSY_SOURCES = {
    "google": ["Google", "google.com", "adwords"],
    "bing": ["Bing", "bing.com"],
    "facebook": ["FB", "facebook.com", "Facebook"],
    "linkedin": ["LinkedIn", "linkedin.com", "lnkd"],
    "newsletter": ["Newsletter", "mailchimp"],
    "partner": ["Partners", "referral-partner"],
    "webinar": ["Webinar"],
}
MESSY_MEDIUMS = {
    "cpc": ["CPC", "ppc"],
    "paid_social": ["paidsocial", "Paid-Social"],
    "email": ["e-mail", "Email"],
    "referral": ["ref"],
    "event": ["Event"],
}
UNKNOWN_SOURCES = ["tiktok-test", "summer_launch", "influencer_x", "qr-code"]

OPEN_STAGES = [
    "appointmentscheduled",
    "qualifiedtobuy",
    "presentationscheduled",
    "decisionmakerboughtin",
    "contractsent",
]
OPEN_STAGE_WEIGHTS = [30, 25, 20, 15, 10]

# How many of each defect to plant. Kept small so every one can be checked by hand.
DEFECT_COUNTS = {
    "H01": 12,
    "H02": 6,
    "H03_missing": 4,
    "H03_invalid": 6,
    "H04_missing": 5,
    "H04_customer": 5,
    "H05_company": 4,
    "H05_contact": 4,
    "H06_close": 5,
    "H06_idle": 5,
    "H07": 3,  # per missing field (amount, close_date, term_months)
    "H08_contact": 3,
    "H08_deal_inactive": 2,
    "H08_deal_none": 2,
    "H08_company": 2,
    "H09_alias": 8,
    "H09_unknown": 4,
}


# ---------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------


def at(day: date, rng: random.Random) -> datetime:
    """Turn a date into a datetime during business hours, so timestamps look real."""
    return datetime.combine(day, time(rng.randint(8, 17), rng.choice([0, 15, 30, 45])))


def slug(text: str) -> str:
    """Make a domain-safe slug: "Copper Coffee Co." -> "coppercoffeeco"."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def pick_clean(
    rng: random.Random,
    pool: list[dict],
    key: str,
    used: set,
    count: int,
    condition=lambda record: True,
) -> list[dict]:
    """Pick `count` records that no other defect has touched yet, and mark them used."""
    candidates = [r for r in pool if r[key] not in used and condition(r)]
    chosen = rng.sample(candidates, count)
    used.update(r[key] for r in chosen)
    return chosen


# ---------------------------------------------------------------------------------------
# Clean data
# ---------------------------------------------------------------------------------------


def build_owners() -> list[dict]:
    """The sales team: nine active reps across three teams, plus two who left."""
    return [{"owner_id": o, "name": n, "team": t, "active": a} for o, n, t, a in OWNERS]


def build_companies(rng: random.Random, as_of: date, count: int) -> list[dict]:
    """Fictional online brands. Keys starting with "_" are generator-only and not exported."""
    active_by_team: dict[str, list[str]] = {}
    for owner_id, _name, team, active in OWNERS:
        if active:
            active_by_team.setdefault(team, []).append(owner_id)

    names = [
        (p, industry, word)
        for p in NAME_PREFIXES
        for industry, words in INDUSTRIES.items()
        for word in words
    ]
    rng.shuffle(names)
    companies = []
    for number, (prefix, industry, word) in enumerate(names[:count], start=1):
        name = f"{prefix} {word}"
        team = rng.choices(["SMB", "Mid-Market", "Partners"], weights=[60, 25, 15])[0]
        plan = rng.choice(TEAM_PLANS[team])
        companies.append(
            {
                "company_id": f"CO-{number:04d}",
                "name": name,
                "domain": f"{slug(name)}.example",
                "industry": industry,
                "team": team,
                "owner_id": rng.choice(active_by_team[team]),
                "created_at": at(as_of - timedelta(days=rng.randint(700, 1100)), rng),
                "_currency": rng.choices(["USD", "CAD", "EUR"], weights=[80, 12, 8])[0],
                "_plan": plan,
                "_monthly_price": PLANS[plan] * rng.randint(1, 3),  # 1-3 storefronts
            }
        )
    return companies


def build_contacts(rng: random.Random, companies: list[dict]) -> list[dict]:
    """Two to six contacts per company, each with a unique name and a valid work email."""
    contacts = []
    for company in companies:
        people = rng.sample([(f, la) for f in FIRST_NAMES for la in LAST_NAMES], rng.randint(2, 6))
        for first, last in people:
            source = rng.choice(list(SOURCE_UTMS))
            utm_source, utm_medium = rng.choice(SOURCE_UTMS[source])
            contacts.append(
                {
                    "contact_id": f"CT-{len(contacts) + 1:05d}",
                    "first_name": first,
                    "last_name": last,
                    "email": f"{first.lower()}.{last.lower()}@{company['domain']}",
                    "company_id": company["company_id"],
                    "lifecycle_stage": None,  # set after deals exist
                    "owner_id": company["owner_id"],
                    "created_at": company["created_at"] + timedelta(days=rng.randint(0, 60)),
                    "original_source": source,
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "utm_campaign": rng.choice(CAMPAIGNS) if utm_source else None,
                }
            )
    return contacts


def stage_path(rng: random.Random, final_stage: str) -> list[str]:
    """The stages a deal moved through to reach its final stage, in order."""
    if final_stage == "closedwon":
        return OPEN_STAGES + ["closedwon"]
    if final_stage == "closedlost":
        return OPEN_STAGES[: rng.randint(1, len(OPEN_STAGES))] + ["closedlost"]
    return OPEN_STAGES[: OPEN_STAGES.index(final_stage) + 1]


def build_deal(rng, number, company, contacts, final_stage, last_change, close_date):
    """One deal plus its stage history, working backwards from the last stage change."""
    path = stage_path(rng, final_stage)
    gaps = [timedelta(days=rng.randint(3, 21), hours=rng.randint(0, 8)) for _ in path[1:]]
    times = [last_change]
    for gap in reversed(gaps):
        times.insert(0, times[0] - gap)
    deal_id = f"DL-{number:04d}"
    history = [
        {
            "deal_id": deal_id,
            "from_stage": path[i - 1] if i else None,
            "to_stage": stage,
            "changed_at": times[i],
        }
        for i, stage in enumerate(path)
    ]
    term = rng.choice([12, 12, 12, 24, 36])
    annual = company["_monthly_price"] * 12
    deal = {
        "deal_id": deal_id,
        "name": f"{company['name']} - {company['_plan']} plan",
        "company_id": company["company_id"],
        "primary_contact_id": rng.choice(contacts)["contact_id"],
        "owner_id": company["owner_id"],
        "pipeline": "default",
        "stage": final_stage,
        "amount": float(annual * term // 12),  # total contract value for the term
        "currency": company["_currency"],
        "term_months": term,
        "close_date": close_date,
        "created_at": times[0],
        "last_stage_change_at": times[-1],
    }
    return deal, history


def build_deals(rng: random.Random, companies: list[dict], contacts: list[dict], as_of: date):
    """150 won, 70 lost and about 280 open deals; every open deal is fresh (not stale)."""
    contacts_by_company: dict[str, list[dict]] = {}
    for contact in contacts:
        contacts_by_company.setdefault(contact["company_id"], []).append(contact)

    order = companies[:]
    rng.shuffle(order)
    plan = [(c, "closedwon") for c in order[:150]] + [(c, "closedlost") for c in order[150:220]]
    for _ in range(280):
        stage = rng.choices(OPEN_STAGES, weights=OPEN_STAGE_WEIGHTS)[0]
        plan.append((rng.choice(order[100:]), stage))

    deals, history = [], []
    for number, (company, stage) in enumerate(plan, start=1):
        if stage in ("closedwon", "closedlost"):
            closed_on = as_of - timedelta(days=rng.randint(5, 420))
            last_change, close_date = at(closed_on, rng), closed_on
        else:
            last_change = at(as_of - timedelta(days=rng.randint(1, 25)), rng)
            close_date = as_of + timedelta(days=rng.randint(10, 120))
        deal, rows = build_deal(
            rng,
            number,
            company,
            contacts_by_company[company["company_id"]],
            stage,
            last_change,
            close_date,
        )
        deals.append(deal)
        history.extend(rows)
    return deals, history


def set_lifecycle_stages(rng: random.Random, contacts: list[dict], deals: list[dict]) -> None:
    """Clean lifecycle rule: won deal -> customer, open deal -> opportunity, else a lead stage."""
    won = {d["company_id"] for d in deals if d["stage"] == "closedwon"}
    open_ = {d["company_id"] for d in deals if d["stage"] in OPEN_STAGES}
    for contact in contacts:
        if contact["company_id"] in won:
            contact["lifecycle_stage"] = "customer"
        elif contact["company_id"] in open_:
            contact["lifecycle_stage"] = "opportunity"
        else:
            contact["lifecycle_stage"] = rng.choice(
                ["subscriber", "lead", "marketingqualifiedlead"]
            )


def messy_domain(rng: random.Random, domain: str) -> str:
    """How a billing system often stores a domain: with https://, www., capitals or a slash."""
    return rng.choice([f"https://www.{domain}/", domain.upper(), f"www.{domain}", f"{domain}/"])


def build_billing(rng: random.Random, companies: list[dict], deals: list[dict]) -> list[dict]:
    """One active subscription per won deal, priced to match the CRM exactly (clean data)."""
    by_id = {c["company_id"]: c for c in companies}
    subscriptions = []
    for deal in deals:
        if deal["stage"] != "closedwon":
            continue
        company = by_id[deal["company_id"]]
        monthly = rng.random() < 0.6
        number = len(subscriptions) + 1
        domain = company["domain"]
        subscriptions.append(
            {
                "subscription_id": f"sub_{number:04d}",
                "billing_customer_id": f"cus_{number:04d}",
                "company_domain": messy_domain(rng, domain) if rng.random() < 0.2 else domain,
                "plan": company["_plan"],
                # Price per billing interval (Stripe-style), in a column the export calls "mrr".
                "mrr": float(company["_monthly_price"] * (1 if monthly else 12)),
                "currency": company["_currency"],
                "interval": "month" if monthly else "year",
                "status": "active",
                "started_at": deal["close_date"],
                "canceled_at": None,
                "_deal_id": deal["deal_id"],
            }
        )
    return subscriptions


def build_touchpoints(rng, contacts, deals, as_of):
    """Marketing touches. Primary contacts of won deals get 1-4 touches before the deal opened.

    About a quarter of touches carry messy UTM spellings, the way real tracking data does,
    so the attribution page can show the before/after effect of UTM normalization.
    """
    won_contact_start = {
        d["primary_contact_id"]: d["created_at"] for d in deals if d["stage"] == "closedwon"
    }
    touchpoints = []
    for contact in contacts:
        deal_start = won_contact_start.get(contact["contact_id"])
        count = rng.randint(1, 4) if deal_start else rng.randint(0, 2)
        latest = deal_start or at(as_of, rng)
        for _ in range(count):
            source = rng.choice(list(SOURCE_UTMS))
            utm_source, utm_medium = rng.choice(SOURCE_UTMS[source])
            roll = rng.random()
            if utm_source and roll < 0.25:
                utm_source = rng.choice(MESSY_SOURCES[utm_source])
            elif utm_source and roll < 0.28:
                utm_source = rng.choice(UNKNOWN_SOURCES)
            touchpoints.append(
                {
                    "touchpoint_id": f"TP-{len(touchpoints) + 1:05d}",
                    "contact_id": contact["contact_id"],
                    "occurred_at": latest
                    - timedelta(days=rng.randint(1, 90), hours=rng.randint(0, 9)),
                    "channel": CHANNEL_FOR_SOURCE[source],
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "utm_campaign": rng.choice(CAMPAIGNS) if utm_source else None,
                }
            )
    return touchpoints


# ---------------------------------------------------------------------------------------
# Planted defects
# ---------------------------------------------------------------------------------------


def plant_hygiene_defects(rng, data, as_of) -> list[dict]:
    """Break specific clean records so each check H01-H09 has known positives."""
    contacts, companies, deals = data["contacts"], data["companies"], data["deals"]
    history = data["deal_stage_history"]
    used_contacts, used_deals, used_companies = set(), set(), set()
    defects = []
    n = DEFECT_COUNTS

    def record(check_id, record_id, description):
        defects.append({"check_id": check_id, "record_id": record_id, "description": description})

    # H01: copy a contact with a different spelling of the same email.
    for original in pick_clean(rng, contacts, "contact_id", used_contacts, n["H01"]):
        local, domain = original["email"].split("@")
        variant = rng.choice(
            [original["email"].upper(), f"{local}+promo@{domain}", f"{local.title()}@{domain}"]
        )
        duplicate = {
            **original,
            "contact_id": f"CT-{len(contacts) + 1:05d}",
            "email": variant,
            "created_at": original["created_at"] + timedelta(days=rng.randint(30, 300)),
        }
        contacts.append(duplicate)
        used_contacts.add(duplicate["contact_id"])
        record("H01", duplicate["contact_id"], f"duplicate of {original['contact_id']}")

    # H02: copy a company with a differently formatted domain (no contacts or deals).
    for original in pick_clean(rng, companies, "company_id", used_companies, n["H02"]):
        duplicate = {
            **original,
            "company_id": f"CO-{len(companies) + 1:04d}",
            "name": original["name"] + rng.choice(["", " Inc.", " LLC"]),
            "domain": messy_domain(rng, original["domain"]),
            "created_at": original["created_at"] + timedelta(days=rng.randint(30, 300)),
        }
        companies.append(duplicate)
        record("H02", duplicate["company_id"], f"duplicate of {original['company_id']}")

    # H03: blank and malformed emails.
    for contact in pick_clean(rng, contacts, "contact_id", used_contacts, n["H03_missing"]):
        contact["email"] = None
        record("H03", contact["contact_id"], "email missing")
    for contact in pick_clean(rng, contacts, "contact_id", used_contacts, n["H03_invalid"]):
        local, domain = contact["email"].split("@")
        contact["email"] = rng.choice(
            [
                f"{local}@",
                f"{local}.{domain}",
                f"{local}@@{domain}",
                f"{local}@{domain.split('.')[0]}",
                f"{contact['first_name']} {contact['last_name']}@{domain}",
            ]
        )
        record("H03", contact["contact_id"], "email malformed")

    # H04: blank lifecycle stage, and "customer" at a company with no won deal.
    won_companies = {d["company_id"] for d in deals if d["stage"] == "closedwon"}
    for contact in pick_clean(rng, contacts, "contact_id", used_contacts, n["H04_missing"]):
        contact["lifecycle_stage"] = None
        record("H04", contact["contact_id"], "lifecycle stage missing")
    for contact in pick_clean(
        rng,
        contacts,
        "contact_id",
        used_contacts,
        n["H04_customer"],
        lambda c: c["company_id"] not in won_companies,
    ):
        contact["lifecycle_stage"] = "customer"
        record("H04", contact["contact_id"], "customer with no closed-won deal")

    # H06 first, so H05 picks from deals that are still fresh.
    open_deals = [d for d in deals if d["stage"] in OPEN_STAGES]
    for deal in pick_clean(rng, open_deals, "deal_id", used_deals, n["H06_close"]):
        deal["close_date"] = as_of - timedelta(days=rng.randint(3, 60))
        record("H06", deal["deal_id"], "close date in the past")
    for deal in pick_clean(rng, open_deals, "deal_id", used_deals, n["H06_idle"]):
        shift = timedelta(days=rng.randint(45, 120))
        for row in history:
            if row["deal_id"] == deal["deal_id"]:
                row["changed_at"] -= shift
        deal["created_at"] -= shift
        deal["last_stage_change_at"] -= shift
        record("H06", deal["deal_id"], "no stage change in over 30 days")

    # H05: remove associations (only on open/lost deals, so won revenue stays attached).
    not_won = [d for d in deals if d["stage"] != "closedwon"]
    for deal in pick_clean(rng, open_deals, "deal_id", used_deals, n["H05_company"]):
        deal["company_id"] = None
        record("H05", deal["deal_id"], "no company association")
    for deal in pick_clean(rng, not_won, "deal_id", used_deals, n["H05_contact"]):
        deal["primary_contact_id"] = None
        record("H05", deal["deal_id"], "no primary contact")

    # H07: closed-won deals missing amount, close date or term (term only on 12-month deals,
    # because a missing term is read as 12 months, so ARR still matches billing).
    won = [d for d in deals if d["stage"] == "closedwon" and d["deal_id"] not in data["_recon"]]
    for field in ("amount", "close_date", "term_months"):
        condition = (
            (lambda d: d["term_months"] == 12) if field == "term_months" else (lambda d: True)
        )
        for deal in pick_clean(rng, won, "deal_id", used_deals, n["H07"], condition):
            deal[field] = None
            record("H07", deal["deal_id"], f"closed-won deal missing {field}")
            if field == "amount":
                data["_recon_expected_extra"].append(deal["deal_id"])

    # H08: records owned by someone who left, or by nobody.
    inactive = [o["owner_id"] for o in data["owners"] if not o["active"]]
    for contact in pick_clean(rng, contacts, "contact_id", used_contacts, n["H08_contact"]):
        contact["owner_id"] = rng.choice(inactive)
        record("H08", contact["contact_id"], "contact owned by inactive owner")
    for deal in pick_clean(rng, deals, "deal_id", used_deals, n["H08_deal_inactive"]):
        deal["owner_id"] = rng.choice(inactive)
        record("H08", deal["deal_id"], "deal owned by inactive owner")
    for deal in pick_clean(rng, deals, "deal_id", used_deals, n["H08_deal_none"]):
        deal["owner_id"] = None
        record("H08", deal["deal_id"], "deal has no owner")
    for company in pick_clean(rng, companies, "company_id", used_companies, n["H08_company"]):
        company["owner_id"] = rng.choice(inactive)
        record("H08", company["company_id"], "company owned by inactive owner")

    # H09: known aliases (auto-fixable) and unknown values (needs review).
    tagged = [c for c in contacts if c["utm_source"]]
    for contact in pick_clean(rng, tagged, "contact_id", used_contacts, n["H09_alias"]):
        if rng.random() < 0.6:
            contact["utm_source"] = rng.choice(MESSY_SOURCES[contact["utm_source"]])
        else:
            contact["utm_medium"] = rng.choice(MESSY_MEDIUMS[contact["utm_medium"]])
        record("H09", contact["contact_id"], "UTM alias instead of canonical value")
    for contact in pick_clean(rng, tagged, "contact_id", used_contacts, n["H09_unknown"]):
        contact["utm_source"] = rng.choice(UNKNOWN_SOURCES)
        record("H09", contact["contact_id"], "unknown UTM source")

    return defects


def plant_recon_defects(rng, data, as_of) -> None:
    """Break the CRM/billing match for specific accounts, one per reconciliation category.

    Records the expected status per normalized domain in data["_recon_expected"].
    """
    companies = {c["company_id"]: c for c in data["companies"]}
    subs = data["billing_subscriptions"]
    sub_by_deal = {s["_deal_id"]: s for s in subs}
    won = [d for d in data["deals"] if d["stage"] == "closedwon"]
    chosen = rng.sample(won, 17)
    data["_recon"].update(d["deal_id"] for d in chosen)
    expected = data["_recon_expected"]

    def expect(deal, status, description):
        expected.append(
            {
                "domain": companies[deal["company_id"]]["domain"],
                "expected_status": status,
                "description": description,
            }
        )

    # CRM-only: billing has no active subscription.
    for deal in chosen[0:2]:
        subs.remove(sub_by_deal[deal["deal_id"]])
        expect(deal, "CRM-only", "no billing subscription")
    canceled = sub_by_deal[chosen[2]["deal_id"]]
    canceled["status"] = "canceled"
    canceled["canceled_at"] = as_of - timedelta(days=20)
    expect(chosen[2], "CRM-only", "subscription canceled in billing")

    # Amount mismatch: billing price differs (discount or extra storefront).
    for deal, factor in zip(chosen[3:7], [0.85, 0.9, 1.25, 1.5], strict=True):
        sub = sub_by_deal[deal["deal_id"]]
        sub["mrr"] = round(sub["mrr"] * factor, 2)
        expect(deal, "Amount mismatch", f"billing price x{factor}")

    # Term mismatch, CRM side: the monthly price was typed in as the contract amount.
    for deal in chosen[7:9]:
        deal["amount"] = float(companies[deal["company_id"]]["_monthly_price"])
        deal["term_months"] = 12
        expect(deal, "Term mismatch", "monthly price entered as deal amount")
    # Term mismatch, billing side: yearly interval but a monthly price.
    for deal in chosen[9:11]:
        sub = sub_by_deal[deal["deal_id"]]
        sub["mrr"] = float(companies[deal["company_id"]]["_monthly_price"])
        sub["interval"] = "year"
        expect(deal, "Term mismatch", "yearly plan billed at the monthly price")

    # Currency mismatch: billing charges a different currency than the deal.
    for deal in chosen[11:14]:
        sub = sub_by_deal[deal["deal_id"]]
        sub["currency"] = "CAD" if deal["currency"] == "USD" else "USD"
        expect(deal, "Currency mismatch", f"deal {deal['currency']}, billing {sub['currency']}")

    # Billing-only: active subscriptions with no closed-won deal in CRM.
    lost_company = companies[
        next(d["company_id"] for d in data["deals"] if d["stage"] == "closedlost")
    ]
    new_domains = ["self-serve-brand-one.example", "popupshop-two.example"]
    for number, domain in enumerate([lost_company["domain"], *new_domains], start=1):
        subs.append(
            {
                "subscription_id": f"sub_9{number:03d}",
                "billing_customer_id": f"cus_9{number:03d}",
                "company_domain": domain,
                "plan": "Launch",
                "mrr": 199.0,
                "currency": "USD",
                "interval": "month",
                "status": "active",
                "started_at": as_of - timedelta(days=60),
                "canceled_at": None,
                "_deal_id": None,
            }
        )
        expected.append(
            {
                "domain": domain,
                "expected_status": "Billing-only",
                "description": "active subscription with no closed-won deal",
            }
        )
    # chosen[14:17] stay clean on purpose: spare matched accounts.


# ---------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------


def generate(seed: int, out_dir: Path, settings: dict) -> dict:
    """Build the clean data, plant defects, write the CSVs + manifest, and return the manifest."""
    rng = random.Random(seed)
    as_of = settings["params"]["as_of"]
    owners = build_owners()
    companies = build_companies(rng, as_of, count=300)
    contacts = build_contacts(rng, companies)
    deals, history = build_deals(rng, companies, contacts, as_of)
    set_lifecycle_stages(rng, contacts, deals)
    data = {
        "owners": owners,
        "companies": companies,
        "contacts": contacts,
        "deals": deals,
        "deal_stage_history": history,
        "touchpoints": build_touchpoints(rng, contacts, deals, as_of),
        "billing_subscriptions": build_billing(rng, companies, deals),
        "_recon": set(),
        "_recon_expected": [],
        "_recon_expected_extra": [],
    }
    plant_recon_defects(rng, data, as_of)
    defects = plant_hygiene_defects(rng, data, as_of)

    # Won deals that lost their amount (H07) also show up as Amount mismatch in recon.
    by_id = {c["company_id"]: c for c in companies}
    for deal in deals:
        if deal["deal_id"] in data["_recon_expected_extra"]:
            data["_recon_expected"].append(
                {
                    "domain": by_id[deal["company_id"]]["domain"],
                    "expected_status": "Amount mismatch",
                    "description": "closed-won deal missing amount (H07)",
                }
            )

    out_dir = Path(out_dir)
    for table, columns in SCHEMA.items():
        write_csv(out_dir / f"{table}.csv", [to_csv_row(r) for r in data[table]], list(columns))

    manifest = {
        "company": settings["report"]["company_name"],
        "seed": seed,
        "as_of": as_of.isoformat(),
        "note": "Fictional company and generated data. Every planted defect is listed here.",
        "defects": sorted(defects, key=lambda d: (d["check_id"], d["record_id"])),
        "reconciliation": sorted(data["_recon_expected"], key=lambda r: r["domain"]),
    }
    (out_dir / "defects_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def to_csv_row(row: dict) -> dict:
    """Format one record for CSV: ISO dates and times, lowercase booleans."""
    formatted = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            value = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, bool):
            value = "true" if value else "false"
        formatted[key] = value
    return formatted
