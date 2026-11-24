"""
Builds or converts the dataset used by the project -> data/movies.csv, data/ratings.csv, data/users.csv.

Without arguments, it generates a synthetic 1,000,209-rating dataset. With --movielens,
it converts real MovieLens-1M files to the project's CSV schema:
    python backend/generate_dataset.py --movielens path/to/ml-1m
and they will be converted to the same CSV format.
"""
import argparse, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from movies_seed import REAL_MOVIES

GENRES = ["Action", "Adventure", "Animation", "Children's", "Comedy", "Crime", "Documentary",
          "Drama", "Fantasy", "Film-Noir", "Horror", "Musical", "Mystery", "Romance",
          "Sci-Fi", "Thriller", "War", "Western"]
N_USERS, N_MOVIES, N_RATINGS = 6040, 3700, 1_000_209
DATA = os.path.join(os.path.dirname(__file__), "..", "data")

ADJ = {
 "Action": "Furious Iron Last Final Rogue Savage Deadly Burning Silent Brutal Rapid Lethal Ultimate Shattered".split(),
 "Adventure": "Lost Hidden Golden Wild Distant Forgotten Endless Secret Uncharted Ancient Emerald".split(),
 "Animation": "Little Magical Tiny Brave Dancing Happy Curious Sparkling Jolly Bouncy".split(),
 "Children's": "Little Happy Friendly Magic Silly Sleepy Brave Tiny Merry Cheerful".split(),
 "Comedy": "Crazy Awkward Lucky Wild Big Accidental Perfect Weird Unexpected Messy".split(),
 "Crime": "Dirty Cold Crooked Midnight Black Broken Bloody Dark Hollow Quiet".split(),
 "Documentary": "Hidden Living Wild Untold Last Changing Blue Silent Vanishing".split(),
 "Drama": "Quiet Broken Long Distant Fragile Bitter Gentle Lonely Faded Restless".split(),
 "Fantasy": "Enchanted Crystal Silver Mythic Shadow Sacred Elder Starlit Cursed".split(),
 "Film-Noir": "Midnight Neon Smoky Rainy Velvet Shadowed Crooked Bitter".split(),
 "Horror": "Haunted Dark Whispering Cursed Hollow Wicked Rotting Screaming Sinister".split(),
 "Musical": "Dancing Golden Singing Glittering Midnight Electric Jazzy Rhythmic".split(),
 "Mystery": "Silent Missing Hidden Vanishing Secret Cryptic Forgotten Veiled".split(),
 "Romance": "Sweet Endless Summer Tender Eternal Secret Burning Golden Gentle".split(),
 "Sci-Fi": "Quantum Neon Orbital Binary Stellar Synthetic Galactic Cosmic Hyper Lunar".split(),
 "Thriller": "Cold Ruthless Fatal Zero Dead Final Shadow Blind Silent Mortal".split(),
 "War": "Fallen Iron Last Burning Silent Broken Distant Frozen Bloody".split(),
 "Western": "Dusty Lone Wild Rusty Last Red Outlaw Sundown Gritty".split(),
}
NOUN = {
 "Action": "Strike Protocol Fury Mission Vengeance Target Hunter Force Siege Blade Pursuit".split(),
 "Adventure": "Voyage Expedition Island Treasure Journey Frontier Quest Canyon Compass Horizon".split(),
 "Animation": "Adventures Friends Parade Garden Dreamers Kingdom Picnic Voyage Gang".split(),
 "Children's": "Adventures Friends Day Birthday Garden Dreamers Picnic Gang Treehouse".split(),
 "Comedy": "Weekend Wedding Mix-Up Roommates Road-Trip Holiday Reunion Blunder Setup".split(),
 "Crime": "Alley Syndicate Heist Verdict Informant Racket Underworld Ledger Getaway".split(),
 "Documentary": "Planet Ocean Story Frontier Reefs Legacy Mountains Voices Rivers".split(),
 "Drama": "Years Letters Home Silence Promise Seasons Inheritance Shore Echoes".split(),
 "Fantasy": "Realm Crown Sorcerer Prophecy Dragon Throne Grimoire Amulet Forest".split(),
 "Film-Noir": "Alibi City Dame Confession Streets Shadows Gamble Rain".split(),
 "Horror": "Manor House Ritual Whisper Asylum Hollow Woods Nightmare Séance".split(),
 "Musical": "Stage Serenade Rhapsody Encore Spotlight Melody Cabaret Ballroom".split(),
 "Mystery": "Case Clue Secret Disappearance Manuscript Riddle Witness Cipher".split(),
 "Romance": "Heart Promise Kiss Valentine Letters Embrace Affair Wedding Moonlight".split(),
 "Sci-Fi": "Protocol Colony Singularity Horizon Signal Paradox Nebula Android Orbit".split(),
 "Thriller": "Witness Deadline Trap Conspiracy Signal Hostage Fugitive Evidence Pursuit".split(),
 "War": "Front Trench Battalion Offensive Frontline Regiment Armistice Convoy".split(),
 "Western": "Trail Outlaw Frontier Saloon Canyon Gunslinger Territory Ranch".split(),
}
KW = {
 "Action": "chase explosion fight revenge heist mission agent",
 "Adventure": "journey treasure island quest explorer jungle map",
 "Animation": "cartoon talking-animals friendship colorful family songs",
 "Children's": "kids family friendship fun playful pets school",
 "Comedy": "humor funny friends mishap satire quirky wedding",
 "Crime": "detective gang murder police corruption heist underworld",
 "Documentary": "nature true-story interviews history science real-life",
 "Drama": "family emotional struggle redemption life relationships loss",
 "Fantasy": "magic wizard dragon kingdom prophecy myth sword",
 "Film-Noir": "detective femme-fatale shadows classic cynical rainy-city",
 "Horror": "ghost haunted monster slasher demon scary night",
 "Musical": "singing dance stage songs performance showbiz",
 "Mystery": "whodunit clues detective secrets twist investigation",
 "Romance": "love relationship heartbreak wedding passion couple",
 "Sci-Fi": "space future robot aliens technology time-travel dystopia",
 "Thriller": "suspense conspiracy chase twist killer tense",
 "War": "soldiers battle wwii army sacrifice front",
 "Western": "cowboy outlaw frontier desert gunfight sheriff",
}
# user taste clusters: which genres the cluster loves / hates
CLUSTERS = [
 {"Sci-Fi": 1.2, "Action": .8, "Thriller": .6, "Romance": -.7, "Musical": -.8},
 {"Romance": 1.2, "Comedy": .8, "Musical": .6, "Horror": -.8, "War": -.6},
 {"Horror": 1.3, "Thriller": .9, "Mystery": .7, "Children's": -.9, "Musical": -.6},
 {"Animation": 1.2, "Children's": 1.1, "Fantasy": .8, "Adventure": .6, "Horror": -1, "Film-Noir": -.5},
 {"Drama": 1.0, "War": .8, "Crime": .7, "Documentary": .6, "Action": -.3, "Children's": -.6},
 {"Comedy": 1.1, "Adventure": .5, "Children's": .4, "Drama": -.2, "War": -.5, "Horror": -.4},
 {"Crime": 1.2, "Mystery": 1.0, "Film-Noir": .9, "Thriller": .8, "Animation": -.7},
 {"Fantasy": 1.1, "Adventure": 1.0, "Sci-Fi": .6, "Action": .4, "Documentary": -.5},
 {"Western": 1.1, "War": .8, "Action": .6, "Drama": .4, "Musical": -.7, "Romance": -.4},
 {"Musical": 1.2, "Romance": .8, "Drama": .5, "Comedy": .4, "Horror": -.9, "Sci-Fi": -.5},
]


