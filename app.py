import os
import re
import sqlite3
from functools import wraps
from math import radians, cos, sin, sqrt, atan2

import requests
from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "taste_analyzer.db")

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "taste-analyzer-development-key"
)

app.config["DATABASE"] = DATABASE

USER_AGENT = "TasteAnalyzerPro/1.0"

NOMINATIM_URL = "https://nominatim.openstreetmap.org"

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


# =========================================================
# DATABASE
# =========================================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():

    db = get_db()

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            cuisine TEXT,
            distance REAL,
            latitude REAL,
            longitude REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                user_id,
                name,
                latitude,
                longitude
            ),

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );
        """
    )

    db.commit()


@app.context_processor
def inject_user():

    return {
        "current_user": session.get("user")
    }


# =========================================================
# AUTHENTICATION
# =========================================================

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


def valid_email(email):

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return bool(
        re.match(pattern, email)
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        phone = request.form.get(
            "phone", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not name or not email or not password:

            flash(
                "Please complete all required fields.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if not valid_email(email):

            flash(
                "Please enter a valid email address.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "error"
            )

            return render_template(
                "register.html"
            )

        db = get_db()

        try:

            cursor = db.execute(
                """
                INSERT INTO users
                (name, email, phone, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    phone,
                    generate_password_hash(password),
                ),
            )

            db.commit()

        except sqlite3.IntegrityError:

            flash(
                "An account with this email already exists.",
                "error"
            )

            return render_template(
                "register.html"
            )

        session.clear()

        session["user_id"] = cursor.lastrowid

        session["user"] = {
            "id": cursor.lastrowid,
            "name": name,
            "email": email,
        }

        return redirect(
            url_for("home")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        user = get_db().execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        if (
            user
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):

            session.clear()

            session["user_id"] = user["id"]

            session["user"] = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
            }

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# LOCATION SEARCH
# =========================================================

def get_coordinates(location):

    try:

        response = requests.get(
            f"{NOMINATIM_URL}/search",

            params={
                "q": location,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },

            headers={
                "User-Agent": USER_AGENT
            },

            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return None, None

        return (
            float(data[0]["lat"]),
            float(data[0]["lon"]),
        )

    except (
        requests.RequestException,
        ValueError,
        KeyError,
    ):

        return None, None


# =========================================================
# DISTANCE
# =========================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    earth_radius = 6371.0

    dlat = radians(
        lat2 - lat1
    )

    dlon = radians(
        lon2 - lon1
    )

    a = (
        sin(dlat / 2) ** 2
        +
        cos(radians(lat1))
        *
        cos(radians(lat2))
        *
        sin(dlon / 2) ** 2
    )

    a = max(
        0.0,
        min(1.0, a)
    )

    distance = (
        earth_radius
        * 2
        * atan2(
            sqrt(a),
            sqrt(1 - a)
        )
    )

    return round(
        distance,
        2
    )


# =========================================================
# CUISINE MATCHING
# =========================================================

CUISINE_ALIASES = {

    "indian": [
        "indian",
        "north indian",
        "south indian",
        "mughlai",
    ],

    "chinese": [
        "chinese",
        "sichuan",
        "cantonese",
    ],

    "italian": [
        "italian",
        "pizza",
        "pasta",
    ],

    "mexican": [
        "mexican",
        "taco",
        "tex mex",
    ],

    "continental": [
        "continental",
        "european",
    ],

    "fast food": [
        "fast food",
        "burger",
        "fried chicken",
        "chicken",
        "sandwich",
    ],

    "dessert": [
        "dessert",
        "cake",
        "ice cream",
        "bakery",
        "pastry",
        "confectionery",
    ],
}


def normalize_text(value):

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        (value or "").lower()
    ).strip()


def cuisine_matches(
    cuisine,
    selected_tastes
):

    normalized_cuisine = normalize_text(
        cuisine
    )

    for taste in selected_tastes:

        normalized_taste = normalize_text(
            taste
        )

        aliases = CUISINE_ALIASES.get(
            normalized_taste,
            [normalized_taste]
        )

        for alias in aliases:

            if normalize_text(alias) in normalized_cuisine:
                return True

    return False


# =========================================================
# MATCH SCORE
# =========================================================

