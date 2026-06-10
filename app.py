import csv
import io
import os
import re
import threading
import time
import urllib.error
import urllib.request

from flask import Flask, abort, jsonify, render_template, request

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


SHEET_ID = "1oqpw6UxU6jltQnBjiTzvUhaYnFmaCR_-gxUhUXAB5IQ"
SHEET_GID = "817605414"
SHEET_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={SHEET_GID}"
)
BUNDLED_CSV = os.path.join(BASE_DIR, "PHS Clubs 2025-26 - 2024-25.csv")
CACHE_CSV = os.path.join(BASE_DIR, "clubs_cache.csv")
CACHE_TTL_SECONDS = int(os.environ.get("PHSCLUBS_CACHE_TTL", "600"))
REFRESH_TOKEN = os.environ.get("PHSCLUBS_REFRESH_TOKEN", "")
FETCH_TIMEOUT = 15


CATEGORY_ICONS = {
    "Academic Competitions": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "Advocacy & Politics": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "Arts & Creative Writing": '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
    "Business & Finance": '<line x1="12" y1="2" x2="12" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "Community Service": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z"/>',
    "Culture & Identity": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "Dance & Theater": '<path d="M9 11H7a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2"/><path d="M15 11h2a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-2"/><path d="M5 18a7 7 0 1 1 14 0"/><circle cx="9" cy="14" r="1" fill="currentColor"/><circle cx="15" cy="14" r="1" fill="currentColor"/>',
    "Environment & Nature": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/>',
    "Games & Strategy": '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.2" fill="currentColor"/><circle cx="16" cy="8" r="1.2" fill="currentColor"/><circle cx="8" cy="16" r="1.2" fill="currentColor"/><circle cx="16" cy="16" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/>',
    "Health & Wellness": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "Honor Societies": '<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>',
    "Media & Leadership": '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>',
    "Music & Performance": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "Sports & Education": '<circle cx="12" cy="12" r="10"/><path d="M4.93 4.93 19.07 19.07"/><path d="M14.83 14.83 19.07 4.93"/><path d="M9.17 9.17 4.93 19.07"/>',
    "Sports & Recreation": '<circle cx="12" cy="12" r="10"/><path d="M4.93 4.93 19.07 19.07"/><path d="M14.83 14.83 19.07 4.93"/><path d="M9.17 9.17 4.93 19.07"/>',
    "STEM & Education": '<path d="M10 2v7.31"/><path d="M14 9.3V1.99"/><path d="M8.5 2h7"/><path d="M14 9.3a6.5 6.5 0 1 1-4 0"/>',
    "Technology & Engineering": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="2" x2="9" y2="4"/><line x1="15" y1="2" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="22"/><line x1="15" y1="20" x2="15" y2="22"/><line x1="20" y1="9" x2="22" y2="9"/><line x1="20" y1="15" x2="22" y2="15"/><line x1="2" y1="9" x2="4" y2="9"/><line x1="2" y1="15" x2="4" y2="15"/>',
}

DEFAULT_ICON = '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'


RESOURCE_LINKS = [
    {
        "label": "Start a new Club",
        "url": "https://docs.google.com/forms/d/e/1FAIpQLSf2r7XdY2sVdzbxxDFTzxqFxOvhhNxSgZQPnRgdQ8_dLGgvxw/viewform",
    },
    {
        "label": "Join an existing Club",
        "url": "https://docs.google.com/forms/d/e/1FAIpQLSdI9s9OVqN5O11VDDNfdEMPwwspOeO2TxcoRnq2vuAgm8cP_A/viewform",
    },
    {
        "label": "Alphabetized list of Clubs",
        "url": "https://docs.google.com/spreadsheets/d/1oqpw6UxU6jltQnBjiTzvUhaYnFmaCR_-gxUhUXAB5IQ/edit?usp=sharing",
    },
    {
        "label": "Approval Process for Guests",
        "url": "https://docs.google.com/document/d/1MYz6xlP6A6s3aDTIylwr-Y-W6GiLn5gjmUYcjJIyW4g/edit?usp=sharing",
    },
    {
        "label": "Approval Process for Announcements",
        "url": "https://docs.google.com/document/d/16eEMVkf2XKNkZIFFoQ2I6gIT0ZO3c5iZNRr0SyyUk4w/edit?usp=sharing",
    },
]


