"""
Abstract base class for slave loggers that communicate with master loggers via Redis.

Key design decisions
────────────────────
1.  Structured Redis payload
    Each message is sent as two fields:
        "text"          – the formatted log line
        "message_type"  – the integer MessageType, so the consumer never needs
                          to infer it by scanning the text string.

2.  Stacklevel-based caller capture
    makeLoggingMessage() accepts a ``stacklevel`` parameter (default 3) that
    controls how many frames to climb.  Subclasses or wrappers that add an
    extra call layer simply pass stacklevel=4 (or higher) instead of the
    frame count being silently wrong.

3.  Severity-aware queue-full handling
    When the internal queue is full, DEBUG/INFO messages are silently dropped
    (expected under back-pressure), but WARNING and above are written directly
    to stderr so critical information is never lost.
"""
import inspect
import os
import sys
import threading
import time
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from queue import Queue, Full
from threading import Thread
from typing import Optional

from redis import Redis

from utils.CosThetaPrintUtils import printBoldRed
from logutils.Logger import Logger, LogLevel, MessageType

warnings.filterwarnings('ignore', '.*h264.*')

from Configuration import *

CosThetaConfigurator.getInstance()

# Redis payload field names
TEXT_KEY:         str = "text"
MESSAGE_TYPE_KEY: str = "message_type"