def calculate_match_score(
    cuisine,
    distance,
    tastes
):

    reasons = []

    # -----------------------------------------
    # TASTE SCORE
    # -----------------------------------------

    if tastes:

        if cuisine_matches(
            cuisine,
            tastes
        ):

            taste_score = 70

            reasons.append(
                "Cuisine matches your taste"
            )

        else:

            taste_score = 0

            reasons.append(
                "No cuisine match found"
            )

    else:

        taste_score = 50

        reasons.append(
            "No cuisine preference selected"
        )

    # -----------------------------------------
    # DISTANCE SCORE
    # -----------------------------------------

    if distance <= 1:

        distance_score = 30

        reasons.append(
            "Very close"
        )

    elif distance <= 3:

        distance_score = 25

        reasons.append(
            "Close by"
        )

    elif distance <= 5:

        distance_score = 20

    elif distance <= 7:

        distance_score = 10

    else:

        distance_score = 5

    # -----------------------------------------
    # FINAL SCORE
    # -----------------------------------------

    final_score = min(
        100,
        taste_score + distance_score
    )

    return (
        final_score,
        reasons
    )


# =========================================================
# RESTAURANT SEARCH
# =========================================================

def get_restaurants(
    lat,
    lon,
    radius=10000
):

    query = f"""
    [out:json][timeout:45];

    (
        nwr["amenity"="restaurant"]
        (around:{radius},{lat},{lon});

        nwr["amenity"="fast_food"]
        (around:{radius},{lat},{lon});

        nwr["amenity"="cafe"]
        (around:{radius},{lat},{lon});
    );

    out center tags;
    """

    for server in OVERPASS_SERVERS:

        try:

            response = requests.post(
                server,

                data={
                    "data": query
                },

                headers={
                    "User-Agent": USER_AGENT
                },

                timeout=60,
            )

            response.raise_for_status()

            data = response.json()

            restaurants = []

            seen = set()

            for element in data.get(
                "elements",
                []
            ):

                tags = element.get(
                    "tags",
                    {}
                )

                name = tags.get(
                    "name"
                )

                if not name:
                    continue

                rlat = element.get(
                    "lat"
                )

                rlon = element.get(
                    "lon"
                )

                if (
                    rlat is None
                    or rlon is None
                ):

                    center = element.get(
                        "center",
                        {}
                    )

                    rlat = center.get(
                        "lat"
                    )

                    rlon = center.get(
                        "lon"
                    )

                if (
                    rlat is None
                    or rlon is None
                ):
                    continue

                try:

                    rlat = float(rlat)
                    rlon = float(rlon)

                except (
                    TypeError,
                    ValueError,
                ):

                    continue

                key = (
                    name.lower().strip(),
                    round(rlat, 5),
                    round(rlon, 5),
                )

                if key in seen:
                    continue

                seen.add(key)

                amenity = tags.get(
                    "amenity",
                    "restaurant"
                )

                cuisine = tags.get(
                    "cuisine",
                    ""
                ).strip()

                if not cuisine:

                    cuisine = {
                        "restaurant": "Restaurant",
                        "fast_food": "Fast Food",
                        "cafe": "Cafe",
                    }.get(
                        amenity,
                        "Not specified"
                    )

                opening_hours = tags.get(
                    "opening_hours",
                    ""
                ).strip()

                distance = calculate_distance(
                    lat,
                    lon,
                    rlat,
                    rlon
                )

                restaurants.append({

                    "name": name,

                    "cuisine": cuisine,

                    "lat": rlat,

                    "lon": rlon,

                    "distance": distance,

                    "opening_hours": opening_hours,

                    "score": 0,

                    "matched_tastes": [],

                    "match_reasons": [],

                })

            return restaurants

        except (
            requests.RequestException,
            ValueError,
        ):

            continue

    return []


# =========================================================
# HOME
# =========================================================

@app.route("/")
@login_required
def home():

    cuisine_options = [
        "Indian",
        "Chinese",
        "Italian",
        "Mexican",
        "Continental",
        "Fast Food",
        "Dessert",
    ]

    return render_template(
        "index.html",
        cuisine_options=cuisine_options
    )


# =========================================================
# RESULTS
# =========================================================