SGA_INFO = {
    "name": "Student Government Association",
    "description": (
        "The Student Government Association (SGA) represents the student body, plans "
        "school-wide events, and serves as a link between students and administration. "
        "All Falcons are welcome to attend meetings and get involved."
    ),
    "external_url": "https://www.montgomeryschoolsmd.org/schools/poolesvillehs/clubs/sga/",
}
CLASSES_EXTERNAL_URL = "https://www.montgomeryschoolsmd.org/schools/poolesvillehs/clubs/classes/"


def categorize_club(name, description):
    """Categorize a club based on its name and description."""
    name_lower = name.lower()
    desc_lower = description.lower() if description else ""

    overrides = {
        "book club": "Arts & Creative Writing",
        "falcon film club": "Arts & Creative Writing",
        "photography club": "Arts & Creative Writing",
        "animation/digital art club": "Arts & Creative Writing",
        "phs literary magazine club": "Arts & Creative Writing",
        "creative writing": "Arts & Creative Writing",
        "spoken word & poetry club": "Arts & Creative Writing",
        "falcon media club": "Media & Leadership",
        "phs av": "Media & Leadership",
        "falcon ambassadors": "Media & Leadership",
        "poolesville sportsweb": "Media & Leadership",
        "tedxphs": "Media & Leadership",
        "model un": "Academic Competitions",
        "neuroscience club": "Academic Competitions",
        "mesa jhu apl": "Academic Competitions",
        "poolesville philosophy club": "Academic Competitions",
        "history club": "Academic Competitions",
        "chesapeake bay coalition": "Environment & Nature",
        "poolesville green works": "Environment & Nature",
        "treeplenish": "Environment & Nature",
        "roots and shoots": "Environment & Nature",
        "poolesville ecoimpact": "Community Service",
        "kindco.": "Community Service",
        "so do we poolesville": "Community Service",
        "hero": "Community Service",
        "medlife phs": "Community Service",
        "red cross": "Community Service",
        "poolesville american cancer society": "Community Service",
        "project unity poolesville chapter": "Community Service",
        "poolesville meteorology club": "STEM & Education",
        "conrad challenge club": "STEM & Education",
        "young researchers club": "STEM & Education",
        "phs mind boosters": "STEM & Education",
        "moco cap student advisory council": "STEM & Education",
        "holidays club": "Culture & Identity",
        "muslim students association": "Culture & Identity",
        "minority scholars program": "Culture & Identity",
        "moco empowher": "Advocacy & Politics",
        "young democrats of america": "Advocacy & Politics",
        "students fair (for asylum and immigration reform)": "Advocacy & Politics",
        "phs fishing club": "Sports & Recreation",
        "fashion skate club (skatewalk society)": "Sports & Recreation",
        "super smash bros club": "Games & Strategy",
        "esports club": "Games & Strategy",
        "intro to godot engine": "Games & Strategy",
        "mind4youth": "Health & Wellness",
        "allergy awareness club": "Health & Wellness",
        "michael jackson club": "Music & Performance",
        "black & gold club": "Technology & Engineering",
    }

    for key, cat in overrides.items():
        if key in name_lower:
            return cat

    if any(kw in name_lower for kw in ["honor society", "tri-m", "mu alpha theta"]):
        return "Honor Societies"

    if any(
        kw in name_lower
        for kw in [
            "math team", "science olympiad", "science bowl", "quiz bowl",
            "history bowl", "debate", "mock trial", "forensics", "physics team",
            "rocketry", "chemistry", "biology club", "science fair", "puzzle",
            "research olympiad",
        ]
    ):
        return "Academic Competitions"

    if any(
        kw in name_lower
        for kw in [
            "deca", "fbla", "entrepreneurship", "finance club", "finance",
            "girls for business", "wharton", "economic initiative", "young researchers",
        ]
    ):
        return "Business & Finance"

    if any(
        kw in name_lower
        for kw in [
            "computer", "cyber", "machine learning", "coding", "girls who code",
            "app dev", "game dev", "esports", "godot", "smash bros",
            "remote control", "sweenext", "swe",
        ]
    ):
        return "Technology & Engineering"

    if any(
        kw in name_lower
        for kw in [
            "physician", "hosa", "pre-med", "operation smile", "allergy", "aces",
            "red cross", "cancer", "mind booster", "neuroscience", "medlife",
        ]
    ):
        return "Health & Wellness"

    if any(
        kw in name_lower
        for kw in ["green", "chesapeake", "roots and shoots", "treeplenish", "meteorology"]
    ):
        return "Environment & Nature"

    if any(kw in name_lower for kw in ["jazz", "songwrite", "tri-m"]):
        return "Music & Performance"

    if any(kw in name_lower for kw in ["dance", "masti", "midnight players"]):
        return "Dance & Theater"

    if any(
        kw in name_lower
        for kw in [
            "key club", "leo club", "feed the need", "kits to heart",
            "save the children", "unicef", "happy feet", "heartsongs",
            "friendship bracelet", "front liners", "stitches for smiles",
            "red poppy", "paws", "animal welfare",
        ]
    ):
        return "Community Service"

    if any(kw in name_lower for kw in ["mind4youth", "yoga", "uplift", "mental health"]):
        return "Health & Wellness"

    if any(
        kw in name_lower
        for kw in [
            "amnesty", "political", "democrat", "for change", "asylum",
            "immigration", "peace maker", "empowher",
        ]
    ):
        return "Advocacy & Politics"

    if any(
        kw in name_lower
        for kw in [
            "black student", "hispanic", "korean", "chinese", "slavic",
            "south asian", "hindi", "jewish", "muslim", "christian", "fellowship",
            "holiday", "sign language", "braille", "beyond the sight",
            "french club", "culture club", "qsu",
        ]
    ):
        return "Culture & Identity"

    if any(
        kw in name_lower
        for kw in [
            "tutoring", "falcon vision", "minority scholar", "elevate",
            "stem council", "conrad", "mesa", "nasa", "steam magic", "tedx",
        ]
    ):
        return "STEM & Education"

    if any(kw in name_lower for kw in ["frisbee", "weightlifting", "ski", "trail", "fishing"]):
        return "Sports & Recreation"

    if any(
        kw in name_lower
        for kw in ["chess", "mahjong", "dnd", "d&d", "magic: the gathering", "magic the gathering"]
    ):
        return "Games & Strategy"

    if any(kw in name_lower for kw in ["media", "ambassador", "model un"]):
        return "Media & Leadership"

    if any(kw in desc_lower for kw in ["public health", "medical training", "healthcare"]):
        return "Health & Wellness"

    if any(kw in desc_lower for kw in ["environment", "conservation", "sustainability"]):
        return "Environment & Nature"

    return "Academic Competitions"


