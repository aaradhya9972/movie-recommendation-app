"""
Train + evaluate everything and write the artefacts the web app / Java app read.
    python backend/train.py
Outputs: artifacts/model.pkl, artifacts/metrics.json, artifacts/stats.json, artifacts/graphs/*.png
"""
import json, os, pickle, sys, time
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

sys.path.insert(0, os.path.dirname(__file__))
from recsys import load_data, to_csr, MatrixFactorization, Engine

ROOT = os.path.join(os.path.dirname(__file__), "..")
ART = os.path.join(ROOT, "artifacts"); GR = os.path.join(ART, "graphs"); os.makedirs(GR, exist_ok=True)
K, REG, ITERS, LIKE = 20, 0.06, 12, 4     # defaults, replaced by validation tuning below
POP_W = 0.8                                # default, replaced by validation tuning below
rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))
mae = lambda a, b: float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))

# ---- chart style (matches the GUI) ------------------------------------------------------------
BG, FG, MUTE, AMB, TEAL, ROSE = "#0f1320", "#e8e6e1", "#8a90a6", "#f5b94a", "#4fd1c5", "#f0647a"
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "axes.edgecolor": "#2a3048",
                     "axes.labelcolor": FG, "text.color": FG, "xtick.color": MUTE, "ytick.color": MUTE, "axes.grid": True,
                     "grid.color": "#1f2538", "axes.spines.top": False, "axes.spines.right": False, "font.size": 11})
def save(fig, name): fig.tight_layout(); fig.savefig(os.path.join(GR, name), dpi=140); plt.close(fig)
def heat(cm, labels, title, name, fmt="d", cmap="YlOrBr"):
    fig, ax = plt.subplots(figsize=(5.6, 4.8)); ax.grid(False)
    im = ax.imshow(cm, cmap=cmap)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            v = cm[i, j]; ax.text(j, i, format(v, fmt), ha="center", va="center", fontsize=13, fontweight="bold",
                                  color=FG if v > cm.max() * .6 else "#10131f")
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels))); ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(title, color=AMB, pad=12); save(fig, name)

t00 = time.time()
movies, ratings, users = load_data(os.path.join(ROOT, "data"))
U, N = int(ratings.user_id.max()), len(movies)
print(f"[data] {len(ratings):,} ratings | {U:,} users | {N:,} movies")

# ---- 1. 70/15/15 split -------------------------------------------------------------------------
rng = np.random.default_rng(7)
split = rng.random(len(ratings))
train = ratings[split < .70].reset_index(drop=True)
val = ratings[(split >= .70) & (split < .85)].reset_index(drop=True)
test = ratings[split >= .85].reset_index(drop=True)
tu, ti, ty = test.user_id.values - 1, test.movie_id.values - 1, test.rating.values
vu, vi, vy = val.user_id.values - 1, val.movie_id.values - 1, val.rating.values
Rtr = to_csr(train, U, N)
print(f"[split] train={len(train):,}  validation={len(val):,}  test={len(test):,}")

# ---- 2. models on the training split ---------------------------------------------------------
# ---- validation hyperparameter tuning ---------------------------------------------------------
tune_rows = []
for k in [12, 20, 32]:
    for reg in [0.03, 0.06, 0.10]:
        for iterations in [12, 16, 20]:
            candidate = MatrixFactorization(k, reg, iterations).fit(Rtr)
            pred = candidate.predict_pairs(vu, vi)
            tune_rows.append(dict(k=k, reg=reg, iters=iterations, rmse=rmse(pred, vy), mae=mae(pred, vy)))
            print(f"[tune mf] k={k} reg={reg:.2f} iters={iterations} rmse={tune_rows[-1]['rmse']:.4f}")
best_tune = min(tune_rows, key=lambda r: r["rmse"])
K, REG, ITERS = int(best_tune["k"]), float(best_tune["reg"]), int(best_tune["iters"])
print(f"[tuned mf] k={K} reg={REG} iters={ITERS}")

threshold_rows = []
mf_validation = MatrixFactorization(K, REG, ITERS).fit(Rtr)
validation_predictions = mf_validation.predict_pairs(vu, vi)
validation_true = (vy >= LIKE).astype(int)
for threshold in [3.0, 3.25, 3.5, 3.75, 4.0]:
    cm = confusion_matrix(validation_true, (validation_predictions >= threshold).astype(int))
    tn, fp, fn, tp = cm.ravel()
    threshold_rows.append(dict(threshold=threshold, accuracy=(tn + tp) / cm.sum(), f1=2 * tp / (2 * tp + fp + fn)))
