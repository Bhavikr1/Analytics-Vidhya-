"""Download the Stack Overflow Python Q&A dataset from Kaggle into ./data.

Requires Kaggle credentials (~/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY).
Alternatively, download manually from
https://www.kaggle.com/datasets/stackoverflow/pythonquestions
and place Questions.csv + Answers.csv in backend/data/.
"""

import shutil
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REQUIRED = ["Questions.csv", "Answers.csv"]


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if all((DATA_DIR / f).exists() for f in REQUIRED):
        print(f"Dataset already present in {DATA_DIR}")
        return

    try:
        import kagglehub
    except ImportError:
        sys.exit("kagglehub not installed: pip install kagglehub")

    print("Downloading stackoverflow/pythonquestions from Kaggle (~2 GB)...")
    path = Path(kagglehub.dataset_download("stackoverflow/pythonquestions"))
    print(f"Downloaded to cache: {path}")

    for name in REQUIRED + ["Tags.csv"]:
        src = path / name
        if src.exists():
            print(f"Copying {name} -> {DATA_DIR}")
            shutil.copy2(src, DATA_DIR / name)

    missing = [f for f in REQUIRED if not (DATA_DIR / f).exists()]
    if missing:
        sys.exit(f"Missing files after download: {missing}")
    print("Done.")


if __name__ == "__main__":
    main()
