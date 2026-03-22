# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
Central / Master loggers that consume from Redis streams and perform actual I/O.

Key changes from the previous version
──────────────────────────────────────
- Each Redis record now carries TWO fields:
      "text"          – the formatted log line
      "message_type"  – integer MessageType sent by the slave logger

  MasterConsoleLogger reads message_type directly instead of scanning the
  text string for words like "PROBLEM" or "ISSUE".  This eliminates false
  positives and couples the display colour to the producer's intent.

- MasterFileLogger and MasterConsoleLogger no longer call self.start() in
  __init__; startLoggers() / main() is responsible for that, consistent with
  the pattern used by the slave loggers.
"""
import os
import time
import warnings
from threading import Thread
from typing import Optional, TextIO
import sys

from redis import Redis

from logutils.SlaveLoggers import SlaveConsoleLogger, SlaveFileLogger
from logutils.Logger import Logger, MessageType, LogLevel, get_print_fn
from logutils.AbstractSlaveLogger import TEXT_KEY, MESSAGE_TYPE_KEY
from utils.CosThetaFileUtils import createDirectory
from utils.CosThetaPrintUtils import (
    printBoldRed, getCurrentTime, printBoldBlue, printBoldGreen, printLight, printBoldYellow, printRed, printBlue, printBoldSeparator, printGreen, printPlain, printSeparator, printBold, printYellow
)

warnings.filterwarnings('ignore')

from Configuration import *

CosThetaConfigurator.getInstance()


class MasterFileLogger(Thread):
    """
    Master logger that consumes records from the file-logging Redis stream
    and writes them to a rotating log file.

    Responsibilities
    ────────────────
    - Create and open a timestamped log file on startup.
    - Consume (text, message_type) records from Redis.
    - Write the text field to disk; flush periodically.
    - Drain the queue fully before closing on graceful shutdown.
    """

    logSource: str = ""

    def __init__(self, **kwargs) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.kwargs = kwargs
        self.stopped: bool = False
        self.started: bool = False

        MasterFileLogger.logSource = getFullyQualifiedName(__file__, __class__)

        self.hostname: str = CosThetaConfigurator.getInstance().getRedisHost()
        self.port:     int = CosThetaConfigurator.getInstance().getRedisPort()
        self.loggingQ: str = CosThetaConfigurator.getInstance().getFileLoggingQueue()

        self.redisConnection: Optional[Redis] = None
        self.clientRedisConnected: bool = False

        self.loggingDirectory: str = (
            f"{get_project_root()}/{CosThetaConfigurator.getInstance().getLoggingDirectory()}"
        )
        createDirectory(self.loggingDirectory)

        self.fileName:   str = ""
        self.fileHandle: Optional[TextIO] = None

        self.connectToRedis()
        self.createLoggingFile()
        self.clearQueue()

    # ── Redis connection ──────────────────────────────────────────────────────

    def connectToRedis(self, forceRenew: bool = False) -> None:
        """Establish (or re-establish) the Redis connection."""
        if forceRenew:
            self.redisConnection = None
            self.clientRedisConnected = False

        if not self.clientRedisConnected:
            try:
                self.redisConnection = Redis(
                    self.hostname, self.port, retry_on_timeout=True
                )
                self.clientRedisConnected = True
            except Exception:
                self.clientRedisConnected = False
                SlaveConsoleLogger.getInstance().logCritical(
                    MasterFileLogger.logSource,
                    f'Could not get Redis connection (pid {os.getpid()})',
                    MessageType.ISSUE,
                )

    # ── file management ───────────────────────────────────────────────────────

    def createLoggingFile(self) -> None:
        """Open a new log file with a timestamp-based filename."""
        suffix = CosThetaConfigurator.getInstance().getFileLoggingSuffix()
        self.fileName = f"{self.loggingDirectory}/{getCurrentTime()}.{suffix}"
        try:
            self.fileHandle = open(self.fileName, 'a', encoding='utf-8')
        except Exception as e:
            SlaveConsoleLogger.getInstance().logError(
                MasterFileLogger.logSource,
                f"Could not create log file {self.fileName}: {e}",
                MessageType.ISSUE,
            )

    def _writeToFile(self, data: str) -> bool:
        if not self.fileHandle:
            return False
        try:
            self.fileHandle.write(data)
            return True
        except Exception as e:
            SlaveConsoleLogger.getInstance().logCritical(
                MasterFileLogger.logSource,
                f'Could not write to log file {self.fileName}: {e}',
                MessageType.PROBLEM,
            )
            self._safeCloseFile()
            self.createLoggingFile()
            return False

    def _flushFile(self) -> None:
        if self.fileHandle:
            try:
                self.fileHandle.flush()
                os.fsync(self.fileHandle.fileno())
            except Exception:
                pass

    def _safeCloseFile(self) -> None:
        if self.fileHandle:
            try:
                self.fileHandle.flush()
                os.fsync(self.fileHandle.fileno())
                self.fileHandle.close()
            except Exception:
                pass
            self.fileHandle = None

    # ── queue helpers ─────────────────────────────────────────────────────────

    def clearQueue(self) -> None:
        try:
            if self.redisConnection:
                self.redisConnection.xtrim(self.loggingQ, 0)
        except Exception:
            pass

    def _getMessageCount(self) -> int:
        try:
            if self.redisConnection:
                return self.redisConnection.xlen(self.loggingQ)
        except Exception:
            pass
        return 0

    def _getData(self) -> Optional[dict]:
        """
        Read one record from the Redis stream.

        Returns a dict with string keys TEXT_KEY and MESSAGE_TYPE_KEY,
        or None if the stream is empty or an error occurs.
        """
        try:
            if not self.redisConnection:
                return None

            resp = self.redisConnection.xread(
                {self.loggingQ: 0}, count=1, block=1000
            )
            if not resp:
                return None

            _key, messages = resp[0]
            last_id, raw = messages[0]

            decoded = {k.decode('utf-8'): v for k, v in raw.items()}
            self.redisConnection.xdel(self.loggingQ, last_id)
            return decoded

        except Exception as e:
            SlaveConsoleLogger.getInstance().logCritical(
                MasterFileLogger.logSource,
                f'Error reading from Redis: {e}',
                MessageType.PROBLEM,
            )
            self.connectToRedis(forceRenew=True)

        return None

    def _checkStopCommand(self) -> bool:
        try:
            if not self.redisConnection:
                return False
            from utils.RedisUtils import getStopCommandFromQueue
            _, shallStop = getStopCommandFromQueue(self.redisConnection)
            return shallStop
        except Exception as e:
            SlaveConsoleLogger.getInstance().logCritical(
                MasterFileLogger.logSource,
                f'Error checking stop command: {e}',
                MessageType.PROBLEM,
            )
            self.connectToRedis(forceRenew=True)
        return False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Signal shutdown; also stop both slave loggers."""
        self.stopped = True
        self.started = False
        # SlaveFileLogger.getInstance().stop()
        # SlaveConsoleLogger.getInstance().stop()

    def doWork(self) -> None:
        """
        Main loop — consume records and write text to the log file.

        Flushes to disk every ``flushAfter`` records.
        Drains the queue fully before returning.
        """
        count:      int = 0
        flushAfter: int = 3

        while not (self.stopped and self._getMessageCount() == 0):
            record = self._getData()    # xread blocks for up to 1000ms if empty

            if record and TEXT_KEY in record:
                text = record[TEXT_KEY]
                if isinstance(text, bytes):
                    text = text.decode('utf-8')
                text += "\n"

                if self._writeToFile(text):
                    count += 1
                    if count % flushAfter == 0:
                        self._flushFile()
                        count = 0

            if self._checkStopCommand():
                printBoldRed(f"Stop command received in {MasterFileLogger.logSource}")
                self.stop()

            # if self._getMessageCount() == 0:
            #     time.sleep(timeout)

        # ── graceful shutdown ─────────────────────────────────────────────────
        if self.fileHandle:
            try:
                self.fileHandle.write(
                    f"{getCurrentTime()} : Closing down MasterFileLogger\n"
                )
            except Exception:
                pass
        self._safeCloseFile()
        self.clearQueue()

    def run(self) -> None:
        if not self.started:
            self.started = True
            self.stopped = False
            # self.doWork(timeout=1)
            self.doWork()