def build_movies(rng):
    rows, used = [], set()
    for line in REAL_MOVIES:
        t, y, g, k = line.split("|")
        rows.append(dict(title=t, year=int(y), genres=g.replace(",", "|"), keywords=k, is_real=1))
        used.add(t)
    gw = np.array([0.18, 0.11, 0.04, 0.05, 0.17, 0.07, 0.02, 0.28, 0.05, 0.01, 0.07, 0.03, 0.04, 0.14, 0.09, 0.14, 0.04, 0.02])
    gw = gw / gw.sum()
    while len(rows) < N_MOVIES:
        n_g = rng.choice([1, 2, 3], p=[.45, .42, .13])
        gs = list(rng.choice(GENRES, size=n_g, replace=False, p=gw))
        p = gs[0]
        title = f"The {rng.choice(ADJ[p])} {rng.choice(NOUN[p])}" if rng.random() < .6 else f"{rng.choice(ADJ[p])} {rng.choice(NOUN[p])}"
        year = int(np.clip(rng.normal(1996, 15), 1930, 2024))
        if title in used:
            title = f"{title} ({year})"
        if title in used:
            continue
        used.add(title)
        kws = []
        for g in gs:
            kws += list(rng.choice(KW[g].split(), size=3, replace=False))
        rows.append(dict(title=title, year=year, genres="|".join(gs), keywords=" ".join(dict.fromkeys(kws)), is_real=0))
    df = pd.DataFrame(rows)
    df.insert(0, "movie_id", np.arange(1, len(df) + 1))
    return df


