"""Entry point — CLI interface for the Instagram story scraper."""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zero2Sudo Story Harvester — capture Instagram story opportunities."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit (default if no flag given).",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on a recurring schedule (interval set by SCRAPE_INTERVAL_MINUTES).",
    )
    parser.add_argument(
        "--log",
        metavar="FILE",
        nargs="?",
        const=None,
        default=None,
        help="Append raw Instagram API JSON to a file (defaults to logs/raw.json if flag is given without a path).",
    )
    args = parser.parse_args()

    # Import here so config errors surface cleanly before anything else
    import config
    from scheduler import run_once, run_scheduled

    # Resolve log path: explicit file > default logs/raw.json if --log given > None
    log_path = None
    if "--log" in __import__("sys").argv:
        log_path = args.log or os.path.join(config.LOGS_DIR, "raw.json")
        os.makedirs(config.LOGS_DIR, exist_ok=True)

    if args.schedule:
        run_scheduled(log_path=log_path)
    else:
        run_once(log_path=log_path)


if __name__ == "__main__":
    main()