class SlaveLogger(Thread, ABC):
    """
    Abstract base class for slave loggers.

    Slave loggers run inside application processes and forward log records to
    Redis streams.  Master loggers (CentralLoggers.py) consume those streams
    and perform the actual I/O (file write / console print).

    Class-level attributes
    ──────────────────────
    currentFileLoggingLevel    – file logging threshold, refreshed from config
    currentConsoleLoggingLevel – console logging threshold, refreshed from config
    """

    currentFileLoggingLevel:    int = LogLevel.DEBUG
    currentConsoleLoggingLevel: int = LogLevel.DEBUG
    _lastTimeConfigLoaded: Optional[str] = None
    _configLock: threading.Lock = threading.Lock()
    logSource: str = ""

    def __init__(self, max_size: int = 4096, **kwargs) -> None:
        """
        Args:
            max_size: Maximum number of messages held in the internal queue
                      before back-pressure kicks in.
            **kwargs: Passed through to Thread (unused currently).
        """
        Thread.__init__(self)
        self.daemon = True
        self.kwargs = kwargs
        self.stopped: bool = False
        self.started: bool = False
        self.processingQueue: Queue = Queue(max_size)

        self.hostname: str = CosThetaConfigurator.getInstance().getRedisHost()
        self.port:     int = CosThetaConfigurator.getInstance().getRedisPort()

        SlaveLogger.logSource = getFullyQualifiedName(__file__, __class__)

        # Default queue — subclasses must override in their own __init__
        self.loggingQ: str = CosThetaConfigurator.getInstance().getFileLoggingQueue()

        self.redisConnection: Optional[Redis] = None
        self.clientRedisConnected: bool = False
        self.connectToRedis()

    # ── Redis connection ──────────────────────────────────────────────────────

    def connectToRedis(self, forceRenew: bool = False) -> bool:
        """
        Establish (or re-establish) the Redis connection.

        Args:
            forceRenew: Drop any existing connection and create a fresh one.
        """
        if forceRenew:
            self.redisConnection = None
            self.clientRedisConnected = False

        if not self.clientRedisConnected:
            try:
                self.redisConnection = Redis(
                    self.hostname,
                    self.port,
                    retry_on_timeout=True
                )
                self.clientRedisConnected = True
            except Exception as e:
                self.clientRedisConnected = False
                printBoldRed(
                    f'Could not get Redis connection in {SlaveLogger.logSource} '
                    f'(pid {os.getpid()}): {e}'
                )
        return self.clientRedisConnected

    # ── config / level refresh ────────────────────────────────────────────────

    @classmethod
    def updateLoggingLevels(cls) -> None:
        """Reload logging thresholds from config if the config file has changed."""
        with cls._configLock:
            currentConfigTime = CosThetaConfigurator.getLastTimeLoaded()
            if cls._lastTimeConfigLoaded != currentConfigTime:
                cls._lastTimeConfigLoaded = currentConfigTime
                cls.currentFileLoggingLevel = Logger.getLoggingLevelInt(
                    CosThetaConfigurator.getInstance().getFileLoggingLevel()
                )
                cls.currentConsoleLoggingLevel = Logger.getLoggingLevelInt(
                    CosThetaConfigurator.getInstance().getConsoleLoggingLevel()
                )

    # ── abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def logMessage(
        self,
        messageLogLevel: int,
        source: str,
        message: str,
        messageType: int,
        stacklevel: int = 3,
    ) -> bool:
        """
        Enqueue a log record for forwarding to Redis.

        Args:
            messageLogLevel: Severity level (LogLevel int).
            source:          Originating class/module name.
            message:         Human-readable message text.
            messageType:     Display hint (MessageType int).
            stacklevel:      Frames to climb to find the original caller.
                             Default 3 = caller → logXxx() → logMessage() → makeLoggingMessage().
                             Pass 4 when logBoth() is in the chain.

        Returns:
            True if the record was enqueued, False if it was discarded.
        """
        ...

    # ── public convenience wrappers ───────────────────────────────────────────

    def logDebug(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.GENERAL,
        stacklevel: int = 3,
    ) -> None:
        """Log at DEBUG severity."""
        if not self.stopped:
            self.logMessage(LogLevel.DEBUG, source, message, messageType, stacklevel)

    def logInfo(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.SUCCESS,
        stacklevel: int = 3,
    ) -> None:
        """Log at INFO severity."""
        if not self.stopped:
            self.logMessage(LogLevel.INFO, source, message, messageType, stacklevel)

    def logWarning(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.RISK,
        stacklevel: int = 3,
    ) -> None:
        """Log at WARNING severity (unexpected but recoverable)."""
        if not self.stopped:
            self.logMessage(LogLevel.WARNING, source, message, messageType, stacklevel)

    def logError(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.ISSUE,
        stacklevel: int = 3,
    ) -> None:
        """Log at ERROR severity (requires attention)."""
        if not self.stopped:
            self.logMessage(LogLevel.ERROR, source, message, messageType, stacklevel)

    def logCritical(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.PROBLEM,
        stacklevel: int = 3,
    ) -> None:
        """Log at CRITICAL severity (requires immediate action)."""
        if not self.stopped:
            self.logMessage(LogLevel.CRITICAL, source, message, messageType, stacklevel)

    # ── legacy aliases (backward-compat) ─────────────────────────────────────

    def logTakeNote(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.RISK,
        stacklevel: int = 3,
    ) -> None:
        """Alias for logWarning() — kept for backward-compatibility."""
        self.logWarning(source, message, messageType, stacklevel)

    def logConsiderAction(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.ISSUE,
        stacklevel: int = 3,
    ) -> None:
        """Alias for logError() — kept for backward-compatibility."""
        self.logError(source, message, messageType, stacklevel)

    def logTakeAction(
        self,
        source: str,
        message: str,
        messageType: int = MessageType.PROBLEM,
        stacklevel: int = 3,
    ) -> None:
        """Alias for logCritical() — kept for backward-compatibility."""
        self.logCritical(source, message, messageType, stacklevel)

    # ── message formatting ────────────────────────────────────────────────────

    def makeLoggingMessage(
        self,
        loggingLevel: str,
        source: str,
        message: str,
        messageType: int = MessageType.GENERAL,
        stacklevel: int = 3,
    ) -> str:
        """
        Build a formatted log line.

        Caller information (function name, line number) is obtained by
        climbing ``stacklevel`` frames up the call stack.  If you add a
        wrapper layer between the public log method and this function,
        increase stacklevel by 1 for each extra frame.

        Args:
            loggingLevel: String name of the severity level.
            source:       Source identifier embedded in the message.
            message:      The log body text.
            messageType:  MessageType int (clamped to valid range).
            stacklevel:   How many frames to climb to find the original caller.
                          Default 3 matches: caller → logXxx() → logMessage()
                          → makeLoggingMessage().

        Returns:
            Formatted log string (no trailing newline).
        """
        # Clamp messageType
        messageType = max(int(MessageType.GENERAL), min(int(messageType), int(MessageType.PROBLEM)))

        # ── caller info ───────────────────────────────────────────────────────
        func_name: str = ""
        lno: str = ""
        try:
            frame = inspect.currentframe()
            for _ in range(stacklevel):
                if frame is None:
                    break
                frame = frame.f_back
            if frame is not None:
                func_name = frame.f_code.co_name
                lno       = str(frame.f_lineno)
        except (AttributeError, TypeError):
            pass
        finally:
            del frame

        # ── timestamp ─────────────────────────────────────────────────────────
        msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
        dt, ms = msTime.split('.')
        ms_int = int(ms) // 1000
        currentTime = f'{dt}-{ms_int:03}'

        # ── assemble ──────────────────────────────────────────────────────────
        mtText      = Logger.getMessageTypeText(messageType)
        source_part = f"{source.strip()}." if source else ""
        func_part   = func_name.strip() if func_name else ""

        return (
            f'{currentTime} :  {loggingLevel}->{mtText}'
            f'->{source_part}{func_part}:{lno} :: {message}'
        )

    # ── internal queue helpers ────────────────────────────────────────────────

    def _enqueue(self, text: str, messageType: int, severity: int) -> bool:
        """
        Put a structured record onto the internal processing queue.

        The record is a dict with two keys:
            TEXT_KEY         – formatted log line
            MESSAGE_TYPE_KEY – integer MessageType

        Severity-aware back-pressure policy:
            DEBUG / INFO  → silently drop when full (expected under load)
            WARNING+      → write to stderr so the message is never lost

        Args:
            text:        Formatted log line.
            messageType: Integer MessageType for the consumer.
            severity:    Integer LogLevel used for the drop policy.

        Returns:
            True if enqueued, False if dropped.
        """
        record = {TEXT_KEY: text, MESSAGE_TYPE_KEY: int(messageType), 'log_level': int(severity)}
        try:
            self.processingQueue.put_nowait(record)
            return True
        except Full:
            if severity >= LogLevel.WARNING:
                # Never silently drop WARNING or above — write to stderr
                print(
                    f"[LOGQUEUE FULL – NOT DROPPED] {text}",
                    file=sys.stderr,
                    flush=True,
                )
            return False

    def grabRecordForRedis(self, block: bool = True, timeout: float = 0.05) -> Optional[dict]:
        """
        Retrieve the next record from the internal queue.

        Returns:
            A dict with TEXT_KEY and MESSAGE_TYPE_KEY, or None on timeout/empty.
        """
        try:
            return self.processingQueue.get(block=block, timeout=timeout)
        except Exception:
            return None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Signal the logger thread to drain remaining messages and exit."""
        self.stopped = True
        self.started = False

    def doWork(self, block: bool = True, timeout: float = 0.05) -> None:
        """
        Main work loop — drain the internal queue into the Redis stream.

        Continues until both ``stopped`` is True *and* the queue is empty,
        ensuring no messages are lost on graceful shutdown.

        Stop-command polling policy:
            Checked at whichever comes first —
              • every 50 messages processed, or
              • every 10 seconds elapsed since the last check.
        """
        from utils.RedisUtils import sendData, getStopCommandFromQueue
        _stop_check_interval = 50
        _stop_check_timeout = 10.0  # seconds
        _iteration = 0
        _last_stop_check = time.monotonic()

        while not self.stopped or self.processingQueue.qsize() > 0:
            record = self.grabRecordForRedis(block, timeout = timeout)

            if record is not None:
                try:
                    sendData(
                        self.redisConnection,
                        record,
                        self.loggingQ,
                        aProducer=SlaveLogger.logSource,
                    )
                except Exception:
                    self.connectToRedis(forceRenew=True)

                _iteration += 1

            # Check stop command at the earlier of: 50 messages or 10 seconds
            _time_elapsed = time.monotonic() - _last_stop_check
            if _iteration >= _stop_check_interval or _time_elapsed >= _stop_check_timeout:
                _iteration = 0
                _last_stop_check = time.monotonic()
                try:
                    _, shallStop = getStopCommandFromQueue(self.redisConnection)
                    if shallStop:
                        self.stop()
                except Exception:
                    self.connectToRedis(forceRenew=True)

    def run(self) -> None:
        """Thread entry point."""
        if not self.started:
            self.started = True
            self.stopped = False
            self.doWork(timeout=0.05)