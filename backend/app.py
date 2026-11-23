"""
Flask backend  ->  python backend/app.py   then open http://127.0.0.1:5000
Serves the web GUI (frontend/) and a JSON REST API that both the web page and the Java app use.
No external APIs are called: everything comes from the local dataset and the trained model.
"""
import json, os, pickle, sys, time
from flask import Flask, jsonify, request, send_from_directory, abort

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, ".."); ART = os.path.join(ROOT, "artifacts")
sys.path.insert(0, HERE)
import recsys  # noqa  (needed so pickle can find the classes)
from semantic import SemanticSearch

if not os.path.exists(os.path.join(ART, "model.pkl")):
    sys.exit("Model not found. Run:  python backend/generate_dataset.py  &&  python backend/train.py")
print("Loading model ...", end=" ", flush=True); t = time.time()
ENG = pickle.load(open(os.path.join(ART, "model.pkl"), "rb"))
METRICS = json.load(open(os.path.join(ART, "metrics.json"))); STATS = json.load(open(os.path.join(ART, "stats.json")))
print(f"done in {time.time() - t:.1f}s  ({ENG.N:,} movies, {ENG.U:,} users, {int(ENG.R.nnz):,} ratings)")
GENRES = sorted(STATS["genre_counts"])
app = Flask(__name__, static_folder=None)
SEMANTIC = SemanticSearch(ENG.movies, os.path.join(ROOT, "data"), ART)


def intarg(name, default, lo=None, hi=None):
    try: v = int(request.args.get(name, default))
    except ValueError: abort(400, f"{name} must be an integer")
    if lo is not None: v = max(lo, v)
    if hi is not None: v = min(hi, v)
    return v


@app.get("/api/health")
def health(): return jsonify(status="ok", movies=int(ENG.N), users=int(ENG.U), ratings=int(ENG.R.nnz))

@app.get("/api/search")
def search(): return jsonify(ENG.search(request.args.get("q", ""), intarg("limit", 8, 1, 25)))

@app.get("/api/semantic-search")
def semantic_search():
    query = request.args.get("q", "")
    if not query.strip(): abort(400, "q must not be empty")
    if len(query) > 500: abort(400, "q must be 500 characters or fewer")
    try:
        result = SEMANTIC.search(query, intarg("n", 12, 1, 50))
        result["results"] = [
            ENG.card(movie["movie_id"] - 1, semantic_score=movie["semantic_score"])
            for movie in result["results"]
        ]
        return jsonify(result)
    except ImportError as exc:
        return jsonify(error="Local semantic search requires sentence-transformers. Install requirements.txt first.",
                       detail=str(exc)), 503
    except ValueError as exc:
        abort(400, str(exc))

@app.get("/api/genres")
def genres(): return jsonify(GENRES)

@app.get("/api/recommend")
def recommend():
    """GET /api/recommend?ids=1,2,3 (movie ids) | title=Inception   &mode=hybrid|content|collab &n=12 &alpha=.45 &genre= &year_min= &year_max="""
    ids = []
    if request.args.get("ids"):
        try: ids = [int(x) - 1 for x in request.args["ids"].split(",") if x]
        except ValueError: abort(400, "ids must be integers")
    elif request.args.get("title"):
        hit = ENG.search(request.args["title"], 1)
        ids = [hit[0]["movie_id"] - 1] if hit else []
    ids = [i for i in ids if 0 <= i < ENG.N][:5]
    if not ids:
        return jsonify(error="Movie not found", suggestions=ENG.search(request.args.get("title", ""), 5)), 404
    mode = request.args.get("mode", "hybrid")
    if mode not in ("hybrid", "content", "collab"): abort(400, "mode must be hybrid, content or collab")
    return jsonify(ENG.similar(ids, mode, intarg("n", 12, 1, 50), float(request.args.get("alpha", .45)), request.args.get("genre") or None,
                               intarg("year_min", 0) or None, intarg("year_max", 0) or None))

@app.get("/api/user/<int:uid>")
def user(uid):
    if not 1 <= uid <= ENG.U: return jsonify(error=f"User id must be between 1 and {ENG.U}"), 404
    return jsonify(ENG.user_info(uid))

@app.get("/api/user/<int:uid>/recommend")
def user_rec(uid):
    if not 1 <= uid <= ENG.U: return jsonify(error=f"User id must be between 1 and {ENG.U}"), 404
    return jsonify(ENG.recommend_user(uid, intarg("n", 12, 1, 50), request.args.get("genre") or None))

@app.get("/api/predict")
def predict():
    uid, mid = intarg("user", 1), intarg("movie", 1)
    if not (1 <= uid <= ENG.U and 1 <= mid <= ENG.N): return jsonify(error="user or movie id out of range"), 404
    return jsonify(ENG.predict(uid, mid))

@app.get("/api/top")
def top(): return jsonify(ENG.top_movies(request.args.get("genre") or None, intarg("n", 12, 1, 50)))

@app.get("/api/metrics")
def metrics(): return jsonify(METRICS)

@app.get("/api/stats")
def stats(): return jsonify(STATS)

@app.get("/graphs/<path:f>")
def graphs(f): return send_from_directory(os.path.join(ART, "graphs"), f)

@app.get("/")
def index(): return send_from_directory(os.path.join(ROOT, "frontend"), "index.html")

@app.get("/<path:f>")
def static_files(f): return send_from_directory(os.path.join(ROOT, "frontend"), f)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
