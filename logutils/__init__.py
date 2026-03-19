"""
Logging utilities package.

Provides a Redis-based distributed logging system with:
- SlaveLoggers: Run in application processes, send logs to Redis queues
- MasterLoggers: Run in dedicated process, consume from queues and output

Usage:
    # In application code
    from logutils.SlaveLoggers import SlaveConsoleLogger, SlaveFileLogger

    SlaveConsoleLogger.getInstance().logInfo("MyClass", "Application started")
    SlaveFileLogger.getInstance().logDebug("MyClass", "Debug information")

    # In dedicated logging process
    from logutils.CentralLoggers import startLoggers
    startLoggers()
"""

from logutils.Logger import Logger, LogLevel, MessageType
from logutils.SlaveLoggers import (
    SlaveConsoleLogger,
    SlaveFileLogger,
    stopSlaveLoggingThreads,
)
from logutils.CentralLoggers import (
    MasterConsoleLogger,
    MasterFileLogger,
    startLoggers,
)

__all__ = [
    'Logger',
    'LogLevel',
    'MessageType',
    'SlaveConsoleLogger',
    'SlaveFileLogger',
    'MasterConsoleLogger',
    'MasterFileLogger',
    'startLoggers',
    'stopSlaveLoggingThreads',
]