#!/usr/bin/env bash
# One-command start (Linux/macOS):  ./run.sh
set -e; cd "$(dirname "$0")"
[ -f data/ratings.csv ] || python3 backend/generate_dataset.py
[ -f artifacts/model.pkl ] || python3 backend/train.py
python3 backend/app.py
