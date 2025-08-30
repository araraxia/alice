
import os
import logging
from logging.handlers import TimedRotatingFileHandler

class Logger:
    def __init__(self,
        log_name: str,
        log_dir: str,
        log_file: str,
        format: str = "%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
        interval: int = 1,
        backup_count: int = 7,
        log_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        console_level: int = logging.DEBUG,
    ):
        """
        INFO: 20
        DEBUG: 10
        """
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        self.formatter = logging.Formatter(format)
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, log_file),
            when="midnight",
            interval=interval,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(self.formatter)
        file_handler.setLevel(file_level)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.formatter)
        console_handler.setLevel(console_level)

        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(log_level)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

        self.logger.debug("Logger initialized")

    def get_logger(self):
        return self.logger