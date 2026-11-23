"""
Core recommendation engine (no external APIs - everything is computed from data/*.csv).

Three models live here
  1. Content-based  : TF-IDF vectors of genres + keywords + decade  -> cosine similarity
  2. Collaborative  : item-item *adjusted cosine* on the 1M user-rating matrix (+ shrinkage)
  3. Matrix factorisation ("SVD-style" latent factors, trained with ALS) -> rating prediction
and a Hybrid = alpha * content + (1-alpha) * collaborative  for "movies like X".
"""
import difflib, re, time
import numpy as np, pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer


# ----------------------------------------------------------------------------- data
def load_data(data_dir):
    movies = pd.read_csv(f"{data_dir}/movies.csv")
    ratings = pd.read_csv(f"{data_dir}/ratings.csv")
    users = pd.read_csv(f"{data_dir}/users.csv")
    movies["keywords"] = movies["keywords"].fillna("")
    return movies, ratings, users


def to_csr(ratings, n_users, n_items):
    """user x item sparse matrix (ids are 1-based in the files, 0-based inside)"""
    return sp.csr_matrix((ratings.rating.values.astype(np.float32),
                          (ratings.user_id.values - 1, ratings.movie_id.values - 1)), shape=(n_users, n_items))


# ----------------------------------------------------------------------------- matrix factorisation
class MatrixFactorization:
    """Biased latent-factor model  r_ui ~ mu + b_u + b_i + p_u . q_i   (ALS-WR training)."""

    def __init__(self, k=32, reg=0.1, iters=10, seed=0):
        self.k, self.reg, self.iters, self.seed = k, reg, iters, seed

    def fit(self, R):
        R = R.tocsr(); n_u, n_i = R.shape
        rows, cols = R.nonzero(); vals = np.asarray(R[rows, cols]).ravel()
        self.mu = float(vals.mean())
        # damped bias terms
        cnt_i = np.bincount(cols, minlength=n_i); sum_i = np.bincount(cols, weights=vals - self.mu, minlength=n_i)
        self.b_i = sum_i / (cnt_i + 10)
        cnt_u = np.bincount(rows, minlength=n_u); sum_u = np.bincount(rows, weights=vals - self.mu - self.b_i[cols], minlength=n_u)
        self.b_u = sum_u / (cnt_u + 10)
        resid = vals - self.mu - self.b_u[rows] - self.b_i[cols]
        E = sp.csr_matrix((resid, (rows, cols)), shape=R.shape); Et = E.T.tocsr()
        rng = np.random.default_rng(self.seed)
        self.P = rng.normal(0, .1, (n_u, self.k)); self.Q = rng.normal(0, .1, (n_i, self.k))
        for _ in range(self.iters):
            self._als(E, self.P, self.Q); self._als(Et, self.Q, self.P)
        return self

    def _als(self, M, X, Y):
        """solve for X (rows of M) with Y fixed:  (Y_u^T Y_u + reg*n_u I) x = Y_u^T r_u"""
        eye = np.eye(self.k)
        for u in range(M.shape[0]):
            s, e = M.indptr[u], M.indptr[u + 1]
            if s == e:
                continue
            Yu = Y[M.indices[s:e]]
            X[u] = np.linalg.solve(Yu.T @ Yu + self.reg * (e - s) * eye, Yu.T @ M.data[s:e])

    def predict_pairs(self, u, i):
        p = self.mu + self.b_u[u] + self.b_i[i] + np.einsum("ij,ij->i", self.P[u], self.Q[i])
        return np.clip(p, 1, 5)

    def predict_user(self, u):
        return np.clip(self.mu + self.b_u[u] + self.b_i + self.Q @ self.P[u], 1, 5)