SKIP_NAMES = {
    "CLASS SPONSORS",
    "ACTIVE CLUB",
    "CLUB NEEDS TO BE APPROVED",
}
CLASS_SPONSOR_RE = re.compile(r"^\s*(\d{4})\s*:\s*(.+?)\s*$")
# Sheet bookkeeping marker: a lowercase "x" prepended to a club name
NAME_MARKER_RE = re.compile(r"^x(?=[A-Z])")


def parse_csv(text):
    """Parse the PHS Clubs CSV text into (clubs, classes)."""
    rows = list(csv.reader(io.StringIO(text)))

    # Find the header row (the one that starts with "Timestamp")
    header_idx = None
    for i, row in enumerate(rows[:20]):
        if row and row[0].strip() == "Timestamp":
            header_idx = i
            break
    if header_idx is None:
        header_idx = 7  # fall back to known position in current sheet

    # Newer sheets have a "Club Category" column inserted after the club name,
    # shifting the remaining columns right by one.
    header = rows[header_idx] if header_idx < len(rows) else []
    has_category_col = (
        len(header) > 2 and header[2].strip().lower() == "club category"
    )
    shift = 1 if has_category_col else 0

    clubs = []
    classes = []
    for row in rows[header_idx + 1 :]:
        if len(row) < 2:
            continue
        name = row[1].strip() if len(row) > 1 else ""
        if not name:
            continue

        # Pull out class sponsor rows like "2026: Ms. Sibrian"
        m = CLASS_SPONSOR_RE.match(name)
        if m:
            classes.append({"year": f"Class of {m.group(1)}", "sponsor": m.group(2)})
            continue

        if name in SKIP_NAMES:
            continue

        name = NAME_MARKER_RE.sub("", name)

        category = row[2].strip() if has_category_col and len(row) > 2 else ""
        contact = row[2 + shift].strip() if len(row) > 2 + shift else ""
        email = row[3 + shift].strip() if len(row) > 3 + shift else ""
        sponsor = row[4 + shift].strip() if len(row) > 4 + shift else ""
        sponsor_email = row[5 + shift].strip() if len(row) > 5 + shift else ""
        description = row[6 + shift].strip() if len(row) > 6 + shift else ""
        meeting_time = row[7 + shift].strip() if len(row) > 7 + shift else ""
        location = row[8 + shift].strip() if len(row) > 8 + shift else ""
        additional = row[9 + shift].strip() if len(row) > 9 + shift else ""

        clubs.append(
            {
                "name": name,
                "contact": contact,
                "email": email,
                "sponsor": sponsor,
                "sponsor_email": sponsor_email,
                "description": description,
                "meeting_time": meeting_time,
                "location": location,
                "additional": additional,
                "category": category or categorize_club(name, description),
            }
        )

    classes.sort(key=lambda c: c["year"])
    return clubs, classes