def build_ratings(movies, rng):
    N = len(movies)
    G = np.zeros((N, len(GENRES)), np.float32)
    for i, gs in enumerate(movies.genres):
        for g in gs.split("|"):
            G[i, GENRES.index(g)] = 1
    Gn = G / np.sqrt(G.sum(1, keepdims=True))

    # movie properties
    real = movies.is_real.values == 1
    quality = rng.normal(0, .42, N) + .55 * real
    pop = np.exp(rng.normal(0, 1.15, N)) * np.where(real, 7.0, 1.0)         # long-tail popularity
    lat_item = rng.normal(0, 1, (N, 6))

    # users
    cl = np.zeros((len(CLUSTERS), len(GENRES)), np.float32)
    for c, d in enumerate(CLUSTERS):
        for g, v in d.items():
            cl[c, GENRES.index(g)] = v
    ucl = rng.integers(0, len(CLUSTERS), N_USERS)
    A = cl[ucl] + rng.normal(0, .30, (N_USERS, len(GENRES)))
    b_user = rng.normal(0, .38, N_USERS)
    lat_user = rng.normal(0, 1, (N_USERS, 6))

    # number of ratings per user: long-tailed, min 20, total = N_RATINGS
    raw = rng.lognormal(0, 1.05, N_USERS)
    counts = 20 + np.floor(raw / raw.sum() * (N_RATINGS - 20 * N_USERS)).astype(int)
    counts = np.minimum(counts, N - 50)
    diff = N_RATINGS - counts.sum()
    while diff != 0:
        idx = rng.integers(0, N_USERS, abs(diff))
        counts[idx] += np.sign(diff)
        counts = np.clip(counts, 20, N - 50)
        diff = N_RATINGS - counts.sum()

    us, it = [], []
    logpop = np.log(pop)
    for u in range(N_USERS):
        logits = logpop + 1.0 * (Gn @ A[u]) + rng.gumbel(size=N)       # Gumbel top-k == sampling w/o replacement
        chosen = np.argpartition(-logits, counts[u])[:counts[u]]
        us.append(np.full(counts[u], u)); it.append(chosen)
    us = np.concatenate(us); it = np.concatenate(it)

    affinity = np.einsum("ij,ij->i", A[us], Gn[it])
    latent = np.einsum("ij,ij->i", lat_user[us], lat_item[it]) / np.sqrt(6)
    score = 3.08 + b_user[us] + quality[it] + 1.0 * affinity + .35 * latent + rng.normal(0, .72, len(us))
    rating = np.clip(np.rint(score), 1, 5).astype(np.int8)
    ts = rng.integers(1_500_000_000, 1_730_000_000, len(us))
    ratings = pd.DataFrame(dict(user_id=us + 1, movie_id=it + 1, rating=rating, timestamp=ts))
    ratings = ratings.sample(frac=1, random_state=1).reset_index(drop=True)

    users = pd.DataFrame(dict(
        user_id=np.arange(1, N_USERS + 1),
        gender=rng.choice(["M", "F"], N_USERS, p=[.58, .42]),
        age=rng.choice([1, 18, 25, 35, 45, 50, 56], N_USERS, p=[.04, .18, .35, .20, .09, .08, .06])))
    return ratings, users


def from_movielens(path):
    """Convert real MovieLens-1M (ml-1m/*.dat) to our CSV schema."""
    m = pd.read_csv(os.path.join(path, "movies.dat"), sep="::", engine="python", names=["movie_id", "raw", "genres"], encoding="latin-1")
    m["year"] = m.raw.str.extract(r"\((\d{4})\)\s*$").astype(float).fillna(1990).astype(int)
    m["title"] = m.raw.str.replace(r"\s*\(\d{4}\)\s*$", "", regex=True)
    m["keywords"] = ""; m["is_real"] = 1
    r = pd.read_csv(os.path.join(path, "ratings.dat"), sep="::", engine="python", names=["user_id", "movie_id", "rating", "timestamp"])
    u = pd.read_csv(os.path.join(path, "users.dat"), sep="::", engine="python", names=["user_id", "gender", "age", "occ", "zip"])
    m = m.sort_values("movie_id").reset_index(drop=True)
    id_map = dict(zip(m["movie_id"], np.arange(1, len(m) + 1)))
    m["movie_id"] = np.arange(1, len(m) + 1)
    r["movie_id"] = r["movie_id"].map(id_map)
    return m[["movie_id", "title", "year", "genres", "keywords", "is_real"]], r, u[["user_id", "gender", "age"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--movielens", default=None); a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    if a.movielens:
        movies, ratings, users = from_movielens(a.movielens)
    else:
        rng = np.random.default_rng(42)
        movies = build_movies(rng)
        ratings, users = build_ratings(movies, rng)
    movies.to_csv(os.path.join(DATA, "movies.csv"), index=False)
    ratings.to_csv(os.path.join(DATA, "ratings.csv"), index=False)
    users.to_csv(os.path.join(DATA, "users.csv"), index=False)
    print(f"movies={len(movies):,}  users={ratings.user_id.nunique():,}  ratings={len(ratings):,}")
    print(ratings.rating.value_counts(normalize=True).sort_index().round(3).to_dict(), "mean", round(ratings.rating.mean(), 3))
