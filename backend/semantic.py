"""Local BGE semantic search for natural-language movie discovery."""
import hashlib
import os
import threading
import time

import numpy as np
import pandas as pd


MODEL_NAME = "BAAI/bge-base-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class SemanticSearch:
    def __init__(self, movies, data_dir, cache_dir):
        self.movies = movies.reset_index(drop=True)
        self.data_dir = data_dir
        self.cache_path = os.path.join(cache_dir, "bge_movie_embeddings.npz")
        self._lock = threading.Lock()
        self._model = None
        self._embeddings = None

    def _documents(self):
        movies = self.movies
        summaries = {}
        overview_path = os.path.join(self.data_dir, "movie_overviews.csv")
        if os.path.exists(overview_path):
            overview = pd.read_csv(overview_path)
            if not {"movie_id", "plot_summary"}.issubset(overview.columns):
                raise ValueError("movie_overviews.csv must contain movie_id and plot_summary columns")
            if overview["movie_id"].duplicated().any():
                raise ValueError("movie_overviews.csv contains duplicate movie_id values")
            known_ids = set(movies.movie_id)
            unknown_ids = set(overview.movie_id.dropna()) - known_ids
            if unknown_ids:
                raise ValueError("movie_overviews.csv contains movie_id values not present in movies.csv")
            summaries = dict(zip(overview.movie_id, overview.plot_summary.fillna("").astype(str)))

        docs = []
        has_summaries = False
        for row in movies.itertuples(index=False):
            summary = summaries.get(row.movie_id, "")
            if not summary and hasattr(row, "plot_summary"):
                summary = str(row.plot_summary) if pd.notna(row.plot_summary) else ""
            summary = summary.strip()
            has_summaries |= bool(summary)
            genres = str(row.genres).replace("|", ", ")
            keywords = str(row.keywords).strip()
            parts = [f"Movie: {row.title}.", f"Genres: {genres}."]
            if summary:
                parts.append(f"Plot: {summary}")
            if keywords:
                parts.append(f"Themes: {keywords}.")
            docs.append(" ".join(parts))
        return docs, has_summaries

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    def _index(self):
        if self._embeddings is not None:
            return self._embeddings, self._source

        docs, has_summaries = self._documents()
        source = "plot summaries and movie metadata" if has_summaries else "movie titles, genres, and keywords"
        fingerprint = hashlib.sha256((MODEL_NAME + "\0" + "\0".join(docs)).encode("utf-8")).hexdigest()
        if os.path.exists(self.cache_path):
            with np.load(self.cache_path, allow_pickle=False) as cache:
                if str(cache["fingerprint"].item()) == fingerprint:
                    self._embeddings = cache["embeddings"]
                    self._source = source
                    return self._embeddings, source

        model = self._load_model()
        embeddings = model.encode(
            docs, batch_size=64, show_progress_bar=True,
            convert_to_numpy=True, normalize_embeddings=True,
        ).astype(np.float32)
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        np.savez_compressed(self.cache_path, fingerprint=fingerprint, embeddings=embeddings)
        self._embeddings, self._source = embeddings, source
        return embeddings, source

    def search(self, query, limit=12):
        query = query.strip()
        if not query:
            raise ValueError("q must not be empty")

        with self._lock:
            started = time.time()
            embeddings, source = self._index()
            query_vector = self._load_model().encode(
                [QUERY_PREFIX + query], convert_to_numpy=True, normalize_embeddings=True,
            )[0]
            scores = embeddings @ query_vector
            order = np.argsort(-scores)[:limit]
            results = []
            for i in order:
                results.append(dict(movie_id=int(self.movies.iloc[i].movie_id),
                                    semantic_score=round(float(scores[i]), 4)))
            return dict(
                model=MODEL_NAME,
                source=source,
                results=results,
                total_ms=round((time.time() - started) * 1000, 1),
            )