def _fetch_sheet_csv():
    """Try to pull the latest CSV directly from Google Sheets."""
    try:
        req = urllib.request.Request(
            SHEET_CSV_URL, headers={"User-Agent": "phsclubs-site/1.0"}
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        if "Timestamp" in text and "Name of club" in text:
            with open(CACHE_CSV, "w", encoding="utf-8") as f:
                f.write(text)
            return text, "google-sheet"
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        pass
    return None, None


def _load_csv_text():
    text, source = _fetch_sheet_csv()
    if text:
        return text, source
    if os.path.exists(CACHE_CSV):
        with open(CACHE_CSV, encoding="utf-8") as f:
            return f.read(), "disk-cache"
    with open(BUNDLED_CSV, encoding="utf-8") as f:
        return f.read(), "bundled"


_data_lock = threading.Lock()
_data_cache = {
    "fetched_at": 0.0,
    "clubs": None,
    "categories": None,
    "classes": None,
    "source": None,
}


def get_data(force=False):
    """Return the current clubs/categories/classes, refreshing from the sheet
    if the cache is older than CACHE_TTL_SECONDS (or force=True)."""
    now = time.time()
    with _data_lock:
        fresh_enough = (
            not force
            and _data_cache["clubs"] is not None
            and (now - _data_cache["fetched_at"]) < CACHE_TTL_SECONDS
        )
        if fresh_enough:
            return _data_cache

        text, source = _load_csv_text()
        clubs, classes = parse_csv(text)
        categories = {}
        for club in sorted(clubs, key=lambda c: c["name"]):
            categories.setdefault(club["category"], []).append(club)
        categories = dict(sorted(categories.items()))

        _data_cache.update(
            {
                "fetched_at": now,
                "clubs": clubs,
                "categories": categories,
                "classes": classes,
                "source": source,
            }
        )
        return _data_cache


# Prime the cache at import so the first request is fast.
try:
    get_data(force=True)
except Exception:
    pass


@app.route("/")
def index():
    data = get_data()
    return render_template(
        "index.html",
        categories=data["categories"],
        total=len(data["clubs"]),
        category_icons=CATEGORY_ICONS,
        default_icon=DEFAULT_ICON,
        resource_links=RESOURCE_LINKS,
    )


@app.route("/sga-classes")
def sga_classes():
    data = get_data()
    return render_template(
        "sga_classes.html",
        sga=SGA_INFO,
        classes=data["classes"],
        classes_external_url=CLASSES_EXTERNAL_URL,
        resource_links=RESOURCE_LINKS,
    )


@app.route("/api/clubs")
def api_clubs():
    return jsonify(get_data()["clubs"])


@app.route("/api/status")
def api_status():
    data = get_data()
    return jsonify(
        {
            "total_clubs": len(data["clubs"]),
            "total_classes": len(data["classes"]),
            "categories": {k: len(v) for k, v in data["categories"].items()},
            "source": data["source"],
            "fetched_at": data["fetched_at"],
            "cache_age_seconds": int(time.time() - data["fetched_at"]),
            "ttl_seconds": CACHE_TTL_SECONDS,
        }
    )


@app.route("/refresh", methods=["GET", "POST"])
def refresh():
    """Force re-fetch from Google Sheets. If PHSCLUBS_REFRESH_TOKEN is set,
    requests must pass ?token=... matching it."""
    if REFRESH_TOKEN:
        if request.args.get("token") != REFRESH_TOKEN:
            abort(403)
    data = get_data(force=True)
    return jsonify(
        {
            "ok": True,
            "source": data["source"],
            "total_clubs": len(data["clubs"]),
            "fetched_at": data["fetched_at"],
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
