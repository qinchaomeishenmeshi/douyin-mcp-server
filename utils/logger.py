import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = setup_logger("douyin_downloader", "logs/douyin_downloader.log")
