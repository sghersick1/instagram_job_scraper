"""Pipeline orchestration — run once or on a schedule."""

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from scraper import capture_stories
from extractor import extract
from normalizer import normalize
from storage import save


def run_once(log_path: str | None = None) -> None:
    """Execute the full pipeline once."""
    print("[pipeline] Starting story capture...")
    frames = capture_stories(log_path=log_path)

    if not frames:
        print("[pipeline] No story frames captured. Exiting.")
        return

    records: list[dict] = []
    for frame in frames:
        extraction = extract(frame)

        # Filter 1: no link sticker → not an internship/hackathon post, skip entirely
        if not extraction["links"]:
            print(f"[pipeline] No link sticker — skipping frame ({frame.account} @ {frame.captured_at})")
            continue

        print(f"[pipeline] Extracting: @{frame.account} @ {frame.captured_at} (link: {extraction['links'][0]})")
        record = normalize(
            account=frame.account,
            captured_at=frame.captured_at,
            raw_text=extraction["raw_text"],
            links=extraction["links"],
        )

        # Filter 2: Claude classified it as advice/other → skip
        if record.get("category") == "skip":
            print(f"[pipeline] Claude classified as 'skip' — discarding frame")
            continue

        records.append(record)

    print(f"[pipeline] Saving {len(records)} records...")
    save(records)
    print("[pipeline] Done.")


def run_scheduled(log_path: str | None = None) -> None:
    """Run the pipeline on a recurring schedule defined by SCRAPE_INTERVAL_MINUTES."""
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_once,
        trigger="interval",
        minutes=config.SCRAPE_INTERVAL_MINUTES,
        kwargs={"log_path": log_path},
        id="story_scraper",
    )
    print(
        f"[scheduler] Starting — will run every {config.SCRAPE_INTERVAL_MINUTES} minutes. "
        "Press Ctrl+C to stop."
    )
    run_once(log_path=log_path)
    scheduler.start()