PRED_THRESHOLD = max(threshold_rows, key=lambda r: r["f1"])["threshold"]
print(f"[tuned threshold] threshold={PRED_THRESHOLD}")

t = time.time(); mf = MatrixFactorization(K, REG, ITERS).fit(Rtr); print(f"[mf] trained in {time.time() - t:.1f}s")
p_mf = mf.predict_pairs(tu, ti)
p_glob = np.full(len(ty), mf.mu)
p_bias = np.clip(mf.mu + mf.b_u[tu] + mf.b_i[ti], 1, 5)

# item-kNN (collaborative filtering) on a sample of test pairs
eng_tr = Engine(movies, train, users, mf)
samp = rng.choice(len(ty), 4000, replace=False); p_knn, um = [], np.asarray(Rtr.sum(1)).ravel() / np.maximum(np.diff(Rtr.indptr), 1)
for s in samp:
    u, i = tu[s], ti[s]; sim, _ = eng_tr._cf_scores(i); row = Rtr[u]; idx = row.indices
    nb = idx[np.argsort(-sim[idx])[:30]]; w = sim[nb]
    p_knn.append(np.clip(um[u] + (w @ (Rtr[u, nb].toarray().ravel() - um[u])) / (np.abs(w).sum() + 1e-9), 1, 5))
p_knn = np.array(p_knn)

models = {"Global mean": (p_glob, np.arange(len(ty))), "User+Item bias": (p_bias, np.arange(len(ty))),
          "Item-kNN (CF)": (p_knn, samp), "SVD / ALS (MF)": (p_mf, np.arange(len(ty)))}
model_rows = []
for name, (p, ix) in models.items():
    model_rows.append(dict(model=name, rmse=round(rmse(p if len(p) == len(ix) else p, ty[ix]), 4), mae=round(mae(p, ty[ix]), 4)))
print(pd.DataFrame(model_rows))

# ---- 3. confusion matrices (best model = MF) --------------------------------------------------
y_true = (ty >= LIKE).astype(int); y_pred = (p_mf >= PRED_THRESHOLD).astype(int)
cm2 = confusion_matrix(y_true, y_pred); tn, fp, fn, tp = cm2.ravel()
acc, prec, rec = (tp + tn) / cm2.sum(), tp / (tp + fp), tp / (tp + fn); f1 = 2 * prec * rec / (prec + rec)
auc = float(roc_auc_score(y_true, p_mf)); fpr, tpr, _ = roc_curve(y_true, p_mf)
cm5 = confusion_matrix(ty, np.clip(np.rint(p_mf), 1, 5).astype(int), labels=[1, 2, 3, 4, 5])
acc5 = float(np.trace(cm5) / cm5.sum()); within1 = float(np.mean(np.abs(np.rint(p_mf) - ty) <= 1))
print(f"[cm] acc={acc:.3f} prec={prec:.3f} rec={rec:.3f} f1={f1:.3f} auc={auc:.3f}")

# ---- 4. ranking quality: Precision/Recall/NDCG@10 -----------------------------------------------
users_s = rng.choice(np.where(np.diff(Rtr.indptr) >= 20)[0], 600, replace=False)
Rval = to_csr(val, U, N); Rte = to_csr(test, U, N)
cnt_tr = np.asarray((Rtr > 0).sum(0)).ravel(); logp = np.log1p(cnt_tr)
zp = (logp - logp.mean()) / logp.std()
def rank_eval(scorefn, rel_matrix, K_=10):
    P, R_, ND, HIT = [], [], [], []
    for u in users_s:
        rel = set(rel_matrix[u].indices[rel_matrix[u].data >= LIKE])
        if not rel: continue
        s = scorefn(u).copy(); s[Rtr[u].indices] = -9; s[cnt_tr < 30] = -9
        top = np.argpartition(-s, K_)[:K_]; top = top[np.argsort(-s[top])]
        hits = np.array([i in rel for i in top]); P.append(hits.mean()); R_.append(hits.sum() / len(rel))
        ND.append((hits / np.log2(np.arange(2, K_ + 2))).sum() / (1 / np.log2(np.arange(2, min(len(rel), K_) + 2))).sum()); HIT.append(hits.any())
    return dict(precision=round(float(np.mean(P)), 4), recall=round(float(np.mean(R_)), 4), ndcg=round(float(np.mean(ND)), 4), hit_rate=round(float(np.mean(HIT)), 4))
