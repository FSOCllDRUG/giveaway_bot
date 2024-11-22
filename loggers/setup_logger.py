import logging
import os
from logging.handlers import TimedRotatingFileHandler


def module_logger(logger_name, log_dir, log_filename, level=logging.WARNING, console=False, detail=True):
    log_dir = log_dir
    os.makedirs(log_dir, exist_ok=True)
    log_filename = f"{log_dir}/{log_filename}"
    handler = TimedRotatingFileHandler(log_filename, when="midnight", interval=1, backupCount=7)
    if detail:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.addHandler(handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)


# Usage
# setup_logger("aiogram", "logs_bot", "bot.log")
# setup_logger("sqlalchemy", "logs_db", "db.log")
