"""
Concrete slave logger implementations for file and console logging.

Both classes are singletons.  The singleton is fully constructed *and* its
background thread is started inside getInstance() so there is never a window
where the instance exists but the thread is not yet running.
"""
import threading
import warnings
from typing import Optional

from logutils.Logger import Logger, LogLevel, MessageType
from logutils.AbstractSlaveLogger import SlaveLogger
from utils.CosThetaPrintUtils import printRed

warnings.filterwarnings('ignore', '.*h264.*')

from Configuration import *

CosThetaConfigurator.getInstance()


class SlaveFileLogger(SlaveLogger):
    """
    Singleton slave logger for file logging.

    Enqueues formatted log records (text + message_type) to the file-logging
    Redis stream.  MasterFileLogger consumes that stream and writes to disk.
    """

    _instance: Optional['SlaveFileLogger'] = None
    _lock: threading.Lock = threading.Lock()
    logSource: str = "logutils.SlaveFileLogger"

    def __init__(self, max_size: int = 4096, **kwargs) -> None:
        if SlaveFileLogger._instance is not None:
            raise Exception(
                f"{getFullyQualifiedName(__file__, __class__)} is a singleton. "
                f"Use {getFullyQualifiedName(__file__, __class__)}.getInstance()"
            )
        SlaveLogger.__init__(self, max_size, **kwargs)
        SlaveFileLogger.logSource = getFullyQualifiedName(__file__, __class__)
        self.loggingQ = CosThetaConfigurator.getInstance().getFileLoggingQueue()
        self.name = SlaveFileLogger.logSource

    @classmethod
    def getInstance(cls) -> 'SlaveFileLogger':
        """
        Thread-safe singleton accessor.

        Constructs the instance and starts its background thread atomically
        inside the lock so callers always receive a fully-running logger.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = SlaveFileLogger()
                    instance.start()          # start before publishing
                    cls._instance = instance  # publish after start
        return cls._instance

    def logMessage(
        self,
        messageLogLevel: int,
        source: str,
        message: str,
        messageType: int = MessageType.GENERAL,
        stacklevel: int = 3,
    ) -> bool:
        """
        Format and enqueue a log record for file output.

        Args:
            messageLogLevel: Severity level (LogLevel int).
            source:          Originating class/module name.
            message:         Human-readable message text.
            messageType:     Display hint (MessageType int).
            stacklevel:      Frames to climb to find the original caller.
                             Default 3 = caller → logXxx() → logMessage() → makeLoggingMessage().
                             Pass 4 when logBoth() is in the chain.

        Returns:
            True if the record was enqueued, False if discarded.
        """
        SlaveFileLogger.updateLoggingLevels()

        if self.stopped:
            return False

        if messageLogLevel < SlaveFileLogger.currentFileLoggingLevel:
            return False

        formatted = self.makeLoggingMessage(
            Logger.getLoggingLevelText(messageLogLevel),
            source,
            message,
            messageType,
            stacklevel=stacklevel,
        )

        return self._enqueue(formatted, messageType, messageLogLevel)


class SlaveConsoleLogger(SlaveLogger):
    """
    Singleton slave logger for console logging.

    Enqueues formatted log records (text + message_type) to the console-logging
    Redis stream.  MasterConsoleLogger consumes that stream and prints to stdout.
    """

    _instance: Optional['SlaveConsoleLogger'] = None
    _lock: threading.Lock = threading.Lock()
    logSource: str = "logutils.SlaveConsoleLogger"

    def __init__(self, max_size: int = 4096, **kwargs) -> None:
        if SlaveConsoleLogger._instance is not None:
            raise Exception(
                f"{getFullyQualifiedName(__file__, __class__)} is a singleton. "
                f"Use {getFullyQualifiedName(__file__, __class__)}.getInstance()"
            )
        SlaveLogger.__init__(self, max_size, **kwargs)
        SlaveConsoleLogger.logSource = getFullyQualifiedName(__file__, __class__)
        self.loggingQ = CosThetaConfigurator.getInstance().getConsoleLoggingQueue()
        self.name = SlaveConsoleLogger.logSource

    @classmethod
    def getInstance(cls) -> 'SlaveConsoleLogger':
        """
        Thread-safe singleton accessor.

        Constructs the instance and starts its background thread atomically
        inside the lock so callers always receive a fully-running logger.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = SlaveConsoleLogger()
                    instance.start()          # start before publishing
                    cls._instance = instance  # publish after start
        return cls._instance

    def logMessage(
        self,
        messageLogLevel: int,
        source: str,
        message: str,
        messageType: int = MessageType.GENERAL,
        stacklevel: int = 3,
    ) -> bool:
        """
        Format and enqueue a log record for console output.

        Args:
            messageLogLevel: Severity level (LogLevel int).
            source:          Originating class/module name.
            message:         Human-readable message text.
            messageType:     Display hint (MessageType int).
            stacklevel:      Frames to climb to find the original caller.
                             Default 3 = caller → logXxx() → logMessage() → makeLoggingMessage().
                             Pass 4 when logBoth() is in the chain.

        Returns:
            True if the record was enqueued, False if discarded.
        """
        SlaveConsoleLogger.updateLoggingLevels()

        if self.stopped:
            printRed("SlaveConsoleLogger is stopped — message discarded")
            return False

        if messageLogLevel < SlaveConsoleLogger.currentConsoleLoggingLevel:
            return False

        formatted = self.makeLoggingMessage(
            Logger.getLoggingLevelText(messageLogLevel),
            source,
            message,
            messageType,
            stacklevel=stacklevel,
        )

        return self._enqueue(formatted, messageType, messageLogLevel)


