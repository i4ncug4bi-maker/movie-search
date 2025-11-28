import os
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, abort

# Încarcă variabilele din .env (local).
load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY nu este setat în .env sau în environment!")

app = Flask(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"  # pentru postere


def tmdb_get(path, params=None):
    """Apel simplu la TMDB cu tratare de erori."""
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY
    params.setdefault("language", "en-US")

    resp = requests.get(f"{TMDB_BASE_URL}{path}", params=params, timeout=10)
    if resp.status_code == 200:
        return resp.json()
    print("TMDB error:", resp.status_code, resp.text)
    return {}


def get_genres():
    data = tmdb_get("/genre/movie/list")
    return data.get("genres", [])


def search_movies(title=None, genre_id=None, year=None):
    """
    Dacă avem title -> /search/movie + filtrare după gen/an.
    Dacă nu avem title -> /discover/movie cu gen/an.
    """
    if title:
        params = {
            "query": title,
            "include_adult": False,
        }
        if year:
            params["year"] = year

        data = tmdb_get("/search/movie", params)
        results = data.get("results", [])

        if genre_id:
            results = [
                m for m in results
                if genre_id in m.get("genre_ids", [])
            ]
    else:
        params = {
            "sort_by": "popularity.desc",
            "include_adult": False,
        }
        if genre_id:
            params["with_genres"] = genre_id
        if year:
            params["primary_release_year"] = year

        data = tmdb_get("/discover/movie", params)
        results = data.get("results", [])

    return results


def get_movie_details(movie_id):
    """
    Detalii film + trailere + where to watch (US).
    """
    data = tmdb_get(
        f"/movie/{movie_id}",
        params={"append_to_response": "videos,watch/providers"},
    )
    if not data or "id" not in data:
        return None

    # Trailer YouTube
    trailer_url = None
    videos = data.get("videos", {}).get("results", [])
    for v in videos:
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
            break

    # Where to watch (US)
    providers = []
    wp = data.get("watch/providers", {}).get("results", {})
    us_providers = wp.get("US", {})  # poți schimba țara aici
    flatrate = us_providers.get("flatrate", [])
    for p in flatrate:
        name = p.get("provider_name")
        if name:
            providers.append(name)

    # Construim un dict simplu pentru template
    movie = {
        "id": data["id"],
        "title": data.get("title"),
        "overview": data.get("overview"),
        "poster_url": TMDB_IMAGE_BASE + data["poster_path"]
        if data.get("poster_path")
        else None,
        "year": (data.get("release_date") or "")[:4],
        "rating": round(data.get("vote_average", 0), 1)
        if data.get("vote_average") is not None
        else None,
        "votes": data.get("vote_count"),
        "genres": [g["name"] for g in data.get("genres", [])],
        "trailer_url": trailer_url,
        "providers": providers,
    }

    return movie


@app.route("/", methods=["GET"])
def index():
    genres = get_genres()
    return render_template("index.html", genres=genres)


@app.route("/search", methods=["POST"])
def search():
    title = (request.form.get("title") or "").strip()
    genre_id_raw = request.form.get("genre_id") or ""
    year_raw = (request.form.get("year") or "").strip()

    genre_id = int(genre_id_raw) if genre_id_raw.isdigit() else None
    year = int(year_raw) if year_raw.isdigit() else None

    genres = get_genres()
    genre_name = None
    if genre_id:
        for g in genres:
            if g["id"] == genre_id:
                genre_name = g["name"]
                break

    tmdb_results = search_movies(title=title or None, genre_id=genre_id, year=year)

    movies = []
    for m in tmdb_results:
        poster_url = TMDB_IMAGE_BASE + m["poster_path"] if m.get("poster_path") else None
        movies.append(
            {
                "id": m["id"],
                "title": m.get("title"),
                "overview": (m.get("overview") or "")[:230],
                "poster_url": poster_url,
                "rating": round(m.get("vote_average", 0), 1)
                if m.get("vote_average") is not None
                else None,
                "votes": m.get("vote_count"),
                "year": (m.get("release_date") or "")[:4],
            }
        )

    return render_template(
        "results.html",
        movies=movies,
        title_query=title,
        genre_name=genre_name,
        year=year,
    )


@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    movie = get_movie_details(movie_id)
    if not movie:
        abort(404)
    return render_template("detail.html", movie=movie)


if __name__ == "__main__":
    # Local run
    app.run(debug=True)
