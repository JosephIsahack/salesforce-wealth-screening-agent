from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger
from config import load_config
from agent import WealthScoringAgent


def main():
    config = load_config()
    agent = WealthScoringAgent(config)

    logger.info(
        f"Wealth Scoring Agent starting — "
        f"poll interval: {config.poll_interval_seconds}s, "
        f"alert threshold: {config.high_value_threshold}"
    )

    # Run one cycle immediately on startup before the scheduler kicks in
    agent.run_cycle()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        agent.run_cycle,
        "interval",
        seconds=config.poll_interval_seconds,
        id="wealth_scoring_poll",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Agent stopped")


if __name__ == "__main__":
    main()
