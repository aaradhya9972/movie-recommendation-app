# CineMatch — Movie Recommendation System (Generative-AI course project)

Backend (Python/Flask + ML) · Frontend (HTML/CSS/JS) · Desktop GUI (Java Swing) · **no external API**.

## Run
```bash
pip install -r requirements.txt
python backend/generate_dataset.py   # 1,000,209 ratings  -> data/   (3 s)   [already included]
python backend/train.py              # train + evaluate + graphs (~75 s)    [already included]
python backend/app.py                # open http://127.0.0.1:5000
# Java GUI (needs the backend running):
cd java && javac MovieRecApp.java && java MovieRecApp
```
Windows: double-click `run.bat`. Linux/Mac: `./run.sh`.
Keep the backend window open and open **http://127.0.0.1:5000** in your browser; do not open `frontend/index.html` directly (`file://` cannot reach the local API). On Windows, `run.bat` installs the requirements and starts the backend.

## Dataset (1 million)
`data/ratings.csv` = **1,000,209 ratings**, 6,040 users, 3,700 movies (same size as MovieLens-1M).
It is **synthetic**: generated with user taste-clusters, movie quality, popularity long-tail, so ML has real structure to learn.
194 titles are real famous films (Hollywood + Bollywood), the rest are generated titles.
To use the *real* MovieLens-1M: download it from grouplens.org, then
`python backend/generate_dataset.py --movielens path/to/ml-1m && python backend/train.py` — nothing else changes.
(Say in your report which one you used.)

## Algorithms
| Model | Idea | Used for |
|---|---|---|
| Content-based | TF-IDF of genres×3 + keywords + decade → cosine similarity | "movies like X" |
| Item-item collaborative filtering | user-mean-centred ratings → adjusted cosine between movie columns, shrunk by n/(n+25) | "movies like X" |
| Hybrid | α·content + (1−α)·collaborative (slider in GUI) | default |
| Matrix factorisation (SVD-style, ALS) | r̂ = μ + b_u + b_i + p_u·q_i, k=20 factors | rating **prediction**, "For You" |
| Local semantic search | BGE-base-en-v1.5 embeddings + cosine similarity | natural-language movie discovery |

### Natural-language semantic search (no inference API)
Use the **Describe the movie you want** box in Discover (for example, “a feel-good heist film with clever twists”). The first search downloads `BAAI/bge-base-en-v1.5` from Hugging Face; subsequent embedding and search runs locally, with movie embeddings cached under `artifacts/`. Install `requirements.txt` before starting the backend. Model download requires an internet connection once. BGE is a text-embedding encoder (it ranks semantic matches; it does not generate plot text).

The bundled dataset has no plot summaries, so it searches title, genre, and keyword metadata by default. To add plot-aware matching, place `data/movie_overviews.csv` with columns `movie_id,plot_summary`; only summaries for matching movie IDs are used. The existing dataset and rating-based recommendations are unchanged.

## What happens when you type a movie name
1. Browser/Java calls `GET /api/search?q=incep` on every keystroke → backend normalises text, scores exact/prefix/substring/fuzzy (difflib) matches → autocomplete list.
2. You pick a title → `GET /api/recommend?ids=2&mode=hybrid&n=12`.
3. Flask (`backend/app.py`) validates parameters and calls `Engine.similar()` (`backend/recsys.py`).
4. **Content score**: TF-IDF vector of the movie × TF-IDF matrix of all 3,700 movies (cosine).
5. **Collaborative score**: movie's column of the 1M-rating matrix vs all other columns (adjusted cosine + shrinkage).
6. Blend, apply genre/year filters, remove the movie itself, multiply by a mild popularity prior, take top-N.
7. Return JSON: ranked movies + match %, content %, collab %, shared genres/themes + a **timing trace** (shown as "Behind the scenes").
8. GUI draws cards. Typical latency: 10–40 ms.

Multiple movies can be added to the "taste mix": their score vectors are averaged.

## Evaluation (70/15/15 split: 700,424 train / 150,342 validation / 149,443 test)
| Model | RMSE | MAE |
|---|---|---|
| Global mean | 1.0653 | 0.9089 |
| User+Item bias | 0.9143 | 0.7441 |
| Item-kNN (4,000-rating sample) | 0.8656 | 0.6997 |
| **SVD/ALS (k=20, reg=0.06, 20 iterations)** | **0.8221** | **0.6574** |

Hyperparameters are selected against the validation split; the final serving model is retrained on all ratings. The binary like threshold is 4 stars, and the prediction threshold is tuned on validation data (3.25). On the held-out test split: accuracy 70.9 %, precision 67.0 %, recall 89.9 %, F1 76.8 %, ROC-AUC 0.816. Ranking @10 (600 users) with the tuned popularity prior (weight 1.6): Precision 0.13, NDCG 0.178, hit rate 0.688.
All numbers are in `artifacts/metrics.json` and the **Analytics** tab; PNG graphs are in `artifacts/graphs/`.
(Numbers apply to the synthetic data; real MovieLens will give different values, e.g. RMSE ≈ 0.85–0.87.)

## Files
```
data/        movies.csv  ratings.csv  users.csv
backend/     generate_dataset.py  recsys.py  train.py  app.py  movies_seed.py
frontend/    index.html  style.css  app.js
java/        MovieRecApp.java
artifacts/   model.pkl  metrics.json  stats.json  graphs/*.png
docs/        screenshots
```
REST API: `/api/search` `/api/semantic-search?q=...` `/api/recommend` `/api/user/<id>/recommend` `/api/predict` `/api/top` `/api/metrics` `/api/stats`.

## Scope
Applications: OTT "more like this", e-commerce, music/books/courses. Limits: cold-start, sparsity (95.5 %), popularity bias, static data.
Future: neural CF / transformers, context-aware and diversity re-ranking, online learning.

## Likely viva questions
* **Why hybrid?** Content handles new movies (cold start); CF captures taste patterns content can't see.
* **Why mean-centre?** Some users rate everything 5, others 3; centring compares *preferences*, not scales.
* **Why shrinkage?** Two movies co-rated by 2 users can have similarity 1.0 by luck; n/(n+25) discounts that.
* **RMSE vs confusion matrix?** RMSE measures numeric error; the matrix measures like/dislike decisions (precision, recall).
* **Why ALS?** Each step is a closed-form ridge regression; fast and stable on sparse data.