pop_tuning = []
for weight in [0.0, 0.4, 0.8, 1.2, 1.6, 2.0]:
    result = rank_eval(lambda u, w=weight: mf.predict_user(u) + w * zp, Rval)
    pop_tuning.append(dict(pop_w=weight, **result))
    print(f"[tune ranking] pop_w={weight:.1f} ndcg={result['ndcg']:.4f}")
POP_W = max(pop_tuning, key=lambda r: r["ndcg"])["pop_w"]
print(f"[tuned ranking] pop_w={POP_W}")
rk_rng = np.random.default_rng(1)
ranking = {"Random": rank_eval(lambda u: rk_rng.random(N), Rte), "Popularity": rank_eval(lambda u: logp, Rte),
           "SVD / ALS": rank_eval(lambda u: mf.predict_user(u), Rte),
           "SVD + popularity prior (served)": rank_eval(lambda u: mf.predict_user(u) + POP_W * zp, Rte)}
print(json.dumps(ranking, indent=1))

# ---- 5. effect of latent factors k --------------------------------------------------------------
ksweep = []
for k in [2, 4, 8, 12, 20, 32]:
    m = MatrixFactorization(k, REG, 8).fit(Rtr); ksweep.append(dict(k=k, rmse=round(rmse(m.predict_pairs(tu, ti), ty), 4)))
print(ksweep)

# ---- 6. dataset statistics ---------------------------------------------------------------------
g_cnt, g_sum = {}, {}
mg = ratings.merge(movies[["movie_id", "genres", "year"]], on="movie_id")
for g in sorted({x for gs in movies.genres for x in gs.split("|")}):
    sub = mg[mg.genres.str.contains(g, regex=False)]; g_cnt[g] = int(len(sub)); g_sum[g] = round(float(sub.rating.mean()), 3)