def stopSlaveLoggingThreads() -> None:
    """
    Gracefully stop both slave logging threads.

    Logs a final WARNING before stopping so the shutdown is visible in the
    output streams.
    """
    SlaveFileLogger.getInstance().logWarning(
        SlaveFileLogger.logSource,
        f'Shutting down {SlaveFileLogger.logSource}',
        MessageType.RISK,
    )
    SlaveConsoleLogger.getInstance().logWarning(
        SlaveConsoleLogger.logSource,
        f'Shutting down {SlaveConsoleLogger.logSource}',
        MessageType.RISK,
    )
    SlaveFileLogger.getInstance().stop()
    SlaveConsoleLogger.getInstance().stop()

_VALID_LOG_METHODS = frozenset({   # ← add this constant at module level
    'logMessage', 'logDebug', 'logInfo', 'logWarning', 'logTakeNote', 'logError', 'logCritical', 'logTakeNote', 'logTakeAction', 'logConsiderAction'
})

def logBoth(
    level: str,
    source: str,
    message: str,
    messageType: int,
) -> None:
    """
    Log the same message to both the console and file slave loggers in one call.

    The call stack when using logBoth is one frame deeper than a direct call:
        caller → logBoth → logXxx → logMessage → makeLoggingMessage

    stacklevel=4 is passed so that the logged function name and line number
    always reflect the original call site, not this helper.

    Args:
        level:       Name of the log-level method to call, e.g. 'logInfo',
                     'logWarning', 'logError', 'logCritical', 'logDebug'.
        source:      Originating class/module name (passed through unchanged).
        message:     Human-readable message text.
        messageType: Display/colour hint (MessageType int).

    Example::

        from logutils.SlaveLoggers import logBoth
        from logutils.Logger import MessageType

        logBoth('logInfo',    src, "Server started",      MessageType.SUCCESS)
        logBoth('logWarning', src, "Retrying connection", MessageType.RISK)
        logBoth('logCritical', src, f"Fatal error: {e}",  MessageType.PROBLEM)
    """
    if level not in _VALID_LOG_METHODS:  # ← add this guard
        # raise ValueError(
        #     f"logBoth(): unknown level {level!r}. "
        #     f"Valid options: {sorted(_VALID_LOG_METHODS)}"
        # )
        printRed(f"logBoth(): unknown level {level!r}. Valid options: {sorted(_VALID_LOG_METHODS)}")
        return

    _STACKLEVEL = 4  # caller → logBoth → logXxx → logMessage → makeLoggingMessage
    getattr(SlaveConsoleLogger.getInstance(), level)(source, message, messageType, _STACKLEVEL)
    getattr(SlaveFileLogger.getInstance(),   level)(source, message, messageType, _STACKLEVEL)