# CineMatch

CineMatch is an end-to-end movie recommendation application built with Python, Flask, HTML/CSS/JavaScript, and an optional Java Swing desktop client.

It combines:

- **Content-based filtering** using genres, themes, keywords, and release decade
- **Item-based collaborative filtering** using adjusted cosine similarity
- **Matrix factorization** for personalized star-rating prediction
- **Hybrid recommendations** that blend content and collaborative signals
- **Local semantic search** using the BGE sentence-transformer model

The system does not require an external recommendation API. Its data, embeddings, and trained model run locally.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Dataset](#dataset)
- [Recommendation methods](#recommendation-methods)
- [Model training and evaluation](#model-training-and-evaluation)
- [Installation](#installation)
- [Running the project](#running-the-project)
- [Using the applications](#using-the-applications)
- [REST API](#rest-api)
- [Project structure](#project-structure)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Future improvements](#future-improvements)
- [Troubleshooting](#troubleshooting)
- [Viva and interview questions](#viva-and-interview-questions)

---

## Features

### Movie discovery

- Search movies by title with exact, prefix, substring, fuzzy, and popularity-aware matching
- Discover movies using natural-language descriptions
- Filter recommendations by genre and release-year range
- Explore popular titles from the complete dataset

### Recommendation modes

- **Hybrid:** balances content similarity and collaborative similarity
- **Content:** recommends movies that share genres, themes, and metadata
- **Collaborative:** recommends movies that users with similar rating patterns prefer
- **For You:** predicts the ratings for every unseen movie for a selected user

### Rating prediction

- Predicts a rating from 1 to 5 stars
- Breaks a prediction into global mean, user bias, item bias, and latent-factor interaction components
- Converts ratings into a binary “like”/“dislike” decision using a tuned threshold

### Analytics

- Compares baseline, bias, item-kNN, and SVD/ALS models
- Reports RMSE and MAE
- Visualizes confusion matrices and ranking metrics
- Displays dataset sparsity, rating distribution, genre averages, and decade information

---

## Architecture

```text
Browser or Java Swing client
        |
        | HTTP / JSON
        v
Flask REST API (backend/app.py)
        |
        +-- Recommendation engine (backend/recsys.py)
        |     +-- TF-IDF content model
        |     +-- Item-item collaborative model
        |     +-- Biased matrix-factorization model
        |
        +-- Semantic search (backend/semantic.py)
              +-- BGE embeddings
              +-- Local embedding cache
```

The main execution flow is:

1. `generate_dataset.py` creates the movie, user, and rating data.
2. `train.py` evaluates the models and writes JSON metrics and graphs.
3. `train.py` trains the final matrix-factorization model on all ratings.
4. `app.py` loads the serialized `Engine` from `artifacts/model.pkl`.
5. The browser or Java client consumes the local Flask REST API.

---

## Dataset

The bundled dataset contains **1,000,209 ratings**:

| Entity | Count |
|---:|---:|
| Ratings | 1,000,209 |
| Users | 6,040 |
| Movies | 3,883 |

The project currently uses the real **MovieLens-1M** dataset. It contains ratings from 6,040 users for 3,883 movies, totaling 1,000,209 ratings.

MovieLens-1M is a research dataset commonly used for recommender-system benchmarks. It includes:

- 1 to 5 star ratings
- User gender and age metadata
- Movie titles, release years, and genres
- 1,000,209 historical interactions

Movie IDs that contain gaps in the original archive are remapped to contiguous IDs during CSV conversion so they remain compatible with the application's sparse matrices.

The generated files are stored in:

```text
data/
├── movies.csv
├── ratings.csv
└── users.csv
```

### Data sparsity

The rating matrix has shape:

\[
6040 \times 3883
\]

It contains 1,000,209 observed ratings out of approximately 22.35 million possible user/movie pairs. This gives approximately 95.5% sparsity.

The sparsity is calculated as:

\[
1-\frac{\text{number of ratings}}{\text{number of users} \times \text{number of movies}}
\]

### Replacing or restoring the dataset

The active CSV files were generated from MovieLens-1M with:

```bash
python backend/generate_dataset.py --movielens path\to\ml-1m
python backend/train.py
python backend/app.py
```

The synthetic backup was saved in `backups/synthetic-20261124-093523/`. Restoring it requires copying the backed-up `data/` and `artifacts/` directories back to the project root and rerunning `python backend/app.py`.

---

## Recommendation methods

## 1. Content-based recommendations

Each movie is represented by metadata text containing:

- Genres repeated for additional weight
- Keywords and themes
- A release-decade feature

The text is converted into TF-IDF vectors and normalized. Similarity is calculated using cosine similarity:

\[
cosine(a,b)=\frac{a \cdot b}{\|a\|\|b\|}
\]

This method is useful for cold-start movies because it only requires movie metadata. It works especially well for:

- Finding movies with the same genres
- Finding films with similar themes
- Recommending based on one or more seed movies

## 2. Item-item collaborative filtering

Collaborative filtering compares movie rating columns from the sparse user-by-movie matrix.

Before similarity is calculated, each user's ratings are mean-centred:

\[
r'_{ui}=r_{ui}-\mu_u
\]

The resulting vectors are cosine-normalized and used to compute adjusted cosine similarity.

Similarity is shrunk when the number of common raters is small:

\[
similarity_{shrunk}=similarity \times \frac{n}{n+25}
\]

Here, `n` is the number of users who rated both movies. Shrinkage prevents a pair of movies from appearing perfectly similar when they have only one or two raters in common.

## 3. Hybrid recommendations

For one or more selected movies, the engine averages content and collaborative vectors.

The default hybrid score is:

\[
S=\alpha S_{content}+(1-\alpha)S_{collaborative}
\]

The default value is `alpha = 0.45`.

- `alpha = 1.0` uses content-only recommendations
- `alpha = 0.0` uses collaborative-only recommendations
- Values between 0 and 1 blend both approaches

Before ranking, the engine:

1. Normalizes both score sources
2. Removes the selected movie or taste-profile movies
3. Applies genre and year filters
4. Keeps only movies with at least 30 ratings
5. Applies a small popularity factor
6. Sorts and returns the top N results

Multiple selected movies produce an averaged taste profile.

## 4. Matrix factorization

The personalized rating model uses a biased SVD-style latent-factor model trained with alternating least squares (ALS):

\[
\hat r_{ui}=\mu+b_u+b_i+p_u\cdot q_i
\]

Where:

- \(\mu\) is the global mean rating
- \(b_u\) is the user bias
- \(b_i\) is the movie bias
- \(p_u\) is the latent taste vector for user `u`
- \(q_i\) is the latent attribute vector for movie `i`

Predictions are restricted to the range 1 to 5.

The tuned model uses:

| Parameter | Value |
|---|---:|
| Latent factors (`k`) | 32 |
| Regularization (`reg`) | 0.10 |
| ALS iterations | 20 |
| Like threshold | 4 stars |
| Prediction threshold | 3.25 |
| Popularity prior weight | 2.0 |

The model is trained on the training matrix for evaluation. A final model is retrained on all available ratings and saved to `artifacts/model.pkl` for serving.

## 5. Local semantic search

Natural-language search uses `BAAI/bge-base-en-v1.5` through `sentence-transformers`.

The first semantic search downloads the model and creates embeddings for:

- Movie title
- Genres
- Keywords
- Optional plot summaries

Embeddings are normalized, and query/document similarity is measured with cosine similarity. A cache of the embeddings is stored in `artifacts/bge_movie_embeddings.npz`.

Optional plot summaries can be provided by creating:

```text
data/movie_overviews.csv
```

with columns:

```csv
movie_id,plot_summary
```

The cached index is regenerated when the movie documents or model name change.

---

## Model training and evaluation

## Train-validation-test split

Ratings are split deterministically using a NumPy random generator:

| Split | Size |
|---|---:|
| Training | 700,424 |
| Validation | 150,342 |
| Test | 149,443 |

The split is approximately 70%/15%/15%.

- Training is used to fit models
- Validation is used to tune hyperparameters and thresholds
- Test data is used only for final reporting

## Rating prediction metrics

### RMSE

Root Mean Squared Error:

\[
RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(r_i-\hat r_i)^2}
\]

RMSE penalizes large prediction errors more strongly. Lower is better.

### MAE

Mean Absolute Error:

\[
MAE=\frac{1}{n}\sum_{i=1}^{n}|r_i-\hat r_i|
\]

MAE reports the average distance between actual and predicted ratings.

### Model comparison

| Model | RMSE | MAE |
|---|---:|---:|
| Global mean | 1.1163 | 0.9334 |
| User + item bias | 0.9088 | 0.7202 |
| Item-kNN, 4,000-rating sample | 0.8823 | 0.6922 |
| **SVD/ALS, k=32** | **0.8684** | **0.6828** |

These values are saved in `artifacts/metrics.json`.

## Binary classification metrics

A rating of 4 or 5 is considered a “like.” The model predicts a like when its predicted rating is at least 3.25.

The confusion matrix contains:

|  | Predicted dislike | Predicted like |
|---|---:|---:|
| Actual dislike | TN | FP |
| Actual like | FN | TP |

### Accuracy

\[
Accuracy=\frac{TP+TN}{TP+TN+FP+FN}
\]

### Precision

\[
Precision=\frac{TP}{TP+FP}
\]

### Recall

\[
Recall=\frac{TP}{TP+FN}
\]

### F1 score

\[
F1=2\frac{Precision \times Recall}{Precision+Recall}
\]

### ROC-AUC

ROC-AUC evaluates how successfully the continuous predicted rating separates liked and disliked movies, independent of one fixed threshold.

### Held-out test results

| Metric | Result |
|---|---:|
| Binary accuracy | 73.13% |
| Precision | 70.88% |
| Recall | 90.58% |
| F1 | 79.53% |
| ROC-AUC | 0.8126 |
| Exact 5-star accuracy | 44.64% |
| Within-one-star accuracy | 91.96% |

## Ranking metrics

Ranking quality is evaluated for 600 users using top-10 recommendations. Relevant movies are test ratings of 4 stars or higher.

Movies the user already rated in the training matrix are removed.

### Precision@10

\[
Precision@10=\frac{\text{relevant items in top 10}}{10}
\]

### Recall@10

\[
Recall@10=\frac{\text{relevant items in top 10}}{\text{all relevant items}}
\]

### Hit rate

The fraction of users who receive at least one relevant movie in their top 10.

### NDCG@10

Normalized Discounted Cumulative Gain rewards relevant items placed at higher positions:

\[
DCG@10=\sum_{i=1}^{10}\frac{relevance_i}{\log_2(i+1)}
\]

\[
NDCG@10=\frac{DCG@10}{IDCG@10}
\]

## Ranking comparison

| Method | Precision@10 | Recall@10 | NDCG@10 | Hit rate |
|---|---:|---:|---:|---:|
| Random | 0.0071 | 0.0039 | 0.0074 | 0.0676 |
| Popularity | 0.1096 | 0.0836 | 0.1283 | 0.5828 |
| SVD/ALS | 0.0566 | 0.0387 | 0.0673 | 0.3649 |
| **SVD + popularity prior** | **0.1204** | **0.0932** | **0.1413** | **0.6149** |

All reported numbers are for the active real MovieLens-1M dataset.

---

## Installation

### Prerequisites

- Python 3.10 or later
- `pip`
- Internet connection for the first semantic-model download
- Java 8 or later only if using the desktop client

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

### Dependencies

- Flask
- NumPy
- pandas
- SciPy
- scikit-learn
- Matplotlib
- `sentence-transformers`

---

## Running the project

## Generate the dataset

The bundled data is already included, but it can be regenerated:

```bash
python backend/generate_dataset.py
```

This writes the files under `data/`.

## Train and evaluate

```bash
python backend/train.py
```

This:

- creates the 70/15/15 split
- tunes matrix-factorization and ranking parameters
- evaluates the models
- writes metrics and graphs
- saves the final model to `artifacts/model.pkl`

On the included dataset, training can take about 75 seconds depending on the machine.

## Start the web application

```bash
python backend/app.py
```

Open:

```text
http://127.0.0.1:5000
```

Do not open `frontend/index.html` directly with `file://`. The frontend needs the Flask API.

## One-command Windows launch

```bat
run.bat
```

The script:

- installs dependencies
- generates missing data
- trains a missing model
- starts Flask

## One-command Linux/macOS launch

```bash
chmod +x run.sh
./run.sh
```

## Java desktop client

Keep Flask running, then:

```bash
cd java
javac MovieRecApp.java
java MovieRecApp
```

The Java client defaults to `http://127.0.0.1:5000`.

---

## Using the applications

## Discover by title

1. Open the Discover view.
2. Enter part or all of a movie title.
3. Select one or more movies.
4. Choose Hybrid, Content, or Collaborative mode.
5. Adjust the content/collaborative blend.
6. Optionally filter by genre and year.
7. View the ranked recommendations and similarity breakdown.

## Describe a movie

Enter a natural-language request such as:

```text
a feel-good heist film with clever twists
```

The semantic search ranks the local movie catalog according to the description.

## Personalized recommendations

Enter a user ID from 1 to 6040 to:

- view the user's rating profile
- inspect favorite genres
- view previously top-rated movies
- receive recommendations for unseen movies

## Rating prediction

The prediction endpoint and UI return:

- global mean
- user bias
- item bias
- latent interaction
- final predicted rating

---

## REST API

The Flask server runs at `http://127.0.0.1:5000`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health, movie, user, and rating counts |
| GET | `/api/search?q=incep&limit=8` | Title search |
| GET | `/api/semantic-search?q=...&n=12` | Natural-language semantic search |
| GET | `/api/genres` | Available genres |
| GET | `/api/recommend?ids=1,2&mode=hybrid&n=12` | Similar movies |
| GET | `/api/recommend?title=Inception&mode=content&n=12` | Recommend from a title |
| GET | `/api/user/1` | User profile |
| GET | `/api/user/1/recommend?n=12&genre=Action` | Personalized recommendations |
| GET | `/api/predict?user=1&movie=2` | Predict a rating |
| GET | `/api/top?n=12&genre=Drama` | Top movies |
| GET | `/api/metrics` | Training and evaluation metrics |
| GET | `/api/stats` | Dataset statistics |
| GET | `/graphs/<filename>.png` | Evaluation graph |

### Example: similar movies

```text
GET /api/recommend?ids=2&mode=hybrid&n=12&alpha=.45
```

Example response fields include:

- `query`
- `results`
- `score`
- `match`
- `content`
- `collab`
- `shared_genres`
- `shared_keywords`
- `trace`
- `total_ms`

### Example: prediction

```text
GET /api/predict?user=10&movie=25
```

The response includes the final prediction and its four decomposition components.

---

## Project structure

```text
.
├── backend/
│   ├── app.py                 Flask server and REST API
│   ├── generate_dataset.py    Synthetic dataset generator
│   ├── movies_seed.py         Seed movie catalog
│   ├── recsys.py              Recommendation engine and models
│   ├── semantic.py            Local BGE semantic search
│   └── train.py               Training and evaluation pipeline
├── frontend/
│   ├── index.html             Web interface
│   ├── style.css              Application styling
│   └── app.js                 Frontend API integration
├── java/
│   └── MovieRecApp.java       Java Swing desktop client
├── data/
│   ├── movies.csv
│   ├── ratings.csv
│   └── users.csv
├── artifacts/
│   ├── model.pkl              Final serialized recommendation engine
│   ├── metrics.json           Evaluation metrics
│   ├── stats.json             Dataset statistics
│   ├── bge_movie_embeddings.npz
│   └── graphs/                Generated evaluation charts
├── requirements.txt
├── run.bat
├── run.sh
└── README.md
```

Generated graphs include:

- Rating distribution
- Training size and rating statistics
- Model RMSE comparison
- Confusion matrices
- K-factor sweep
- Ranking metrics
- Rating-prediction heatmap

---

## Configuration

The main model parameters are defined in `backend/train.py`:

```python
K = 32
REG = 0.10
ITERS = 20
LIKE = 4
POP_W = 2.0
PRED_THRESHOLD = 3.25
```

The engine can adjust other behavior in `backend/recsys.py`:

- `SHRINK = 25.0` for item-item similarity shrinkage
- Candidate minimum: 30 ratings
- Default hybrid alpha: 0.45
- Maximum taste-profile movies: 5

---

## Limitations

- Real-world performance can differ across datasets and deployment conditions
- Popularity and movie-quality patterns can create recommendation bias
- The item-item matrix is sparse and sensitive to small rating counts
- Matrix factorization suffers from cold-start for unknown users and movies
- The semantic model requires a large first download and sufficient memory
- No user accounts or persistent online learning are implemented
- A random train/test split can allow the same users or movies to appear in both sets
- Ranking is evaluated with a single held-out relevance definition: ratings of at least 4

---

## Future improvements

- Deep collaborative filtering with neural networks
- Sequence-aware recommendation with transformers
- Cold-start profiles based on a short onboarding quiz
- Diversity, novelty, and serendipity re-ranking
- Explainable recommendation cards
- User authentication and saved taste profiles
- Real-time feedback and online model updates
- API authentication and rate limiting
- Docker deployment
- Automated unit and integration tests

---

## Troubleshooting

### `Model not found`

Run:

```bash
python backend/generate_dataset.py
python backend/train.py
```

### Port 5000 is already in use

Start Flask on another port:

```bash
set PORT=5001
python backend/app.py
```

PowerShell:

```powershell
$env:PORT="5001"
python backend/app.py
```

### Semantic search is unavailable

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

The first search may take longer because it downloads `BAAI/bge-base-en-v1.5`.

### Java client cannot connect

Make sure:

1. Flask is running
2. The URL is `http://127.0.0.1:5000`
3. The Java client is compiled and started in a separate terminal

---

## Viva and interview questions

**Why use a hybrid recommendation system?**

Content filtering handles movies with useful metadata and reduces the cold-start problem. Collaborative filtering captures preferences that are not obvious from genre or keywords.

**Why mean-centre ratings in item-item collaborative filtering?**

Mean-centering removes differences between strict and generous raters and makes similarity reflect preference rather than rating scale.

**Why is similarity shrinkage necessary?**

Two movies rated by the same two users can appear perfectly similar by coincidence. Shrinkage reduces similarity when the shared-user count is small.

**Why use alternating least squares?**

ALS is a closed-form optimization method for sparse matrix factorization. It is stable and efficient when user and item matrices are learned alternately.

**Why use RMSE and MAE?**

RMSE strongly penalizes large errors, while MAE gives the average absolute prediction error. Together they provide different views of rating accuracy.

**What is the difference between rating accuracy and recommendation ranking?**

A model can predict ratings accurately but still produce poor top-N recommendations. Ranking metrics such as Precision@10, Recall@10, NDCG, and hit rate evaluate the actual recommendation list.

**Why use a validation split?**

The validation split tunes model factors, regularization, thresholds, and popularity weight. The test split remains unseen until final reporting, reducing overfitting.

**What are the biggest current limitations?**

Cold-start users and movies, popularity bias, sparse matrices, historical-label bias, and the lack of real-time feedback are the main limitations.