per_user = ratings.groupby("user_id").size(); per_movie = ratings.groupby("movie_id").size()
dec = mg.assign(decade=(mg.year // 10 * 10)).groupby("decade").size()
hist_bins = [0, 25, 50, 100, 200, 400, 800, 5000]
uh = pd.cut(per_user, hist_bins).value_counts().sort_index()
stats = dict(n_ratings=int(len(ratings)), n_users=U, n_movies=N, sparsity=round(1 - len(ratings) / (U * N), 4), mean_rating=round(float(ratings.rating.mean()), 3),
             rating_dist={int(k): int(v) for k, v in ratings.rating.value_counts().sort_index().items()},
             genre_counts=g_cnt, genre_avg=g_sum, decade_counts={int(k): int(v) for k, v in dec.items()},
             user_activity=[[f"{int(i.left) + 1}-{int(i.right)}", int(v)] for i, v in uh.items()],
             movie_long_tail=[int(x) for x in np.sort(per_movie.values)[::-1][::37]],
             gender={k: int(v) for k, v in users.gender.value_counts().items()},
             age={int(k): int(v) for k, v in users.age.value_counts().sort_index().items()},
             median_per_user=int(per_user.median()), max_per_user=int(per_user.max()))
metrics = dict(split=dict(train=int(len(train)), validation=int(len(val)), test=int(len(test))), params=dict(k=K, reg=REG, iters=ITERS, like_threshold=LIKE, pred_threshold=PRED_THRESHOLD, pop_w=POP_W),
               models=model_rows, confusion_binary=dict(matrix=cm2.tolist(), tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp), accuracy=round(float(acc), 4),
               precision=round(float(prec), 4), recall=round(float(rec), 4), f1=round(float(f1), 4), auc=round(auc, 4)),
               confusion_5=dict(matrix=cm5.tolist(), accuracy=round(acc5, 4), within_one_star=round(within1, 4)), ranking=ranking, k_sweep=ksweep,
               tuning=dict(mf=tune_rows, popularity=pop_tuning, threshold=threshold_rows))
json.dump(metrics, open(os.path.join(ART, "metrics.json"), "w"), indent=1); json.dump(stats, open(os.path.join(ART, "stats.json"), "w"), indent=1)

# ---- 7. graphs (PNG, for the report) ------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 4)); v = [stats["rating_dist"][i] for i in range(1, 6)]
ax.bar(range(1, 6), v, color=AMB, width=.65); ax.set_title("Rating distribution (1M ratings)", color=AMB); ax.set_xlabel("Stars"); ax.set_ylabel("Ratings")
[ax.text(i + 1, x, f"{x / 1e3:.0f}k", ha="center", va="bottom", color=FG) for i, x in enumerate(v)]; save(fig, "01_rating_distribution.png")
gs = sorted(g_cnt.items(), key=lambda z: z[1]); fig, ax = plt.subplots(figsize=(6.6, 5.2)); ax.barh([a for a, _ in gs], [b for _, b in gs], color=TEAL)
ax.set_title("Ratings per genre", color=AMB); ax.set_xlabel("Ratings"); save(fig, "02_genre_popularity.png")
fig, ax = plt.subplots(figsize=(6.4, 4)); ax.bar([a for a, _ in stats["user_activity"]], [b for _, b in stats["user_activity"]], color=ROSE)
ax.set_title("How many movies each user rated", color=AMB); ax.set_xlabel("Ratings per user"); ax.set_ylabel("Users"); save(fig, "03_user_activity.png")
fig, ax = plt.subplots(figsize=(6.4, 4)); ax.plot(np.sort(per_movie.values)[::-1], color=AMB, lw=2); ax.set_yscale("log")
ax.set_title("Long-tail of movie popularity", color=AMB); ax.set_xlabel("Movie rank"); ax.set_ylabel("Ratings (log)"); save(fig, "04_long_tail.png")
fig, ax = plt.subplots(figsize=(6.4, 4)); names = [r["model"] for r in model_rows]; vals = [r["rmse"] for r in model_rows]
bars = ax.bar(names, vals, color=[MUTE, MUTE, TEAL, AMB], width=.6); ax.set_ylim(.6, max(vals) + .1); ax.set_title("Model comparison - RMSE (lower is better)", color=AMB)
[ax.text(b.get_x() + b.get_width() / 2, v_, f"{v_:.3f}", ha="center", va="bottom") for b, v_ in zip(bars, vals)]; plt.setp(ax.get_xticklabels(), rotation=12); save(fig, "05_model_rmse.png")
heat(cm2, ["Dislike", "Like"], "Confusion matrix (like = rating >= 4)", "06_confusion_binary.png")
heat(np.round(cm5 / cm5.sum(1, keepdims=True), 2), [1, 2, 3, 4, 5], "Confusion matrix, 5 star classes (row-normalised)", "07_confusion_5class.png", fmt=".2f")
fig, ax = plt.subplots(figsize=(5.6, 4.6)); ax.plot(fpr, tpr, color=AMB, lw=2.5); ax.plot([0, 1], [0, 1], "--", color=MUTE)
ax.set_title(f"ROC curve  (AUC = {auc:.3f})", color=AMB); ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate"); save(fig, "08_roc_curve.png")
fig, ax = plt.subplots(figsize=(6.4, 4)); ax.plot([d["k"] for d in ksweep], [d["rmse"] for d in ksweep], "o-", color=TEAL, lw=2.5)
ax.set_title("RMSE vs number of latent factors (k)", color=AMB); ax.set_xlabel("k"); ax.set_ylabel("Test RMSE"); save(fig, "09_rmse_vs_k.png")
fig, ax = plt.subplots(figsize=(7.4, 4.2)); mn = ["precision", "recall", "ndcg", "hit_rate"]; w = .2
for j, (nm, d) in enumerate(ranking.items()): ax.bar(np.arange(4) + j * w, [d[m] for m in mn], w, label=nm)
ax.set_xticks(np.arange(4) + 1.5 * w); ax.set_xticklabels(["Precision@10", "Recall@10", "NDCG@10", "Hit-rate@10"]); ax.legend(frameon=False, fontsize=8); ax.set_title("Top-10 ranking quality", color=AMB); save(fig, "10_ranking_metrics.png")

# ---- 8. final model on ALL data -> serve ---------------------------------------------------------
t = time.time(); mf_full = MatrixFactorization(K, REG, ITERS).fit(to_csr(ratings, U, N)); eng = Engine(movies, ratings, users, mf_full, pop_w=POP_W)
with open(os.path.join(ART, "model.pkl"), "wb") as f: pickle.dump(eng, f, protocol=4)
print(f"[final] model on all data saved ({os.path.getsize(os.path.join(ART, 'model.pkl')) / 1e6:.0f} MB) in {time.time() - t:.1f}s | total {time.time() - t00:.0f}s")