@app.route(
    "/results",
    methods=["POST"]
)
@login_required
def results():

    location = request.form.get(
        "location",
        ""
    ).strip()

    tastes = request.form.getlist(
        "tastes"
    )

    if not location:

        flash(
            "Please enter a location.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    lat, lon = get_coordinates(
        location
    )

    if lat is None or lon is None:

        return render_template(
            "results.html",

            restaurants=[],

            location=location,

            lat=None,

            lon=None,

            tastes=tastes,

            error=(
                "We couldn't find that location. "
                "Try a city, area, landmark or PIN code."
            ),
        )

    restaurants = get_restaurants(
        lat,
        lon
    )

    for restaurant in restaurants:

        score, reasons = calculate_match_score(
            restaurant["cuisine"],
            restaurant["distance"],
            tastes,
        )

        restaurant["score"] = score

        restaurant["match_reasons"] = reasons

        restaurant["matched_tastes"] = [
            taste
            for taste in tastes
            if cuisine_matches(
                restaurant["cuisine"],
                [taste]
            )
        ]

    restaurants.sort(
        key=lambda restaurant: (
            -restaurant["score"],
            restaurant["distance"]
        )
    )

    return render_template(
        "results.html",

        restaurants=restaurants,

        location=location,

        lat=lat,

        lon=lon,

        tastes=tastes,

        error=None,
    )


# =========================================================
# CURRENT LOCATION
# =========================================================

@app.route(
    "/detect_location",
    methods=["POST"]
)
@login_required
def detect_location():

    data = request.get_json(
        silent=True
    ) or {}

    try:

        lat = float(
            data.get("lat")
        )

        lon = float(
            data.get("lon")
        )

    except (
        TypeError,
        ValueError,
    ):

        return jsonify({
            "address": "Location unavailable"
        }), 400

    try:

        response = requests.get(

            f"{NOMINATIM_URL}/reverse",

            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
            },

            headers={
                "User-Agent": USER_AGENT
            },

            timeout=15,
        )

        response.raise_for_status()

        result = response.json()

        return jsonify({

            "address": result.get(
                "display_name",
                "Current location"
            )

        })

    except (
        requests.RequestException,
        ValueError,
    ):

        return jsonify({
            "address": "Unable to detect location"
        }), 500


# =========================================================
# ADD FAVORITES
# =========================================================

@app.route(
    "/add_selected_favorites",
    methods=["POST"]
)
@login_required
def add_selected_favorites():

    selected = request.form.getlist(
        "selected_restaurants"
    )

    db = get_db()

    saved = 0

    for index in selected:

        name = request.form.get(
            f"restaurant_name_{index}",
            ""
        ).strip()

        cuisine = request.form.get(
            f"restaurant_cuisine_{index}",
            ""
        )

        distance = request.form.get(
            f"restaurant_distance_{index}",
            ""
        )

        latitude = request.form.get(
            f"restaurant_lat_{index}"
        )

        longitude = request.form.get(
            f"restaurant_lon_{index}"
        )

        if not name:
            continue

        try:

            cursor = db.execute(
                """
                INSERT OR IGNORE INTO favorites
                (
                    user_id,
                    name,
                    cuisine,
                    distance,
                    latitude,
                    longitude
                )

                VALUES (?, ?, ?, ?, ?, ?)
                """,

                (
                    session["user_id"],
                    name,
                    cuisine,
                    float(distance)
                    if distance
                    else None,

                    float(latitude)
                    if latitude
                    else None,

                    float(longitude)
                    if longitude
                    else None,
                ),
            )

            if cursor.rowcount:

                saved += 1

        except (
            ValueError,
            sqlite3.Error,
        ):

            continue

    db.commit()

    if saved:

        flash(
            f"{saved} restaurant(s) saved to favorites.",
            "success"
        )

    else:

        flash(
            "No new restaurants were selected.",
            "error"
        )

    return redirect(
        url_for("favorites")
    )


# =========================================================
# FAVORITES
# =========================================================

@app.route("/favorites")
@login_required
def favorites():

    rows = get_db().execute(
        """
        SELECT *
        FROM favorites
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,

        (
            session["user_id"],
        ),
    ).fetchall()

    return render_template(
        "favorites.html",
        favorites=rows
    )


# =========================================================
# REMOVE FAVORITE
# =========================================================

@app.route(
    "/remove_favorite",
    methods=["POST"]
)
@login_required
def remove_favorite():

    favorite_id = request.form.get(
        "favorite_id"
    )

    get_db().execute(
        """
        DELETE FROM favorites
        WHERE id = ?
        AND user_id = ?
        """,

        (
            favorite_id,
            session["user_id"],
        ),
    )

    get_db().commit()

    flash(
        "Restaurant removed from favorites.",
        "success"
    )

    return redirect(
        url_for("favorites")
    )


# =========================================================
# DATABASE COMMAND
# =========================================================

@app.cli.command("init-db")
def init_db_command():

    init_db()

    print(
        "Database initialized successfully."
    )


# =========================================================
# START APPLICATION
# =========================================================

with app.app_context():
    init_db()


if __name__ == "__main__":

    app.run(
        debug=True
    )