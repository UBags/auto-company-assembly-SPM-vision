from abc import ABC, abstractmethod

from logutils.SlaveLoggers import *
from queue import *
from typing import Union, List, Sequence, TypeVar
from threading import Thread
from redis import Redis

from Configuration import *
from utils.RedisUtils import getStopCommandFromQueue

CosThetaConfigurator.getInstance()

class GenericQueueProcessor(Thread, ABC):

    redisHost = CosThetaConfigurator.getInstance().getRedisHost()
    redisPort = CosThetaConfigurator.getInstance().getRedisPort()
    logSource = getFullyQualifiedName(__file__)

    def __init__(self, name: str, consumer: Union[Thread, "GenericQueueProcessor", Any, None] = None, timeout : int = 1, sleepTime : float = 0.05, blocking : bool = True, monitorRedisQueueForStopping : bool = False, max_size=32, **kwargs):
        Thread.__init__(self)
        GenericQueueProcessor.logSource = getFullyQualifiedName(__file__, __class__)
        self.daemon = True
        self.switchOffDebug()
        self.name : str = name
        self.consumer : Union[Thread, "GenericQueueProcessor", Any, None] = consumer
        self.timeout : int = timeout
        self.sleepTime : float = sleepTime
        self.blocking : bool = blocking
        self.monitorRedisQueueForStopping : bool = monitorRedisQueueForStopping
        self.kwargs = kwargs
        self.max_size : int = max_size
        self.stopped : bool = False
        self.started : bool = False
        self.paused : bool = False
        self.processingQueue : Queue = Queue(self.max_size)
        self.redisConnectionForMonitoringStop : Union[Redis, None] = None
        self.clientRedisConnectedForMonitoringStop : bool = False
        if self.monitorRedisQueueForStopping:
            self.connectToRedisForMonitoringStop()
        if self.debugInit:
            logBoth('logDebug', GenericQueueProcessor.logSource,
                    f'Initialised GenericQueueProcessor.{self.name} in {GenericQueueProcessor.logSource}',
                    Logger.SUCCESS)

    def setDebug(self, debugInit : bool = False, debugAddItem : bool = False, debugGetItem : bool = False, debugProcessItem : bool = False, debugWork : bool = False, debugStop : bool = False, debugOtherExceptions : bool = False):
        self.debugInit : bool = debugInit
        self.debugAddItem : bool = debugAddItem
        self.debugGetItem : bool = debugGetItem
        self.debugProcessItem : bool = debugProcessItem
        self.debugWork : bool = debugWork
        self.debugStop : bool = debugStop
        self.debugOtherExceptions : bool = debugOtherExceptions

    def switchOffDebug(self):
        self.setDebug()

    def switchOnDebug(self):
        self.setDebug(debugInit = False, debugAddItem = False, debugProcessItem = False, debugWork = False, debugOtherExceptions = True)

    def connectToRedisForMonitoringStop(self, forceRenew = False):
        if forceRenew:
            self.redisConnectionForMonitoringStop = None
            self.clientRedisConnectedForMonitoringStop = False
        if not self.clientRedisConnectedForMonitoringStop:
            try:
                self.redisConnectionForMonitoringStop = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort, retry_on_timeout=True)
                self.clientRedisConnectedForMonitoringStop = True
            except Exception as e:
                self.clientRedisConnectedForMonitoringStop = False
                logBoth('logTakeNote', GenericQueueProcessor.logSource,
                        f'Could not get Redis Connection in {GenericQueueProcessor.logSource} due to {e}',
                        Logger.RISK)

    def setPause(self, value : bool = False):
        self.paused = value

    def getConsumer(self):
        return self.consumer

    def getStopped(self):
        return self.stopped

    def notifyConsumer(self, item : Any):
        if self.consumer is not None:
            if item is not None:
                self.consumer.addItem(item)

    def addItem(self, item: Any) -> Union[Any, None]:
        if self.stopped:
            # stop addition of items if stopped
            return None
        if self.paused:
            return None
        if item is not None:
            try:
                self.processingQueue.put_nowait(item)
                if self.debugAddItem:
                    logBoth('logDebug', GenericQueueProcessor.logSource,
                            f"Added item {type(item)} in Queue of GenericQueueProcessor.{self.name}",
                            Logger.RISK)
                return item
            except:
                return None  # lose the item, if the queue is full
        else:
            if self.debugAddItem:
                logBoth('logTakeNote', GenericQueueProcessor.logSource,
                        f"Did not add {'None' if item is None else 'item'} in Queue of GenericQueueProcessor.{self.name}",
                        Logger.RISK)
        return None

    def getItem(self, blocking=True) -> Union[Any, None]:
        # continue till the queue is emptied
        if self.paused:
            return None
        try:
            item = self.processingQueue.get(block=blocking, timeout=self.timeout)
            if self.debugGetItem:
                logBoth('logDebug', GenericQueueProcessor.logSource,
                        f"Got {'None' if item is None else type(item)} from Queue of GenericQueueProcessor.{self.name}",
                        Logger.ISSUE)
            return item
        except Exception:
            return None

    def stop(self):
        if self.debugStop:
            logBoth('logDebug', GenericQueueProcessor.logSource,
                    f'Received stop command in {GenericQueueProcessor.logSource}',
                    Logger.PROBLEM)
        self.stopped = True

    @abstractmethod
    def preWorkLoop(self):
        # override this method to do something
        return

    @abstractmethod
    def processItem(self, item : Any) -> Any :
        # override this method to do something with the item
        return False

    @abstractmethod
    def postWorkLoop(self):
        # override this method to do something
        return

    def doWork(self, blocking=True):
        self.preWorkLoop()
        while (not self.stopped) or (self.processingQueue.qsize() > 0):
            startOfProcessing = time.time()
            item = self.getItem(blocking)
            if item is not None:
                try:
                    processed_item = self.processItem(item) # implement processItem() with whatever processing you need to do
                    # Changed isinstance(self.consumer, GenericQueueProcessor) to (self.consumer, Thread) to ensure that other type of processors can also be made as consumer
                    # Recall that consumer type in class initialization is "Any"
                    if (self.consumer is not None) and isinstance(self.consumer, Thread) and (processed_item is not None):
                        # SlaveConsoleLogger.getInstance().logTakeNote(GenericQueueProcessor.logSource,
                        #                                              f"Adding processed_item as {'None' if processed_item is None else 'an startingImage'} in GenericQueueProcessor.{self.name}",
                        #                                              Logger.RISK)
                        try:
                            # This call is put inside try block to ensure that exception is caught if addItem does not exist
                            self.consumer.addItem(processed_item)
                        except:
                            pass
                    if (self.consumer is not None) and isinstance(self.consumer, list) and (processed_item is not None):
                        # SlaveConsoleLogger.getInstance().logTakeNote(GenericQueueProcessor.logSource,
                        #                                              f"Adding processed_item as {'None' if processed_item is None else 'an startingImage'} in GenericQueueProcessor.{self.name}",
                        #                                              Logger.RISK)
                        for aConsumer in self.consumer:
                            if isinstance(aConsumer, Thread):
                                try:
                                    # This call is put inside try block to ensure that exception is caught if addItem does not exist
                                    aConsumer.addItem(processed_item)
                                except:
                                    pass
                except Exception as e:
                    if self.debugOtherExceptions:
                        logBoth('logDebug', GenericQueueProcessor.logSource,
                                f"Did not process item due to Exception {e}",
                                Logger.RISK)
            else:
                if self.debugOtherExceptions:
                    logBoth('logTakeNote', GenericQueueProcessor.logSource,
                            f"Did not process {'None' if item is None else type(item)} in Queue of GenericQueueProcessor.{self.name}",
                            Logger.RISK)
            if self.monitorRedisQueueForStopping:
                try:
                    _, shallStop = getStopCommandFromQueue(self.redisConnectionForMonitoringStop)
                    if shallStop:
                        self.stop()
                except:
                    self.connectToRedisForMonitoringStop(True)
            if self.sleepTime > 0:
                endOfProcessing = time.time()
                processingTime = endOfProcessing - startOfProcessing
                sleep_Time = max(0.0, self.sleepTime - processingTime)
                if sleep_Time > 0.0:
                    time.sleep(sleep_Time)
        self.postWorkLoop()

    def run(self):
        if not self.started:
            self.started = True
            self.stopped = False
            self.paused = False
            self.doWork(blocking=self.blocking)