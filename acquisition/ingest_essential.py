"""Batch ingest expanded accelerator corpus — round 2.

YC is the dominant source of structured accelerator education. Other
accelerators (Techstars, 500 Global, Seedcamp, Antler) produce mostly
program/promotional content rather than curriculum lectures.

Run: .venv/bin/python ingest_essential.py
"""
import json
import os
import time

from founder_guide import Guide, load_dotenv
from founder_guide.transcript import default_live_transcript_provider

load_dotenv()

DB = os.path.expanduser("~/.cache/founder-guide/pilot.sqlite")

# Round 2: covers stages that were empty (team, pmf) and deepens others.
ESSENTIAL_R2 = [
    # pmf — was empty
    ("0LNQxT9LvM0", "How To Find Product Market Fit (David Rusenko)", "pmf"),
    # team — was empty
    ("uVhTvQXfibU", "How to Manage (Ben Horowitz, L15)", "team"),
    ("pkAum45ubWc", "How to Be a Great Founder (Reid Hoffman, L13)", "team"),
    # idea — deepen
    ("Jcuqq48CNj8", "Where Do Great Startup Ideas Come From? (Caldwell+Seibel)", "idea"),
    ("vDXkpJw16os", "How to Get and Test Startup Ideas (Michael Seibel)", "idea"),
    # validation — deepen
    ("MT4Ig2uqjTc", "How to Talk to Users (Eric Migicovsky, classic)", "validation"),
    ("8pNxKX1SUGE", "All About Pivoting (Dalton Caldwell)", "validation"),
    # mvp — deepen
    ("C27RVio2rOs", "Building Product (Michael Seibel)", "mvp"),
    ("6IFR3WYSBFM", "How to Build a Product I (Seibel, Huffman, Shear)", "mvp"),
    ("sr0UabJd8qE", "Doing Things that Don't Scale (L8)", "mvp"),
    # growth — deepen
    ("URiIsrdplbo", "How to Get Users and Grow (Alex Schultz, Facebook)", "growth"),
    ("lL6GdUHIBsM", "How to Set KPIs and Goals (Adora Cheung)", "growth"),
    ("bYf43D4nUPk", "Scaling Growth (Gustaf Alstromer)", "growth"),
]


def main() -> None:
    guide = Guide(db_path=DB)
    provider = default_live_transcript_provider()
    languages = ["en", "es"]
    results = []
    for video_id, title, stage in ESSENTIAL_R2:
        try:
            result = guide.ingest_video(provider, video_id, languages)
            results.append({
                "video_id": video_id,
                "title": title,
                "stage": stage,
                "status": "ok",
                "kind": result.transcript_kind,
                "segments": len(result.segments),
                "created": result.created,
            })
            print(f"  OK  {video_id} | {title} ({len(result.segments)} segs)")
        except Exception as exc:
            results.append({
                "video_id": video_id,
                "title": title,
                "stage": stage,
                "status": "error",
                "error": str(exc)[:120],
            })
            print(f"  ERR {video_id} | {title} | {exc}")
        time.sleep(1)
    print(json.dumps({
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "segments": sum(r.get("segments", 0) for r in results),
        "details": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