class MasterConsoleLogger(Thread):
    """
    Master logger that consumes records from the console-logging Redis stream
    and prints them to stdout with appropriate colour.

    The display colour is determined by the ``message_type`` field in each
    record — sent by the slave logger at the point of logging.  The text
    string is never scanned for keywords to infer the type.
    """

    logSource: str = ""

    def __init__(self, **kwargs) -> None:
        Thread.__init__(self)
        self.daemon = True
        self.kwargs = kwargs
        self.stopped: bool = False
        self.started: bool = False

        MasterConsoleLogger.logSource = getFullyQualifiedName(__file__, __class__)

        self.hostname: str = CosThetaConfigurator.getInstance().getRedisHost()
        self.port:     int = CosThetaConfigurator.getInstance().getRedisPort()
        self.loggingQ: str = CosThetaConfigurator.getInstance().getConsoleLoggingQueue()

        self.redisConnection: Optional[Redis] = None
        self.clientRedisConnected: bool = False

        self.connectToRedis()
        self.clearQueue()

    # ── Redis connection ──────────────────────────────────────────────────────

    def connectToRedis(self, forceRenew: bool = False) -> None:
        if forceRenew:
            self.redisConnection = None
            self.clientRedisConnected = False

        if not self.clientRedisConnected:
            try:
                self.redisConnection = Redis(
                    self.hostname, self.port, retry_on_timeout=True
                )
                self.clientRedisConnected = True
            except Exception:
                self.clientRedisConnected = False
                printBoldRed(
                    f'Could not get Redis connection in {MasterConsoleLogger.logSource} '
                    f'(pid {os.getpid()})'
                )

    # ── queue helpers ─────────────────────────────────────────────────────────

    def clearQueue(self) -> None:
        try:
            if self.redisConnection:
                self.redisConnection.xtrim(self.loggingQ, 0)
        except Exception:
            pass

    def _getMessageCount(self) -> int:
        try:
            if self.redisConnection:
                return self.redisConnection.xlen(self.loggingQ)
        except Exception:
            pass
        return 0

    def _getData(self) -> Optional[dict]:
        """
        Read one record from the Redis stream.

        Returns a dict with string keys TEXT_KEY and MESSAGE_TYPE_KEY,
        or None if the stream is empty or an error occurs.
        """
        try:
            if not self.redisConnection:
                return None

            resp = self.redisConnection.xread(
                {self.loggingQ: 0}, count=1, block=1000
            )
            if not resp:
                return None

            _key, messages = resp[0]
            last_id, raw = messages[0]

            decoded = {k.decode('utf-8'): v for k, v in raw.items()}
            self.redisConnection.xdel(self.loggingQ, last_id)
            return decoded

        except Exception as e:
            printBoldRed(
                f"Error reading from Redis in {MasterConsoleLogger.logSource}: {e}"
            )
            self.connectToRedis(forceRenew=True)

        return None

    def _checkStopCommand(self) -> bool:
        try:
            if not self.redisConnection:
                return False
            from utils.RedisUtils import getStopCommandFromQueue
            _, shallStop = getStopCommandFromQueue(self.redisConnection)
            return shallStop
        except Exception as e:
            printBoldRed(
                f"Error checking stop command in {MasterConsoleLogger.logSource}: {e}"
            )
            self.connectToRedis(forceRenew=True)
        return False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Signal shutdown; also stop both slave loggers."""
        self.stopped = True
        self.started = False
        # SlaveConsoleLogger.getInstance().stop()
        # SlaveFileLogger.getInstance().stop()

    def doWork(self) -> None:
        """
        Main loop — consume records and print to console.

        Colour selection uses the message_type field from the record directly;
        no string scanning is performed.
        """
        while not (self.stopped and self._getMessageCount() == 0):
            record = self._getData()    # xread blocks for up to 1000ms if empty

            if record and TEXT_KEY in record:
                text = record[TEXT_KEY]
                if isinstance(text, bytes):
                    text = text.decode('utf-8')

                # ── colour from structured fields, not string parsing ──────────
                raw_type = record.get(MESSAGE_TYPE_KEY, MessageType.GENERAL)
                if isinstance(raw_type, bytes):
                    raw_type = raw_type.decode('utf-8')
                try:
                    message_type = int(raw_type)
                except (ValueError, TypeError):
                    import re as _re
                    m = _re.search(r':\s*(\d+)\s*>', str(raw_type))
                    message_type = int(m.group(1)) if m else int(MessageType.GENERAL)

                raw_level = record.get('log_level', LogLevel.INFO)
                if isinstance(raw_level, bytes):
                    raw_level = raw_level.decode('utf-8')
                try:
                    log_level = int(raw_level)
                except (ValueError, TypeError):
                    import re as _re
                    m = _re.search(r':\s*(\d+)\s*>', str(raw_level))
                    log_level = int(m.group(1)) if m else int(LogLevel.INFO)

                print_fn = get_print_fn(log_level, message_type)
                print_fn(text, includeTime=False)

            # if self._getMessageCount() == 0:
            #     time.sleep(timeout) # sleep 1 second (or 5 from run())

            if self._checkStopCommand():
                self.stop()

        self.clearQueue()

    def run(self) -> None:
        if not self.started:
            self.started = True
            self.stopped = False
            # self.doWork(timeout=5)
            self.doWork()


def startLoggers() -> None:
    """
    Instantiate both master loggers, start their threads, and block until done.

    Also primes the queues by logging a startup message through the slave
    loggers (prevents MasterFileLogger blocking indefinitely on the first
    xread when the queue is empty).
    """
    mcl = MasterConsoleLogger()
    mfl = MasterFileLogger()

    mcl.start()
    mfl.start()

    printBoldBlue("******************")
    printBoldBlue("Started Logging Server")
    printBoldBlue("******************")

    # Prime both queues
    SlaveConsoleLogger.getInstance().logInfo(
        MasterConsoleLogger.logSource,
        f"{MasterConsoleLogger.logSource} started",
        MessageType.SUCCESS,
    )
    SlaveFileLogger.getInstance().logInfo(
        MasterFileLogger.logSource,
        f"{MasterFileLogger.logSource} started",
        MessageType.SUCCESS,
    )

    mcl.join()
    mfl.join()
    sys.exit(0)
