"""
Core logging initialisation using Python's built-in logging module.

Provides a timed-rotating file handler and a console handler, both
configured from CosThetaConfigurator.

This module is independent of the Redis-based slave/master logger
infrastructure — it is used for direct Python logging in components
that do not route through Redis.
"""
import codecs
import logging
import logging.handlers
import os
import time
from typing import Optional

import regex as re

from utils.CosThetaPrintUtils import printBoldBlue, printBoldGreen, printBoldRed
from BaseUtils import get_project_root

from Configuration import *

CosThetaConfigurator.getInstance()

# Module-level initialisation guard
_logging_initialized: bool = False


class MyTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    TimedRotatingFileHandler that rotates at midnight and uses date-based filenames.
    """

    def __init__(self, dir_log: str) -> None:
        """
        Args:
            dir_log: Directory for log files.  Must end with ``os.sep``.
        """
        self.dir_log = dir_log
        filename = self.dir_log + time.strftime("%m%d%Y") + ".txt"
        logging.handlers.TimedRotatingFileHandler.__init__(
            self,
            filename,
            when='midnight',
            interval=1,
            backupCount=0,
            encoding=None,
        )

    def doRollover(self) -> None:
        """Rotate to a new file at midnight."""
        self.stream.close()

        self.baseFilename = self.dir_log + time.strftime("%m%d%Y") + ".txt"

        if self.encoding:
            self.stream = codecs.open(self.baseFilename, 'a', self.encoding)
        else:
            self.stream = open(self.baseFilename, 'a')

        self.rolloverAt += self.interval


def getCoreLoggingLevel(inputLevel: str) -> int:
    """
    Map a config-string log level to a ``logging`` module constant.

    Args:
        inputLevel: One of 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'.

    Returns:
        Corresponding ``logging`` constant; defaults to ``logging.WARN``.
    """
    return {
        'DEBUG':    logging.DEBUG,
        'INFO':     logging.INFO,
        'WARN':     logging.WARN,
        'WARNING':  logging.WARNING,
        'ERROR':    logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }.get(inputLevel, logging.WARN)


def initialiseLogging() -> bool:
    """
    Set up console and timed-rotating-file handlers on the root logger.

    Idempotent — returns True immediately if already initialised.

    Returns:
        True on success, False if cancelled by KeyboardInterrupt.

    Raises:
        Exception: Re-raises any unexpected error so the caller can decide
                   whether to abort or continue.
    """
    global _logging_initialized

    if _logging_initialized:
        return True

    try:
        root_logger = logging.getLogger('')
        root_logger.setLevel(logging.DEBUG)

        # ── console handler ───────────────────────────────────────────────────
        consoleLogLevel = getCoreLoggingLevel(
            CosThetaConfigurator.getInstance().getConsoleLoggingLevel()
        )
        consoleFormatter = logging.Formatter(
            CosThetaConfigurator.getInstance().getConsoleLoggingFormat()
        )
        console = logging.StreamHandler()
        console.setLevel(consoleLogLevel)
        console.setFormatter(consoleFormatter)
        root_logger.addHandler(console)
        printBoldBlue(f"Console logging level: {logging.getLevelName(consoleLogLevel)}")

        # ── file handler ──────────────────────────────────────────────────────
        fileFormatter = logging.Formatter(
            fmt=CosThetaConfigurator.getInstance().getFileLoggingFormat(),
            datefmt=CosThetaConfigurator.getInstance().getFileLoggingDateFormat(),
        )

        curr_time = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        log_dir   = CosThetaConfigurator.getInstance().getLoggingDirectory()
        app_name  = CosThetaConfigurator.getInstance().getApplicationName()
        suffix    = CosThetaConfigurator.getInstance().getFileLoggingSuffix()

        logFileName = f"{get_project_root()}/{log_dir}/{app_name}-{curr_time}.{suffix}"

        try:
            os.makedirs(os.path.dirname(logFileName), exist_ok=True)
        except Exception:
            # Fall back to project root if directory creation fails
            logFileName = f"{get_project_root()}/{app_name}-{curr_time}.{suffix}"

        filehandler = logging.handlers.TimedRotatingFileHandler(
            logFileName,
            when='midnight',
            interval=1,
            backupCount=CosThetaConfigurator.getInstance().getBackupLogsCount(),
        )
        filehandler.suffix   = ""
        filehandler.extMatch = re.compile(r"^\d{8}$")

        fileLoggingLevel = getCoreLoggingLevel(
            CosThetaConfigurator.getInstance().getFileLoggingLevel()
        )
        filehandler.setLevel(fileLoggingLevel)
        filehandler.setFormatter(fileFormatter)
        root_logger.addHandler(filehandler)

        printBoldBlue(f"File logging level: {logging.getLevelName(fileLoggingLevel)}")
        printBoldGreen(f"Log file: {filehandler.baseFilename}")

        # Root logger threshold = minimum of both handler levels
        root_logger.setLevel(min(consoleLogLevel, fileLoggingLevel))
        _logging_initialized = True
        return True

    except KeyboardInterrupt:
        printBoldRed("initialiseLogging() cancelled by user")
        return False
    except Exception as ex:
        printBoldRed(f"Unhandled error in initialiseLogging(): {ex}")
        raise


def reinitialiseLogging() -> bool:
    """
    Shut down and reinitialise the logging system.

    Useful when configuration changes at runtime.

    Returns:
        True on success, False if cancelled by KeyboardInterrupt.
    """
    global _logging_initialized

    try:
        logging.shutdown()
    except Exception as ex:
        printBoldRed(f"Could not shut down logging: {ex}")

    _logging_initialized = False
    printBoldBlue("Reinitialising logging …")
    return initialiseLogging()


def isLoggingInitialized() -> bool:
    """Return True if the logging system has been initialised."""
    return _logging_initialized