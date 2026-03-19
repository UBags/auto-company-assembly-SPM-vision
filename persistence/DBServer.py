import sys
import time
import threading
import os
from typing import Union
from pathlib import Path
from datetime import datetime
from configparser import ConfigParser

import numpy as np
import psycopg2
from psycopg2 import Error
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pprint

from redis import Redis

# From persistence package
import persistence
from persistence.Persistence import (
    setDatabaseName,
    makeFoldersForImages,
    getDatabaseName,
    getSchemaName,
    getCurrentMode,
    getDataSubFolder,
    checkConnection,
    checkIfDatabaseExists,
    checkIfQRCodeExists,
    insertData,
    getFolderForKnuckleImages,
    getFolderForHubAndBottomBearingImages,
    getFolderForTopBearingImages,
    getFolderForNutAndPlateWasherImages,
    getFolderForSplitPinAndWasherImages,
    getFolderForCapImages,
    getFolderForBunkAndNoBunkImages,
    printAllVariables,
)

# From utils package
from utils.QRCodeHelper import getModel_LHSRHS_AndTonnage
from utils.CosThetaFileUtils import (
    getFileNameForSaving,
    saveFileWithFullPath,
)
from utils.RedisUtils import (
    readDataInDatabaseServerFromFEServer,
    sendHeartbeatFromDBServerToHeartbeatServer,
    getStopCommandFromQueue,
    validate_image,
    ALIVE,
    DEAD,
)

# From BaseUtils
from BaseUtils import (
    getFullyQualifiedName,
    getCurrentTime,
    getYMDHMSmFormatFromTimeDotTime,
)

from utils.CosThetaPrintUtils import (printBoldBlue,
                                      printBlue,
                                      printBoldGreen,
                                      printBoldRed,
                                      printBoldYellow
                                      )

# From logutils
from logutils.SlaveLoggers import (
    SlaveFileLogger,
    SlaveConsoleLogger,
    Logger,
    logBoth,
)

# From Configuration
from Configuration import CosThetaConfigurator

CosThetaConfigurator.getInstance()  # needs to be called to ensure that configurations are properly loaded


