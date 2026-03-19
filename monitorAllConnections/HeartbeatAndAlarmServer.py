import threading
from threading import Thread
import os
import winsound
from logutils.SlaveLoggers import *
import time
from BaseUtils import *
import sys

from Configuration import *

from utils.RedisUtils import readAlarmInHeartbeatServer, sendCombinedHeartbeatFromHeartbeatServerToIOServer, \
    sendHeartbeatsFromHeartbeatServerToFEServer, ALIVE, readDataInHeartbeatServerFromQRCodeServer, \
    readDataInHeartbeatServerFromCameraServer, readDataInHeartbeatServerFromIOServer, \
    readDataInHeartbeatServerFromDatabaseServer, readDataInHeartbeatServerFromFEServer, DEAD, \
    readAllHeartbeatsInHeartbeatServer

CosThetaConfigurator.getInstance()

from processors.GenericQueueProcessor import *

class HeartbeatAndAlarmServer(GenericQueueProcessor):

    logSource = getFullyQualifiedName(__file__)

    beepMessage = CosThetaConfigurator.getInstance().getHeartbeatBeepMessage()
    windows = CosThetaConfigurator.getInstance().isWindows()
    linux = CosThetaConfigurator.getInstance().isLinux()
    mac = CosThetaConfigurator.getInstance().isMac()
    wavDirectory = get_project_root() +"/wavs/"
    disconnectedSoundFile = f"{wavDirectory}Siren.wav"
    connectedSoundFile = f"{wavDirectory}System is ready.wav"
    badComponentSoundFile = f"{wavDirectory}BadComponent.wav"

    MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM: int = CosThetaConfigurator.getInstance().getMinimumContinuousDisconnectionsNeededToSendAlarm()

    def __init__(self, name: str = "HeartbeatServerAndAlarm", consumer: Any = None, timeout : int = 1, sleepTime : float = 0.00, max_size=8, **kwargs):

        GenericQueueProcessor.__init__(self, name=name, consumer=consumer, sleepTime=sleepTime, timeout=timeout,
                                       monitorRedisQueueForStopping=True, max_size=max_size, **kwargs)
        HeartbeatAndAlarmServer.logSource = getFullyQualifiedName(__file__, __class__)

        # self.connAlarmQ = CosThetaConfigurator.getInstance().getSoundQueue()
        self.redisConnectionQ = None
        self.clientRedisConnectedQ = False
        self.connectToRedis()
        logBoth('logInfo', HeartbeatAndAlarmServer.logSource, f"Started Heartbeat and Alarm Server", Logger.GENERAL)

        self.qrCodeServerConnectionStatus : bool = False
        self.cameraServerConnectionStatus: bool = False
        self.ioServerConnectionStatus: bool = False
        self.databaseServerConnectionStatus: bool = False
        self.frontendServerConnectionStatus: bool = False

        self.consecutiveQRCodeServerConnectionDown : int = 0
        self.consecutiveCameraServerConnectionStatusDown : int = 0
        self.consecutiveIOServerConnectionStatusDown : int = 0
        self.consecutiveDatabaseServerConnectionStatusDown : int = 0
        self.consecutiveFrontendServerConnectionStatusDown : int = 0

        self.launchConnectionAlarmMonitoringThread()
        self.launchThreadForBadComponentAlarm()
        logBoth('logCritical', HeartbeatAndAlarmServer.logSource, f"************", Logger.SUCCESS)
        logBoth('logCritical', HeartbeatAndAlarmServer.logSource, f"Started Connection and Alarm Monitoring Thread", Logger.SUCCESS)
        logBoth('logCritical', HeartbeatAndAlarmServer.logSource, f"************", Logger.SUCCESS)


        self.gapBetweenConnectionProblemAlarms : float = CosThetaConfigurator.getInstance().getGapBetweenConnectionAlarms() # secs
        self.alarmSoundedAtLeastOnceForCurrentDisconnection : bool = False
        self.lastTimeAlarmSoundedInSecs = time.time()
        # print(HeartbeatServerAndAlarm.disconnectedSoundFile)

    def connectToRedis(self, forceRenew = False):
        if forceRenew:
            self.redisConnectionQ = None
            self.clientRedisConnectedQ = False
        if not self.clientRedisConnectedQ:
            try:
                self.redisConnectionQ = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort, retry_on_timeout=True)
                self.clientRedisConnectedQ = True
            except:
                self.clientRedisConnectedQ = False
                logBoth('logTakeAction', HeartbeatAndAlarmServer.logSource, 'Could not get Redis Connection', Logger.PROBLEM)
                # pass


    def addItem(self, item: Any) -> Union[Any, None]:
        return super().addItem(HeartbeatAndAlarmServer.beepMessage)

    def clearQueue(self):
        self.processingQueue.queue.clear()

    # def launchConnectionAlarmMonitoringThread(self):
    #     objRef = self
    #     def monitorConnections():
    #         monitoringTimeGap = CosThetaConfigurator.getInstance().getCombinedHeartbeatConnectionStatusSleepInterval()
    #         logBoth('logTakeAction', HeartbeatAndAlarmServer.logSource, f'{monitoringTimeGap = }', Logger.PROBLEM)
    #
    #         counter : int = 0
    #         while not objRef.stopped:
    #             counter += 1
    #             startTime = time.time()
    #             try:
    #                 objRef.qrCodeServerConnectionStatus = readDataInHeartbeatServerFromQRCodeServer(objRef.redisConnectionQ)
    #                 objRef.cameraServerConnectionStatus = readDataInHeartbeatServerFromCameraServer(objRef.redisConnectionQ)
    #                 objRef.ioServerConnectionStatus = readDataInHeartbeatServerFromIOServer(objRef.redisConnectionQ)
    #                 objRef.databaseServerConnectionStatus = readDataInHeartbeatServerFromDatabaseServer(objRef.redisConnectionQ)
    #                 objRef.frontendServerConnectionStatus = readDataInHeartbeatServerFromFEServer(objRef.redisConnectionQ)
    #
    #                 if not objRef.qrCodeServerConnectionStatus:
    #                     objRef.consecutiveQRCodeServerConnectionDown += 1
    #                 else:
    #                     objRef.consecutiveQRCodeServerConnectionDown = 0
    #
    #                 if not objRef.cameraServerConnectionStatus:
    #                     objRef.consecutiveCameraServerConnectionStatusDown += 1
    #                 else:
    #                     objRef.consecutiveCameraServerConnectionStatusDown = 0
    #
    #                 if not objRef.ioServerConnectionStatus :
    #                     objRef.consecutiveIOServerConnectionStatusDown += 1
    #                 else:
    #                     objRef.consecutiveIOServerConnectionStatusDown = 0
    #
    #                 if not objRef.databaseServerConnectionStatus:
    #                     objRef.consecutiveDatabaseServerConnectionStatusDown += 1
    #                 else:
    #                     objRef.consecutiveDatabaseServerConnectionStatusDown = 0
    #
    #                 if not objRef.frontendServerConnectionStatus:
    #                     objRef.consecutiveFrontendServerConnectionStatusDown += 1
    #                 else:
    #                     objRef.consecutiveFrontendServerConnectionStatusDown = 0
    #
    #                 # printLight(f"{objRef.qrCodeServerConnectionStatus = }, {objRef.cameraServerConnectionStatus = }, {objRef.ioServerConnectionStatus = }, {objRef.databaseServerConnectionStatus =}, {objRef.frontendServerConnectionStatus =}")
    #                 maxDisconnectionNumber = max(objRef.consecutiveQRCodeServerConnectionDown, objRef.consecutiveCameraServerConnectionStatusDown, objRef.consecutiveIOServerConnectionStatusDown, objRef.consecutiveDatabaseServerConnectionStatusDown, objRef.consecutiveFrontendServerConnectionStatusDown)
    #                 if (maxDisconnectionNumber > 10) and ((maxDisconnectionNumber % 10) == 0):
    #                     logBoth('logInfo', HeartbeatAndAlarmServer.logSource,
    #                             f"consecutiveQRCodeServerDown = {objRef.consecutiveQRCodeServerConnectionDown}, consecutiveCameraServerDown = {objRef.consecutiveCameraServerConnectionStatusDown}, consecutiveIOServerDown = {objRef.consecutiveIOServerConnectionStatusDown}, consecutiveDatabaseServer = {objRef.consecutiveDatabaseServerConnectionStatusDown}, consecutiveFrontendServerDown = {objRef.consecutiveFrontendServerConnectionStatusDown}",
    #                             Logger.GENERAL)
    #
    #                 sendHeartbeatsFromHeartbeatServerToFEServer(redisConnection=objRef.redisConnectionQ,
    #                                                             cameraServerStatus=ALIVE if (objRef.consecutiveCameraServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM) else DEAD,
    #                                                             qrCodeServerStatus=ALIVE if (objRef.consecutiveQRCodeServerConnectionDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM) else DEAD,
    #                                                             ioServerStatus=ALIVE if (objRef.consecutiveIOServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM) else DEAD,
    #                                                             dbServerStatus=ALIVE if (objRef.consecutiveDatabaseServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM) else DEAD)
    #                 # allok = (objRef.qrCodeServerConnectionStatus and objRef.cameraServerConnectionStatus
    #                 #          and objRef.ioServerConnectionStatus)
    #                 # allok = allok and objRef.databaseServerConnectionStatus and objRef.frontendServerConnectionStatus
    #
    #                 allok = (objRef.consecutiveQRCodeServerConnectionDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM)
    #                 allok = allok and (objRef.consecutiveCameraServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM)
    #                 allok = allok and (objRef.consecutiveIOServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM)
    #                 allok = allok and (objRef.consecutiveDatabaseServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM)
    #                 allok = allok and (objRef.consecutiveFrontendServerConnectionStatusDown < HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM)
    #
    #                 sendCombinedHeartbeatFromHeartbeatServerToIOServer(redisConnection=objRef.redisConnectionQ, combinedConnectionStatus=ALIVE if allok else DEAD)
    #
    #                 # printBoldYellow(f"Current value of allok is {allok}")
    #
    #                 objRef.clearQueue()
    #
    #                 if not allok:
    #                     if not objRef.alarmSoundedAtLeastOnceForCurrentDisconnection:
    #                         objRef.addItem(HeartbeatAndAlarmServer.beepMessage)
    #                         objRef.alarmSoundedAtLeastOnceForCurrentDisconnection = True
    #                         objRef.lastTimeAlarmSoundedInSecs = time.time()
    #                     else:
    #                         currentTime = time.time()
    #                         if currentTime - objRef.lastTimeAlarmSoundedInSecs > objRef.gapBetweenConnectionProblemAlarms:
    #                             objRef.addItem(HeartbeatAndAlarmServer.beepMessage)
    #                             objRef.lastTimeAlarmSoundedInSecs = time.time()
    #                     if (maxDisconnectionNumber > 1) and ((maxDisconnectionNumber % 3) == 0):
    #                         logBoth('logTakeAction', HeartbeatAndAlarmServer.logSource,
    #                                 f'All connections are NOT simultaneously ok - connection status is {objRef.qrCodeServerConnectionStatus}, {objRef.cameraServerConnectionStatus}, {objRef.ioServerConnectionStatus}, {objRef.databaseServerConnectionStatus}, {objRef.frontendServerConnectionStatus}',
    #                                 Logger.PROBLEM)
    #                 else:
    #                     # objRef.clearQueue()
    #                     objRef.alarmSoundedAtLeastOnceForCurrentDisconnection = False
    #                     if counter % 50 == 0:
    #                         logBoth('logTakeNote', HeartbeatAndAlarmServer.logSource, 'All connections are ok', Logger.SUCCESS)
    #             except Exception as e:
    #                 logBoth('logTakeAction', HeartbeatAndAlarmServer.logSource, f'Problem in launchConnectionAlarmMonitoringThread due to {e}', Logger.PROBLEM)
    #                 objRef.connectToRedis()
    #             endTime = time.time()
    #             sleepTime = monitoringTimeGap - (endTime - startTime)
    #             if sleepTime > 0:
    #                 time.sleep(sleepTime)
    #     monitoringThread = threading.Thread(name=f"Connection Alarm Monitoring Thread", target=monitorConnections, args=(), daemon=True)
    #     monitoringThread.start()

    def launchConnectionAlarmMonitoringThread(self):
        objRef = self

        def monitorConnections():
            monitoringTimeGap = CosThetaConfigurator.getInstance().getCombinedHeartbeatConnectionStatusSleepInterval()
            logBoth('logInfo', HeartbeatAndAlarmServer.logSource,
                    f'Heartbeat monitoring interval: {monitoringTimeGap}s', Logger.GENERAL)

            counter: int = 0
            while not objRef.stopped:
                counter += 1
                startTime = time.monotonic()
                try:
                    # ── single multi-stream read replaces 5 sequential reads ──────
                    statuses = readAllHeartbeatsInHeartbeatServer(
                        objRef.redisConnectionQ,
                        block=int(monitoringTimeGap * 1000)  # budget = full interval
                    )

                    objRef.qrCodeServerConnectionStatus = statuses['qrcode']
                    objRef.cameraServerConnectionStatus = statuses['camera']
                    objRef.ioServerConnectionStatus = statuses['io']
                    objRef.databaseServerConnectionStatus = statuses['db']
                    objRef.frontendServerConnectionStatus = statuses['fe']

                    # ── update consecutive-down counters ─────────────────────────
                    def _update(current_status, counter_attr):
                        if not current_status:
                            setattr(objRef, counter_attr, getattr(objRef, counter_attr) + 1)
                        else:
                            setattr(objRef, counter_attr, 0)

                    _update(objRef.qrCodeServerConnectionStatus, 'consecutiveQRCodeServerConnectionDown')
                    _update(objRef.cameraServerConnectionStatus, 'consecutiveCameraServerConnectionStatusDown')
                    _update(objRef.ioServerConnectionStatus, 'consecutiveIOServerConnectionStatusDown')
                    _update(objRef.databaseServerConnectionStatus, 'consecutiveDatabaseServerConnectionStatusDown')
                    _update(objRef.frontendServerConnectionStatus, 'consecutiveFrontendServerConnectionStatusDown')

                    _MIN_ = HeartbeatAndAlarmServer.MINIMUM_CONSECUTIVE_DOWNS_NEEDED_FOR_ALARM

                    maxDisconnectionNumber = max(
                        objRef.consecutiveQRCodeServerConnectionDown,
                        objRef.consecutiveCameraServerConnectionStatusDown,
                        objRef.consecutiveIOServerConnectionStatusDown,
                        objRef.consecutiveDatabaseServerConnectionStatusDown,
                        objRef.consecutiveFrontendServerConnectionStatusDown,
                    )
                    if maxDisconnectionNumber > 10 and maxDisconnectionNumber % 10 == 0:
                        logBoth('logInfo', HeartbeatAndAlarmServer.logSource,
                                f"consecutiveDown: QR={objRef.consecutiveQRCodeServerConnectionDown}, "
                                f"Cam={objRef.consecutiveCameraServerConnectionStatusDown}, "
                                f"IO={objRef.consecutiveIOServerConnectionStatusDown}, "
                                f"DB={objRef.consecutiveDatabaseServerConnectionStatusDown}, "
                                f"FE={objRef.consecutiveFrontendServerConnectionStatusDown}",
                                Logger.GENERAL)

                    # ── send aggregated status to FE and IO ───────────────────────
                    sendHeartbeatsFromHeartbeatServerToFEServer(
                        redisConnection=objRef.redisConnectionQ,
                        cameraServerStatus=ALIVE if objRef.consecutiveCameraServerConnectionStatusDown < _MIN_ else DEAD,
                        qrCodeServerStatus=ALIVE if objRef.consecutiveQRCodeServerConnectionDown < _MIN_ else DEAD,
                        ioServerStatus=ALIVE if objRef.consecutiveIOServerConnectionStatusDown < _MIN_ else DEAD,
                        dbServerStatus=ALIVE if objRef.consecutiveDatabaseServerConnectionStatusDown < _MIN_ else DEAD,
                    )

                    allok = all([
                        objRef.consecutiveQRCodeServerConnectionDown < _MIN_,
                        objRef.consecutiveCameraServerConnectionStatusDown < _MIN_,
                        objRef.consecutiveIOServerConnectionStatusDown < _MIN_,
                        objRef.consecutiveDatabaseServerConnectionStatusDown < _MIN_,
                        objRef.consecutiveFrontendServerConnectionStatusDown < _MIN_,
                    ])

                    sendCombinedHeartbeatFromHeartbeatServerToIOServer(
                        redisConnection=objRef.redisConnectionQ,
                        combinedConnectionStatus=ALIVE if allok else DEAD,
                    )

                    objRef.clearQueue()

                    if not allok:
                        if not objRef.alarmSoundedAtLeastOnceForCurrentDisconnection:
                            objRef.addItem(HeartbeatAndAlarmServer.beepMessage)
                            objRef.alarmSoundedAtLeastOnceForCurrentDisconnection = True
                            objRef.lastTimeAlarmSoundedInSecs = time.time()
                        else:
                            if time.time() - objRef.lastTimeAlarmSoundedInSecs > objRef.gapBetweenConnectionProblemAlarms:
                                objRef.addItem(HeartbeatAndAlarmServer.beepMessage)
                                objRef.lastTimeAlarmSoundedInSecs = time.time()
                        if maxDisconnectionNumber > 1 and maxDisconnectionNumber % 3 == 0:
                            logBoth('logTakeAction', HeartbeatAndAlarmServer.logSource,
                                    f'Connections NOT all OK: '
                                    f'QR={objRef.qrCodeServerConnectionStatus}, '
                                    f'Cam={objRef.cameraServerConnectionStatus}, '
                                    f'IO={objRef.ioServerConnectionStatus}, '
                                    f'DB={objRef.databaseServerConnectionStatus}, '
                                    f'FE={objRef.frontendServerConnectionStatus}',
                                    Logger.PROBLEM)
                    else:
                        objRef.alarmSoundedAtLeastOnceForCurrentDisconnection = False
                        if counter % 50 == 0:
                            logBoth('logTakeNote', HeartbeatAndAlarmServer.logSource,
                                    'All connections are ok', Logger.SUCCESS)

                except Exception as e:
                    logBoth('logTakeAction', HeartbeatAndAlarmServer.logSource,
                            f'Problem in monitorConnections: {e}', Logger.PROBLEM)
                    objRef.connectToRedis()

                # ── precise sleep: subtract actual elapsed time ───────────────────
                elapsed = time.monotonic() - startTime
                sleepTime = monitoringTimeGap - elapsed
                if sleepTime > 0:
                    time.sleep(sleepTime)

        monitoringThread = threading.Thread(
            name="Connection Alarm Monitoring Thread",
            target=monitorConnections,
            args=(),
            daemon=True,
        )
        monitoringThread.start()

    def launchThreadForBadComponentAlarm(self):
        objRef = self
        def sniffForAlarm():
            while not objRef.stopped:
                try:
                    alarmSignalReceived = readAlarmInHeartbeatServer(objRef.redisConnectionQ)
                    if alarmSignalReceived:
                        if HeartbeatAndAlarmServer.linux:
                            os.system(
                                '( speaker-test -t sine -f 1500 >/dev/null) & pid=$! ; sleep 0.4s ; kill -9 $pid ')
                        #       check sudo apt install beep
                        #       Then, use os.system("beep -f 1500 -l 400")
                        elif HeartbeatAndAlarmServer.windows:
                            # for i in range(CosThetaConfigurator.getInstance().getBeeperRepeats()):
                            #     winsound.Beep(1500, 500)
                            #     time.sleep(0.5)
                            winsound.PlaySound(HeartbeatAndAlarmServer.badComponentSoundFile, winsound.SND_FILENAME)

                except:
                    objRef.connectToRedis(forceRenew=True)
                try:
                    time.sleep(1.0)
                except:
                    pass
        monitorAlarmThread = threading.Thread(name=f"Alarm Monitoring Thread", target=sniffForAlarm, args=(), daemon = True)
        monitorAlarmThread.start()

    def preWorkLoop(self):
        return

    def processItem(self, item : Any) -> Any :
        if HeartbeatAndAlarmServer.linux:
            os.system('( speaker-test -t sine -f 1500 >/dev/null) & pid=$! ; sleep 0.4s ; kill -9 $pid ')
        #       check sudo apt install beep
        #       Then, use os.system("beep -f 1500 -l 400")
        elif HeartbeatAndAlarmServer.windows:
            # for i in range(CosThetaConfigurator.getInstance().getBeeperRepeats()):
            #     winsound.Beep(1500, 500)
            #     time.sleep(0.5)
            winsound.PlaySound(HeartbeatAndAlarmServer.disconnectedSoundFile, winsound.SND_FILENAME)
        return None

    def postWorkLoop(self):
        return

def startHeartbeatAndAlarmServer():
    hdServer=HeartbeatAndAlarmServer()
    hdServer.start()
    logBoth('logInfo', HeartbeatAndAlarmServer.logSource, "Started HeartbeatAndAlarmServer", Logger.GENERAL)
    hdServer.join()
    sys.exit(0)

# testRedisConnection = Redis(CosThetaConfigurator.getInstance().getRedisHost(), CosThetaConfigurator.getInstance().getRedisPort(), retry_on_timeout=True)
# testRedisConnection.flushdb()
# clearQueues(testRedisConnection)
# startHeartbeatServerAndAlarm()