"""One command to rebuild everything:  python scripts/build_all.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import build_docs, eval_rag, generate_data, pipeline, train  # noqa: E402


def main():
    generate_data.main()
    pipeline.main()
    build_docs.main()
    train.main()
    eval_rag.main()
    print("[build_all] done - start the app with: uvicorn app.main:app --port 8000")


if __name__ == "__main__":
    main()