class DataPersistence():
    logSource = getFullyQualifiedName(__file__)

    def __init__(self, mode: str, username: str | None, **kwargs) -> None:
        super().__init__()
        self.mode: str = mode
        self.username: str = username
        DataPersistence.logSource = getFullyQualifiedName(__file__, __class__)
        setDatabaseName(self.mode)
        makeFoldersForImages(self.mode)
        # printBoldBlue(f"{getCurrentMode() = }, {getDatabaseName() = }, {getDataSubFolder() = }")
        # print(f"{getFolderForKnuckleImages() = }")
        self.kwargs = kwargs
        self.stopped: bool = False
        self.hostname: str = CosThetaConfigurator.getInstance().getRedisHost()
        self.port: int = CosThetaConfigurator.getInstance().getRedisPort()
        # printBoldYellow(f"Reached 1 in DataPersistence")
        self.redisConnection: Union[Redis, None] = None
        self.clientRedisConnected: bool = False
        self.heartbeatRedisConnection: Union[Redis, None] = None
        self.heartbeatRedisConnected: bool = False
        # printBoldYellow(f"Reached 2 in DataPersistence")
        self.connectToRedis(True)
        # printBoldYellow(f"Reached 3 in DataPersistence")
        self.startPersistenceAndHeartbeatThreads()
        self.currentModelName: str | None = None
        # printBoldYellow(f"Reached 6 in DataPersistence")
        # printBoldYellow(f"Reached 7 in DataPersistence")
        logBoth('logCritical', DataPersistence.logSource, f"************", Logger.SUCCESS)
        logBoth('logCritical', DataPersistence.logSource, "Started DB Server", Logger.SUCCESS)
        logBoth('logCritical', DataPersistence.logSource, f"************", Logger.SUCCESS)

        # printAllVariables()

    # def stop(self) -> None:
    #     self.stopped = True
    #     # printBoldRed("Stopping DB Server")
    #     print("DEBUG: Stop flag set to True")
    #
    #     # Add thread joining
    #     if hasattr(self, 'persistence_thread') and self.persistence_thread:
    #         print("DEBUG: Waiting for persistence thread to finish...")
    #         self.persistence_thread.join(timeout=5)
    #         print("DEBUG: Persistence thread finished")

    def stop(self) -> None:
        import sys

        logBoth('logInfo', DataPersistence.logSource, "stop() called", Logger.GENERAL)
        logBoth('logInfo', DataPersistence.logSource, f"Current stopped state: {self.stopped}", Logger.GENERAL)
        self.stopped = True
        logBoth('logInfo', DataPersistence.logSource, "Stop flag set to True", Logger.GENERAL)

        # List all active threads
        logBoth('logInfo', DataPersistence.logSource, f"Active threads before join: {threading.active_count()}",
                Logger.GENERAL)
        for t in threading.enumerate():
            logBoth('logInfo', DataPersistence.logSource,
                    f"  Thread: {t.name}, daemon={t.daemon}, alive={t.is_alive()}", Logger.GENERAL)

        # Join the main work thread
        if hasattr(self, 'threadForDoingMainWork') and self.threadForDoingMainWork:
            logBoth('logInfo', DataPersistence.logSource,
                    f"Waiting for threadForDoingMainWork to finish (alive={self.threadForDoingMainWork.is_alive()})...",
                    Logger.GENERAL)
            self.threadForDoingMainWork.join(timeout=5)
            if self.threadForDoingMainWork.is_alive():
                logBoth('logWarning', DataPersistence.logSource,
                        "threadForDoingMainWork did not terminate within timeout", Logger.ISSUE)
            else:
                logBoth('logInfo', DataPersistence.logSource, "threadForDoingMainWork finished", Logger.GENERAL)
        else:
            logBoth('logInfo', DataPersistence.logSource, "threadForDoingMainWork not found", Logger.GENERAL)

        # Join the heartbeat thread
        if hasattr(self, 'heartbeatThread') and self.heartbeatThread:
            logBoth('logInfo', DataPersistence.logSource,
                    f"Waiting for heartbeatThread to finish (alive={self.heartbeatThread.is_alive()})...",
                    Logger.GENERAL)
            self.heartbeatThread.join(timeout=5)
            if self.heartbeatThread.is_alive():
                logBoth('logWarning', DataPersistence.logSource,
                        "heartbeatThread did not terminate within timeout", Logger.ISSUE)
            else:
                logBoth('logInfo', DataPersistence.logSource, "heartbeatThread finished", Logger.GENERAL)
        else:
            logBoth('logInfo', DataPersistence.logSource, "heartbeatThread not found", Logger.GENERAL)

        # List remaining active threads
        logBoth('logInfo', DataPersistence.logSource, f"Active threads after join: {threading.active_count()}",
                Logger.GENERAL)
        for t in threading.enumerate():
            logBoth('logInfo', DataPersistence.logSource,
                    f"  Thread: {t.name}, daemon={t.daemon}, alive={t.is_alive()}", Logger.GENERAL)

    def connectToRedis(self, forceRenew=False) -> None:
        if forceRenew:
            self.redisConnection = None
            self.clientRedisConnected = False
            self.heartbeatRedisConnection = None
            self.heartbeatRedisConnected = False
        if not self.clientRedisConnected:
            try:
                self.redisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                self.clientRedisConnected = True
                SlaveFileLogger.getInstance().logTakeNote(DataPersistence.logSource,
                                                          f"Redis Connection in {DataPersistence.logSource} is {self.redisConnection} in process {os.getpid()}",
                                                          Logger.SUCCESS)
                SlaveConsoleLogger.getInstance().logTakeAction(DataPersistence.logSource,
                                                               f"Redis Connection in {DataPersistence.logSource} is {self.redisConnection} in process {os.getpid()}",
                                                               Logger.SUCCESS)
            except:
                self.clientRedisConnected = False
                SlaveFileLogger.getInstance().logTakeAction(DataPersistence.logSource,
                                                            f"Could not get Redis Connection in {DataPersistence.logSource} in process {os.getpid()}",
                                                            Logger.PROBLEM)
                SlaveConsoleLogger.getInstance().logTakeAction(DataPersistence.logSource,
                                                               f"Could not get Redis Connection in {DataPersistence.logSource} in process {os.getpid()}",
                                                               Logger.PROBLEM)
        if not self.heartbeatRedisConnected:
            try:
                self.heartbeatRedisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                self.heartbeatRedisConnected = True
                SlaveFileLogger.getInstance().logTakeNote(DataPersistence.logSource,
                                                          f"Redis Connection in {DataPersistence.logSource} is {self.heartbeatRedisConnection} in process {os.getpid()}",
                                                          Logger.SUCCESS)
                SlaveConsoleLogger.getInstance().logTakeAction(DataPersistence.logSource,
                                                               f"Redis Connection in {DataPersistence.logSource} is {self.heartbeatRedisConnection} in process {os.getpid()}",
                                                               Logger.SUCCESS)
            except:
                self.heartbeatRedisConnected = False
                SlaveFileLogger.getInstance().logTakeAction(DataPersistence.logSource,
                                                            f"Could not get Redis Connection for heartneat in {DataPersistence.logSource} in process {os.getpid()}",
                                                            Logger.PROBLEM)
                SlaveConsoleLogger.getInstance().logTakeAction(DataPersistence.logSource,
                                                               f"Could not get Redis Connection for heartneat in {DataPersistence.logSource} in process {os.getpid()}",
                                                               Logger.PROBLEM)

    def saveKnuckleImage(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForKnuckleImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForKnuckleImages()}{fName}"
            # printBoldYellow(f"Trying to save image to path {fName}")
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def saveHubAndBottomBearingImage(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForHubAndBottomBearingImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForHubAndBottomBearingImages()}{fName}"
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def saveTopBearingImage(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForTopBearingImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForTopBearingImages()}{fName}"
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def saveNutAndPlateWasherImage(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForNutAndPlateWasherImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForNutAndPlateWasherImages()}{fName}"
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def saveSplitPinAndWasherImages(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForSplitPinAndWasherImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForSplitPinAndWasherImages()}{fName}"
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def saveCapImage(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForCapImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForCapImages()}{fName}"
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def saveBunkAndNoBunkImage(self, image: Union[np.ndarray, None]):
        if validate_image(image):
            fName = getFileNameForSaving()
            if self.currentModelName is not None:
                fName = f"{getFolderForBunkAndNoBunkImages()}{self.currentModelName}/{fName}"
            else:
                fName = f"{getFolderForBunkAndNoBunkImages()}{fName}"
            saveFileWithFullPath(image, fName)
            return fName
        return ""

    def doWork(self) -> None:
        SlaveFileLogger.getInstance().logTakeNote(DataPersistence.logSource,
                                                  f"In DBServer, starting doWork",
                                                  Logger.GENERAL)
        SlaveConsoleLogger.getInstance().logTakeNote(DataPersistence.logSource,
                                                     f"In DBServer, starting doWork",
                                                     Logger.SUCCESS)
        # printBoldYellow(f"Starting doWork() in DataPersistence")
        savedRecords: int = 0
        while not self.stopped:
            # time.sleep(0.5)
            time.sleep(5)
            if self.stopped:
                logBoth('logInfo', DataPersistence.logSource, "doWork detected stop flag, exiting", Logger.GENERAL)
                break
            try:
                genuineDataReceived = False
                try:
                    (genuineDataReceived, timeOfMessage, qrCode,
                     knucklePicture, knuckleCheckResult, knuckleCheckDatetime,
                     hubAndBottomBearingPicture, hubAndBottomBearingCheckResult, hubAndBottomBearingCheckDatetime,
                     topBearingPicture, topBearingCheckResult, topBearingCheckDatetime,
                     nutAndPlateWasherPicture, nutAndPlateWasherCheckResult, nutAndPlateWasherCheckDatetime,
                     tighteningTorque1, tighteningTorque1Result, tighteningTorque1Datetime,
                     freeRotationDone, freeRotationDatetime,
                     componentPressBunkPicture, componentPressBunkCheckResult, componentPressBunkCheckDatetime,
                     componentPressDone, componentPressDoneDatetime,
                     noBunkPicture, noBunkCheckResult, noBunkCheckDatetime,
                     tighteningTorque2, tighteningTorque2Result, tighteningTorque2Datetime,
                     splitPinAndWasherPicture, splitPinAndWasherCheckResult, splitPinAndWasherCheckDatetime,
                     capPicture, capCheckResult, capCheckDatetime,
                     capPressBunkPicture, capPressBunkCheckResult, capPressBunkCheckDatetime,
                     capPressDone, capPressDoneDatetime,
                     freeRotationTorque1, freeRotationTorque1Result, freeRotationTorque1Datetime,
                     overallResult) = readDataInDatabaseServerFromFEServer(redisConnection=self.redisConnection)
                except Exception as e:
                    logBoth('logWarning', DataPersistence.logSource,
                            f"Encountered exception {e} in readDataInDatabaseServerFromFEServer()", Logger.ISSUE)

                # printBoldYellow(f"Read data in doWork() of DataPersistence")

                if genuineDataReceived:
                    model, lhs_rhs, tonnage = getModel_LHSRHS_AndTonnage(qrCode)
                    self.currentModelName = model
                    # printBoldGreen(f"Successfully fetched data from the queue in doWork()")
                    knucklePictureFile: str = self.saveKnuckleImage(knucklePicture)
                    hubAndBottomBearingPictureFile: str = self.saveHubAndBottomBearingImage(hubAndBottomBearingPicture)
                    topBearingPictureFile: str = self.saveTopBearingImage(topBearingPicture)
                    nutAndPlateWasherPictureFile: str = self.saveNutAndPlateWasherImage(nutAndPlateWasherPicture)
                    bunkForComponentPressFile: str = self.saveBunkAndNoBunkImage(componentPressBunkPicture)
                    noBunkFile: str = self.saveBunkAndNoBunkImage(noBunkPicture)
                    splitPinAndWasherFile: str = self.saveSplitPinAndWasherImages(splitPinAndWasherPicture)
                    capPictureFile = self.saveCapImage(capPicture)
                    bunkCapPressFile: str = self.saveBunkAndNoBunkImage(capPressBunkPicture)
                    SlaveFileLogger.getInstance().logInfo(DataPersistence.logSource,
                                                          f"Finished savings images",
                                                          Logger.SUCCESS)
                    # tStamp = getYMDHMSmFormatFromTimeDotTime(timeOfMessage)[:-4]
                    tStamp = datetime.fromtimestamp(float(timeOfMessage)).strftime('%Y-%m-%d %H:%M:%S')
                    qrCodeExists = checkIfQRCodeExists(qr_code=qrCode, db_name=getDatabaseName())

                    # print("=" * 80)
                    # print("DEBUG: About to call insertData()")
                    # print(f"db_name = {getDatabaseName()}")
                    # print(f"qr_code = {qrCode}")
                    # print(f"model_name = {model}")
                    # print(f"component_assembly_start_datetime = {tStamp}")
                    # print(f"check_knuckle_result = {knuckleCheckResult}")
                    # print(f"check_knuckle_datetime = {knuckleCheckDatetime}")
                    # print("=" * 80)

                    try:
                        success = insertData(
                            db_name=getDatabaseName(),
                            qr_code=qrCode,
                            model_name=model,
                            lhs_rhs=lhs_rhs,
                            model_tonnage=tonnage,
                            component_assembly_start_datetime=tStamp,
                            check_knuckle_imagefile=knucklePictureFile,
                            check_knuckle_result=knuckleCheckResult,
                            check_knuckle_datetime=knuckleCheckDatetime,
                            check_hub_and_bottom_bearing_imagefile=hubAndBottomBearingPictureFile,
                            check_hub_and_bottom_bearing_result=hubAndBottomBearingCheckResult,
                            check_hub_and_bottom_bearing_datetime=hubAndBottomBearingCheckDatetime,
                            check_top_bearing_imagefile=topBearingPictureFile,
                            check_top_bearing_result=topBearingCheckResult,
                            check_top_bearing_datetime=topBearingCheckDatetime,
                            check_nut_and_platewasher_imagefile=nutAndPlateWasherPictureFile,
                            check_nut_and_platewasher_result=nutAndPlateWasherCheckResult,
                            check_nut_and_platewasher_datetime=nutAndPlateWasherCheckDatetime,
                            nut_tightening_torque_1=float(tighteningTorque1),
                            nut_tightening_torque_1_result=tighteningTorque1Result,
                            nut_tightening_torque_1_datetime=tighteningTorque1Datetime,
                            free_rotations_done=freeRotationDone,
                            free_rotations_datetime=freeRotationDatetime,
                            check_bunk_for_component_press_imagefile=bunkForComponentPressFile,
                            check_bunk_for_component_press_result=componentPressBunkCheckResult,
                            check_bunk_for_component_press_datetime=componentPressBunkCheckDatetime,
                            component_press_done=componentPressDone,
                            component_press_datetime=componentPressDoneDatetime,
                            check_no_bunk_imagefile=noBunkFile,
                            check_no_bunk_result=noBunkCheckResult,
                            check_no_bunk_datetime=noBunkCheckDatetime,
                            nut_tightening_torque_2=float(tighteningTorque2),
                            nut_tightening_torque_2_result=tighteningTorque2Result,
                            nut_tightening_torque_2_datetime=tighteningTorque2Datetime,
                            check_splitpin_and_washer_imagefile=splitPinAndWasherFile,
                            check_splitpin_and_washer_result=splitPinAndWasherCheckResult,
                            check_splitpin_and_washer_datetime=splitPinAndWasherCheckDatetime,
                            check_cap_imagefile=capPictureFile,
                            check_cap_result=capCheckResult,
                            check_cap_datetime=capCheckDatetime,
                            check_bunk_cap_press_imagefile=bunkCapPressFile,
                            check_bunk_cap_press_result=capPressBunkCheckResult,
                            check_bunk_cap_press_datetime=capPressBunkCheckDatetime,
                            cap_press_done=capPressDone,
                            cap_press_datetime=capPressDoneDatetime,
                            free_rotation_torque_1=float(freeRotationTorque1),
                            free_rotation_torque_1_result=freeRotationTorque1Result,
                            free_rotation_torque_1_datetime=freeRotationTorque1Datetime,
                            ok_notok_result=overallResult,
                            username=self.username,
                            remarks="DUPLICATE" if qrCodeExists else "")
                        if success:
                            savedRecords += 1
                            logBoth('logInfo', DataPersistence.logSource,
                                    f"Inserted record number {savedRecords} successfully in database",
                                    Logger.SUCCESS)
                        else:
                            logBoth('logTakeAction', DataPersistence.logSource,
                                    "Failed to insert record in database",
                                    Logger.ISSUE)
                        self.currentModelName = None
                    except (Exception, Error) as error:
                        logBoth('logTakeNote', DataPersistence.logSource,
                                f"Error {error} while inserting data in data_table {id} in schema {getSchemaName()} in database {getDatabaseName()} due to {error}",
                                Logger.RISK)
                else:
                    # printBoldYellow(f"No data received in doWork() - waiting...")
                    pass

                if (savedRecords % 50 == 0):
                    SlaveConsoleLogger.getInstance().logInfo(DataPersistence.logSource,
                                                             f"Saved {savedRecords} records overall since the last start",
                                                             Logger.SUCCESS)
                else:
                    # print(f"Got None in {id}")
                    pass

            except (Exception, Error) as error1:
                logBoth('logTakeAction', DataPersistence.logSource,
                        f"Error in DBServer in process {os.getpid()} due to {error1}",
                        Logger.PROBLEM)
            try:
                _, shallStop = getStopCommandFromQueue(self.redisConnection)
                if shallStop:
                    logBoth('logInfo', DataPersistence.logSource,
                            f"Got stop command in process {os.getpid()} in DBServer - stopping", Logger.GENERAL)
                    self.stop()
            except:
                self.connectToRedis(True)
        logBoth('logInfo', DataPersistence.logSource, "In DBServer, stopping doWork", Logger.GENERAL)

    def sendHeartbeat(self) -> None:
        sleepTime = CosThetaConfigurator.getInstance().getDatabaseConnectionStatusSleepInterval()
        while not self.stopped:
            try:
                connected = checkConnection(db_name=getDatabaseName())
                if connected:
                    # printBoldGreen(f"Connected. Sending heartbeat with OK")
                    if self.heartbeatRedisConnected:
                        sendHeartbeatFromDBServerToHeartbeatServer(self.heartbeatRedisConnection, ALIVE)
                    else:
                        self.connectToRedis(forceRenew=True)
                else:
                    # printBoldRed(f"Not Connected. Sending heartbeat with Not OK")
                    if self.heartbeatRedisConnected:
                        sendHeartbeatFromDBServerToHeartbeatServer(self.heartbeatRedisConnection, DEAD)
                    else:
                        self.connectToRedis(forceRenew=True)
            except:
                logBoth('logTakeAction', DataPersistence.logSource,
                        "Could not send heartbeat from DBServer",
                        Logger.PROBLEM)
            try:
                _, shallStop = getStopCommandFromQueue(self.heartbeatRedisConnection)
                if shallStop:
                    logBoth('logInfo', DataPersistence.logSource,
                            f"Got stop command in process {os.getpid()} in DBServer heartbeat - stopping",
                            Logger.GENERAL)
                    self.stop()
            except:
                self.connectToRedis(True)
            # time.sleep(sleepTime)
            for _ in range(int(sleepTime * 10)):  # Check every 0.1 seconds
                if self.stopped:
                    break
                time.sleep(0.1)

    def startPersistenceAndHeartbeatThreads(self) -> None:
        self.threadForDoingMainWork = threading.Thread(
            name=f'Thread for saving images and updating the database',
            target=self.doWork,
            args=(), daemon=True)
        self.heartbeatThread = threading.Thread(name=f'Heartbeat - {DataPersistence.logSource}',
                                                target=self.sendHeartbeat,
                                                args=(), daemon=True)
        self.threadForDoingMainWork.start()
        # printBoldYellow(f"Reached 4 in DataPersistence")
        self.heartbeatThread.start()
        # printBoldYellow(f"Reached 5 in DataPersistence")

    def printData(self) -> None:
        try:
            print(checkConnection(db_name=getDatabaseName()))
            print(checkIfDatabaseExists("auto_company_production"))
            print(getCurrentTime())
            print(f"{getFolderForKnuckleImages() = }")
            print(f"{getFolderForHubAndBottomBearingImages() = }")
            print(f"{getFolderForTopBearingImages() = }")
            print(f"{getFolderForNutAndPlateWasherImages() = }")
            print(f"{getFolderForSplitPinAndWasherImages() = }")
            print(f"{getFolderForCapImages() = }")
            print(f"{getFolderForBunkAndNoBunkImages() = }")
        except (Exception, Error) as error:
            SlaveFileLogger.getInstance().logTakeNote(DataPersistence.logSource,
                                                      f"Error {error} while executing printData()",
                                                      Logger.RISK)
            SlaveConsoleLogger.getInstance().logTakeNote(DataPersistence.logSource,
                                                         f"Error {error} while executing printData()",
                                                         Logger.RISK)


def startDBServer(mode: str = "Test", username: str | None = "admin") -> None:
    dbServer = DataPersistence(mode=mode, username=username)
    dbServer.threadForDoingMainWork.join()
    sys.exit(0)

# startDBServer()