"""
Logger module providing logging level constants and utility methods.
Uses IntEnum for type-safe log levels and message types.

Design notes:
- LogLevel uses standard severity-based naming (DEBUG → CRITICAL)
- MessageType is purely a display/colour hint; it is NOT parsed from message strings
- MessageType is transmitted as a structured field in the Redis payload, never re-parsed
"""
import threading
import warnings
from enum import IntEnum
from typing import Any, Callable, Optional

warnings.filterwarnings('ignore', '.*h264.*')

from Configuration import *

CosThetaConfigurator.getInstance()


class LogLevel(IntEnum):
    """
    Logging severity levels, ordered low → high.

    Maps to previous names as follows:
        DEBUG          ← DEBUG
        INFO           ← INFO
        WARNING        ← TAKENOTE       (unexpected but recoverable)
        ERROR          ← CONSIDERACTION (requires attention)
        CRITICAL       ← TAKEACTION     (requires immediate action)
    """
    DEBUG    = 1
    INFO     = 2
    WARNING  = 3
    ERROR    = 4
    CRITICAL = 5


class MessageType(IntEnum):
    """
    Display/colour hint for a log message.

    Purely cosmetic — used by MasterConsoleLogger to choose a print colour.
    Must be transmitted as a separate structured field; never inferred by
    scanning the formatted message string.
    """
    GENERAL = 1
    SUCCESS = 2
    RISK    = 3
    ISSUE   = 4
    PROBLEM = 5


# ── colour dispatch ───────────────────────────────────────────────────────────
#
# Returns the correct printXxx() function from CosThetaPrintUtils for a given
# (log_level, message_type) pair.  Import is deferred so Logger.py stays free
# of any dependency on CosThetaPrintUtils (which itself imports CosThetaColors).
#
# Rule matrix  (rows = LogLevel, cols = MessageType):
#
#              GENERAL   SUCCESS        RISK/ISSUE/PROBLEM
#  DEBUG       Light     Green          Red
#  INFO        Light     Green          Red
#  WARNING     Light     BoldGreen      Red
#  ERROR       Light     BoldGreen      Red
#  CRITICAL    Light     BoldBlue       BoldRed
#
# GENERAL always maps to printLight regardless of level (rules 1 & 2).

def get_print_fn(log_level: int, message_type: int) -> Callable[..., None]:
    """
    Return the appropriate ``printXxx`` function for a (log_level, message_type) pair.

    Both arguments are plain integers (LogLevel / MessageType values).
    The import of CosThetaPrintUtils is deferred to avoid circular imports.
    """
    from utils.CosThetaPrintUtils import (
        printLight, printGreen, printBoldGreen,
        printRed, printBoldRed, printBoldBlue,
    )

    # Rule 1 / 2 — GENERAL always light, regardless of severity
    if message_type == MessageType.GENERAL:
        return printLight

    if log_level == LogLevel.CRITICAL:
        # Rule 3 / 4
        if message_type == MessageType.SUCCESS:
            return printBoldBlue
        return printBoldRed                        # RISK / ISSUE / PROBLEM

    # DEBUG / INFO / WARNING / ERROR from here
    if message_type == MessageType.SUCCESS:
        if log_level == LogLevel.ERROR:
            return printBoldGreen                  # Rule 6  (ERROR + SUCCESS)
        return printGreen                          # Rule 8  (DEBUG / INFO / WARNING + SUCCESS)

    # RISK / ISSUE / PROBLEM at any non-CRITICAL level → Rule 5 / 7
    return printRed


# ── string ↔ LogLevel maps ────────────────────────────────────────────────────

_STR_TO_LEVEL: dict[str, LogLevel] = {
    'DEBUG':    LogLevel.DEBUG,
    'INFO':     LogLevel.INFO,
    'WARNING':  LogLevel.WARNING,
    'ERROR':    LogLevel.ERROR,
    'CRITICAL': LogLevel.CRITICAL,
    # Legacy aliases kept for backward-compatibility with config files
    'TAKE_NOTE':       LogLevel.WARNING,
    'CONSIDER_ACTION': LogLevel.ERROR,
    'TAKE_ACTION':     LogLevel.CRITICAL,
}

