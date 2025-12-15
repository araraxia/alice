#!/usr/bin/env python3

import logging, os
from logging.handlers import TimedRotatingFileHandler

def setup_logger(app):
    logs_dir = "logs"
    log_name = "root.log"

    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    log_path = os.path.join(logs_dir, log_name)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s"
    )
    file_handler = TimedRotatingFileHandler(
        log_path, when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    app.logger.handlers = []
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG)

    app.logger.propagate = False
    app.logger.info("Alice logger initialized")

    # Set up waitress logger
    waitress_logger = logging.getLogger("waitress")
    waitress_logger.setLevel(logging.DEBUG)
    waitress_logger.propagate = False
    waitress_logger.handlers = []
    waitress_logger.addHandler(file_handler)
    waitress_logger.addHandler(console_handler)
    waitress_logger.setLevel(logging.DEBUG)

    waitress_logger.info("Alice waitress logger initialized")

    return app