# ----------------------------------------------------------------------------- engine
class Engine:
    SHRINK = 25.0  # similarity shrinkage: sim * n/(n+SHRINK), n = number of co-raters

    def __init__(self, movies, ratings, users, mf, pop_w=0.8):
        t0 = time.time()
        self.movies = movies.reset_index(drop=True)
        self.users = users
        self.N = len(movies); self.U = int(ratings.user_id.max())
        self.R = to_csr(ratings, self.U, self.N)                        # user x item
        self.mf = mf
        self.POP_W = pop_w
        self.genres = [g.split("|") for g in self.movies.genres]
        # ---- item statistics
        cnt = np.asarray((self.R > 0).sum(0)).ravel(); sm = np.asarray(self.R.sum(0)).ravel()
        gm = self.R.data.mean()
        self.n_ratings = cnt; self.avg = np.where(cnt > 0, sm / np.maximum(cnt, 1), gm)
        self.bayes = (sm + 20 * gm) / (cnt + 20)                         # IMDB-style weighted rating
        # ---- content model
        docs = [(" ".join(g.replace("-", "").replace("'", "").lower() + " " for g in gl) * 3) + " " + kw.replace("-", "_") + f" decade{y // 10}"
                for gl, kw, y in zip(self.genres, self.movies.keywords, self.movies.year)]
        self.tfidf = TfidfVectorizer(token_pattern=r"[A-Za-z0-9_']+", sublinear_tf=True)
        self.X = self.tfidf.fit_transform(docs).tocsr()                  # item x term (L2-normalised)
        self.terms = np.array(self.tfidf.get_feature_names_out())
        # ---- collaborative model (adjusted cosine = cosine of user-mean-centred ratings)
        R = self.R.tocsr().copy(); um = np.asarray(R.sum(1)).ravel() / np.maximum(np.diff(R.indptr), 1)
        R.data = R.data - np.repeat(um, np.diff(R.indptr))
        Rc = R.T.tocsr()                                                 # item x user (centred)
        norm = np.sqrt(np.asarray(Rc.multiply(Rc).sum(1)).ravel()) + 1e-9
        self.Cn = sp.diags(1 / norm) @ Rc                                # row-normalised
        self.B = (self.R > 0).astype(np.float32).T.tocsr()               # item x user (0/1)
        # ---- lookup tables
        self.title_norm = [self._norm(t) for t in self.movies.title]
        self.rank_pop = np.log1p(cnt)
        self.pop_pct = np.argsort(np.argsort(cnt)) / (self.N - 1)   # popularity percentile 0..1
        self.build_seconds = time.time() - t0

    # ------------------------------------------------------------------ search
    @staticmethod
    def _norm(s):
        return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("&", "and")).strip()

    def search(self, q, limit=8):
        q = self._norm(q)
        if not q:
            return []
        score = np.zeros(self.N)
        for i, t in enumerate(self.title_norm):
            if t == q: s = 3.0
            elif t.startswith(q): s = 2.0 + len(q) / len(t)
            elif q in t: s = 1.5 + len(q) / len(t)
            else:
                words = t.split()
                s = 1.0 + .2 * sum(w.startswith(qw) for qw in q.split() for w in words) / max(len(q.split()), 1) if any(w.startswith(qw) for qw in q.split() for w in words) else 0
                if s == 0 and len(q) > 3:
                    r = difflib.SequenceMatcher(None, q, t).ratio()
                    s = r if r > .62 else 0
            score[i] = s
        score = score + 0.02 * self.rank_pop / self.rank_pop.max()      # popular titles win ties
        top = np.argsort(-score)[:limit]
        return [self.card(i) for i in top if score[i] > .05]

    # ------------------------------------------------------------------ helpers
    def card(self, i, **extra):
        m = self.movies.iloc[i]
        d = dict(movie_id=int(m.movie_id), title=m.title, year=int(m.year), genres=self.genres[i],
                 avg_rating=round(float(self.avg[i]), 2), n_ratings=int(self.n_ratings[i]), is_real=bool(m.is_real))
        d.update(extra); return d

    def _content_scores(self, i):
        return (self.X @ self.X[i].T).toarray().ravel()

    def _cf_scores(self, i):
        sim = (self.Cn @ self.Cn[i].T).toarray().ravel()
        co = (self.B @ self.B[i].T).toarray().ravel()
        return sim * co / (co + self.SHRINK), co

    # ------------------------------------------------------------------ "movies like X"
    def similar(self, ids, mode="hybrid", n=12, alpha=.45, genre=None, year_min=None, year_max=None):
        """ids: list of 0-based item indices (1 movie or a 'taste profile' of several)."""
        trace = []; t = time.time()
        first = self.card(ids[0])
        trace.append(dict(step="Resolve movie", detail=f"Matched input to '{first['title']}' ({first['year']}) -> movie_id {first['movie_id']}"))
        content = np.zeros(self.N); collab = np.zeros(self.N); coraters = []
        for i in ids:
            content += self._content_scores(i)
        content /= len(ids)
        x = self.X[ids[0]]; top_terms = sorted(zip(self.terms[x.indices], x.data), key=lambda z: -z[1])[:6]
        t1 = time.time()
        trace.append(dict(step="Content-based (TF-IDF + cosine)", ms=round((t1 - t) * 1000, 1),
                          detail="Query vector top terms: " + ", ".join(f"{a} ({b:.2f})" for a, b in top_terms) +
                                 f". Cosine similarity computed against all {self.N:,} movies."))
        for i in ids:
            cf, co = self._cf_scores(i); collab += np.clip(cf, 0, None); coraters.append(int(self.B[i].sum()))
        collab /= len(ids)
        trace.append(dict(step="Collaborative (item-item adjusted cosine)", ms=round((time.time() - t1) * 1000, 1),
                          detail=f"{sum(coraters):,} users rated the query movie(s); each user's ratings were mean-centred, "
                                 f"then similarity = cosine of rating columns, shrunk by n/(n+{int(self.SHRINK)}) so rarely co-rated titles don't dominate."))
        cmax = max(collab.max(), 1e-9)
        collab_n = collab / cmax
        content_n = content / max(content.max(), 1e-9)
        if mode == "content": score = content
        elif mode == "collab": score = collab_n
        else: score = alpha * content_n + (1 - alpha) * collab_n
        trace.append(dict(step="Blend & filter", detail=f"mode={mode}" + (f", score = {alpha:.2f}*content + {1 - alpha:.2f}*collaborative" if mode == "hybrid" else "")
                          + (f", genre={genre}" if genre else "") + ". The query movie itself is removed."))
        mask = np.ones(self.N, bool); mask[ids] = False
        if genre: mask &= np.array([genre in g for g in self.genres])
        if year_min: mask &= self.movies.year.values >= year_min
        if year_max: mask &= self.movies.year.values <= year_max
        mask &= self.n_ratings >= 30
        score = score * (0.6 + 0.4 * self.pop_pct)          # mild popularity/quality prior
        s = np.where(mask, score, -1)
        order = np.argsort(-s)[:n]
        qg = set(g for i in ids for g in self.genres[i]); qk = set(k for i in ids for k in self.movies.keywords[i].split())
        out = []
        for i in order:
            if s[i] <= 0: continue
            shared = [g for g in self.genres[i] if g in qg]
            kws = [k for k in self.movies.keywords[i].split() if k in qk][:4]
            out.append(self.card(i, score=round(float(s[i]), 4), match=int(round(100 * min(1, s[i] / max(s[order[0]], 1e-9)))),
                                 content=round(float(content_n[i]), 3), collab=round(float(collab_n[i]), 3),
                                 shared_genres=shared, shared_keywords=kws))
        trace.append(dict(step="Rank top-N", ms=round((time.time() - t) * 1000, 1), detail=f"Sorted {int(mask.sum()):,} candidate movies by score and returned the best {len(out)}."))
        return dict(query=first, results=out, trace=trace, total_ms=round((time.time() - t) * 1000, 1))

    # ------------------------------------------------------------------ user based
    def user_info(self, uid):
        u = uid - 1; row = self.R[u]; idx = row.indices; r = row.data
        order = np.argsort(-r, kind="stable")
        gcount = {}
        for i, rv in zip(idx, r):
            if rv >= 4:
                for g in self.genres[i]: gcount[g] = gcount.get(g, 0) + 1
        meta = self.users[self.users.user_id == uid].iloc[0]
        return dict(user_id=uid, n_ratings=int(len(idx)), mean_rating=round(float(r.mean()), 2), gender=meta.gender, age=int(meta.age),
                    fav_genres=sorted(gcount.items(), key=lambda z: -z[1])[:5],
                    top_rated=[self.card(idx[j], your_rating=int(r[j])) for j in order[:6]])

    def recommend_user(self, uid, n=12, genre=None):
        t = time.time(); u = uid - 1
        pred = self.mf.predict_user(u)
        seen = self.R[u].indices
        # blend predicted rating with a small popularity prior (users rarely care about obscure titles)
        score = pred + self.POP_W * (self.rank_pop - self.rank_pop.mean()) / self.rank_pop.std()
        mask = np.ones(self.N, bool); mask[seen] = False; mask &= self.n_ratings >= 30
        if genre: mask &= np.array([genre in g for g in self.genres])
        s = np.where(mask, score, -9); order = np.argsort(-s)[:n]
        res = [self.card(i, predicted=round(float(pred[i]), 2)) for i in order]
        return dict(user=self.user_info(uid), results=res, total_ms=round((time.time() - t) * 1000, 1),
                    trace=[dict(step="Load user", detail=f"User {uid} has {len(seen)} ratings in the 1M-rating matrix."),
                           dict(step="Latent-factor prediction", detail=f"predicted = mu + b_user + b_item + p_user . q_item  for all {self.N:,} movies (k={self.mf.k} factors)."),
                           dict(step="Remove seen & rank", detail=f"Removed the {len(seen)} movies already rated, kept titles with >=30 ratings, returned best {len(res)}.")])

    def predict(self, uid, mid):
        u, i = uid - 1, mid - 1
        p = float(self.mf.predict_pairs(np.array([u]), np.array([i]))[0])
        actual = self.R[u, i]
        return dict(user_id=uid, movie=self.card(i), predicted=round(p, 2), actual=int(actual) if actual else None,
                    parts=dict(global_mean=round(self.mf.mu, 2), user_bias=round(float(self.mf.b_u[u]), 2), item_bias=round(float(self.mf.b_i[i]), 2),
                               interaction=round(float(self.mf.P[u] @ self.mf.Q[i]), 2)))

    def top_movies(self, genre=None, n=12):
        mask = np.ones(self.N, bool)
        if genre: mask &= np.array([genre in g for g in self.genres])
        s = np.where(mask & (self.n_ratings >= 100), self.bayes, -1)
        return [self.card(i) for i in np.argsort(-s)[:n]]