_LEVEL_TO_STR: dict[LogLevel, str] = {
    LogLevel.DEBUG:    'DEBUG',
    LogLevel.INFO:     'INFO',
    LogLevel.WARNING:  'WARNING',
    LogLevel.ERROR:    'ERROR',
    LogLevel.CRITICAL: 'CRITICAL',
}

# ── string ↔ MessageType maps ─────────────────────────────────────────────────

_STR_TO_MTYPE: dict[str, MessageType] = {
    'GENERAL': MessageType.GENERAL,
    'SUCCESS': MessageType.SUCCESS,
    'RISK':    MessageType.RISK,
    'ISSUE':   MessageType.ISSUE,
    'PROBLEM': MessageType.PROBLEM,
}

_MTYPE_TO_STR: dict[MessageType, str] = {
    MessageType.GENERAL: 'GENERAL',
    MessageType.SUCCESS: 'SUCCESS',
    MessageType.RISK:    'RISK',
    MessageType.ISSUE:   'ISSUE',
    MessageType.PROBLEM: 'PROBLEM',
}


class Logger:
    """
    Singleton Logger providing level constants and conversion utilities.

    Integer class attributes provide backward-compatible constants so that
    existing call-sites (``Logger.DEBUG``, ``Logger.PROBLEM`` etc.) continue
    to work without modification.
    """

    # ── severity level constants ──────────────────────────────────────────────
    DEBUG:    int = LogLevel.DEBUG
    INFO:     int = LogLevel.INFO
    WARNING:  int = LogLevel.WARNING
    ERROR:    int = LogLevel.ERROR
    CRITICAL: int = LogLevel.CRITICAL

    # Legacy aliases — kept so old call-sites don't break immediately
    TAKENOTE:       int = LogLevel.WARNING
    CONSIDERACTION: int = LogLevel.ERROR
    TAKEACTION:     int = LogLevel.CRITICAL

    # ── message type constants ────────────────────────────────────────────────
    GENERAL: int = MessageType.GENERAL
    SUCCESS: int = MessageType.SUCCESS
    RISK:    int = MessageType.RISK
    ISSUE:   int = MessageType.ISSUE
    PROBLEM: int = MessageType.PROBLEM

    logSource: Optional[str] = None
    _instance: Optional['Logger'] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        if Logger._instance is not None:
            raise Exception(
                f"{getFullyQualifiedName(__file__, __class__)} is a singleton. "
                f"Use {getFullyQualifiedName(__file__, __class__)}.getInstance()"
            )

    @classmethod
    def getInstance(cls) -> 'Logger':
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Logger()
                    cls.logSource = getFullyQualifiedName(__file__, cls)
        return cls._instance

    # ── level helpers ─────────────────────────────────────────────────────────

    @classmethod
    def getLoggingLevelInt(cls, inputLevel: str) -> int:
        """
        Convert a level string to its integer value.

        Accepts current names (DEBUG, INFO, WARNING, ERROR, CRITICAL) and
        legacy config names (TAKE_NOTE, CONSIDER_ACTION, TAKE_ACTION).

        Returns WARNING if the string is not recognised.
        """
        return _STR_TO_LEVEL.get(inputLevel, LogLevel.WARNING)

    @classmethod
    def getLoggingLevelText(cls, inputLevel: int) -> str:
        """
        Convert a level integer to its canonical string.

        Returns 'WARNING' for unrecognised values.
        """
        return _LEVEL_TO_STR.get(inputLevel, 'WARNING')

    # ── message-type helpers ──────────────────────────────────────────────────

    @classmethod
    def getMessageTypeText(cls, inputType: int) -> str:
        """
        Convert a MessageType integer to its string name.

        Returns 'GENERAL' for unrecognised values.
        """
        return _MTYPE_TO_STR.get(inputType, 'GENERAL')

    @classmethod
    def getMessageTypeInt(cls, inputType: str) -> int:
        """
        Convert a MessageType string to its integer value.

        Returns GENERAL for unrecognised values.
        """
        return _STR_TO_MTYPE.get(inputType, MessageType.GENERAL)