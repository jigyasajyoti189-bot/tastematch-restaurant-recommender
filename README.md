# 🍴 # TasteMatch — Explainable Restaurant Recommendation System

A responsive Flask web application that helps users discover nearby restaurants based on location and cuisine preferences.

## ✨ Features

- 🔐 User registration and login
- 🔒 Password hashing with Werkzeug
- 📍 Location search with OpenStreetMap Nominatim
- 🗺️ Interactive restaurant map with Leaflet
- 🍽️ Nearby restaurant discovery through OpenStreetMap Overpass
- 🎯 Cuisine preference matching and ranking
- ❤️ Multi-select favorites
- 🗑️ Remove favorites
- 💾 SQLite persistence
- 📱 Responsive UI
- 🔁 Multiple Overpass endpoints for resilience

## 🧰 Tech Stack

- Python
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript
- Leaflet.js
- OpenStreetMap / Nominatim
- Overpass API

## 🚀 Run locally

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd taste-analyzer
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set a secret key

Windows PowerShell:

```powershell
$env:SECRET_KEY="replace-with-a-long-random-value"
```

macOS/Linux:

```bash
export SECRET_KEY="replace-with-a-long-random-value"
```

### 5. Start the application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## 🧪 Project structure

```text
taste-analyzer/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── results.html
│   └── favorites.html
└── static/
    └── style.css
```

## 🔐 Security notes

- Passwords are stored as hashes, not plaintext.
- SQLite database files are excluded from Git.
- Secret keys should be supplied through environment variables.
- Do not commit API keys, credentials, or `.env` files.

## 🗺️ Data

Restaurant and geocoding data are obtained from OpenStreetMap services. Availability and coverage can vary by location.

## 📌 Future improvements

- Automated tests
- Pagination for large result sets
- Restaurant ratings and opening hours
- Better cuisine normalization
- Recommendation model based on user history
- Production deployment with PostgreSQL
- CI/CD with GitHub Actions

### Location behavior
The map and restaurant search are based on the location entered in the search box. Your current device location is **not used automatically**. The **Use my location** button is optional and only uses browser geolocation when you explicitly click it.
