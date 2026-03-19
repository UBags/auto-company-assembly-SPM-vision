import copy
import time
from threading import Thread
from queue import *
import cv2
import numpy as np
import sys

import logutils.SlaveLoggers
from camera.RTSPCam import *
from processors.GenericQueueProcessor import *
from utils.CosThetaFileUtils import *
from utils.RedisUtils import *
from BaseUtils import *
from logutils import SlaveLoggers
from logutils.SlaveLoggers import *
from utils.QRCodeHelper import *
# from processors.image.ImageSaver import *
from concurrent.futures import ThreadPoolExecutor, wait

from camera.CheckKnuckle import CheckKnuckle
from camera.CheckHubAndBottomBearing import CheckHubAndBottomBearing
from camera.CheckTopBearing import CheckTopBearing
from camera.CheckNutAndPlateWasher import CheckNutAndPlateWasher
from camera.CheckSplitPinAndWasher import CheckSplitPinAndWasher
from camera.CheckCap import CheckCap
from camera.CheckNoCapBunk import CheckNoCapBunk
from camera.CheckNoBunk import CheckNoBunk
from camera.CheckBunk import CheckBunk

import warnings
warnings.filterwarnings('ignore', '.*h264.*', )

from Configuration import *
CosThetaConfigurator.getInstance()

# CONSTANTS
FIRST_PICTURE : str = "firstPicture"
SECOND_PICTURE : str = "secondPicture"
THIRD_PICTURE : str = "thirdPicture"

# GLOBAL VARIABLES
logSource = getFullyQualifiedName(__file__)

# *******************************Start of the main Threaded Classes*********************************

# *******************************MonitorGetPicQueue start*******************************************
class MonitorGetPicQueue(GenericQueueProcessor):

    # NOTE: This is a thread that is constantly monitoring the io2cameraq for a (takePicture+currentMachineState) message
    # How it works is like this:
    # 1. In init(), I put MonitorGetPicQueue.monitorQCommand into the python queue
    # 2. That ensures that in the doWork() loop, the non-blocking getItem() always gets a non-None item
    # 3. This non-None item in turn ensures that this thread always peeps into the non-blocking
    #    Redis call to io2cameraq
    #    in every loop of the thread to see if there is an item in that Redis queue

    logSource = getFullyQualifiedName(__file__)
    monitorQCommand : str = "monitorQ"

    def __init__(self, name: str, consumer: Thread = None, timeout: int = 1,
                 # sleepTime: float = CosThetaConfigurator.getInstance().getSleepTimeForMonitoringTakePicQ(),
                 sleepTime: float = 0.1,
                 blocking: bool = True, monitorRedisQueueForStopping: bool = True, max_size: int = 32, **kwargs):
        GenericQueueProcessor.__init__(self, name=name, consumer=consumer, sleepTime=sleepTime, blocking=blocking,
                                       timeout=timeout,
                                       monitorRedisQueueForStopping=monitorRedisQueueForStopping, max_size=max_size,
                                       **kwargs)
        if consumer is None:
            logBoth('logWarning', MonitorGetPicQueue.logSource,
                    f"In {MonitorGetPicQueue.logSource}.{self.name}, consumer instance is None",
                    Logger.ISSUE)
            raise Exception("Consumer is needed for MonitorGetPicQueue")
        MonitorGetPicQueue.logSource = getFullyQualifiedName(__file__, __class__)
        self.redisConnectionQ = None
        self.clientRedisConnectedQ = False
        self.connectToRedis()
        self.addItem(MonitorGetPicQueue.monitorQCommand)

    def connectToRedis(self, forceRenew = False):
        if forceRenew:
            self.redisConnectionQ = None
            self.clientRedisConnectedQ = False
        if not self.clientRedisConnectedQ:
            try:
                self.redisConnectionQ = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort,
                                              retry_on_timeout=True)
                self.clientRedisConnectedQ = True
                logBoth('logInfo', MonitorGetPicQueue.logSource, 'Redis connection established', Logger.SUCCESS)
            except:
                self.clientRedisConnectedQ = False
                logBoth('logCritical', MonitorGetPicQueue.logSource, 'Could not get Redis Connection', Logger.PROBLEM)
                # pass

    def getItem(self, blocking=True) -> Union[Any, None]:

        return super().getItem()

    def preWorkLoop(self):
        return

    def processItem(self, item: Any) -> Any:
        # print(f"In MonitorGetPic, got item {item}")
        if not self.getStopped():
            # See NOTE above to understand wht this line is there
            self.addItem(MonitorGetPicQueue.monitorQCommand)
        timeOfMessage : Union[str, float, None] = None
        currentMachineState : MachineState = MachineState.INVALID_STATE
        takePicture : bool = False
        try:
            timeOfMessage, currentMachineState, takePicture = readDataInCameraServerFromIOServer(self.redisConnectionQ, block=500)
        except Exception as e:
            logBoth('logWarning', MonitorGetPicQueue.logSource, f"Exception reading camera queue: {e}", Logger.ISSUE)
            self.connectToRedis()
        if takePicture:
            timeOfMessage = float(timeOfMessage)
            logBoth('logInfo', MonitorGetPicQueue.logSource, f"Got takePicture command in MonitorGetPicQueue", Logger.SUCCESS)
            messageToBeSentToConsumer = {timeKeyString: timeOfMessage, currentMachineStateKeyString : currentMachineState,
                    actionKeyString: takePictureCommand}
            logBoth('logDebug', MonitorGetPicQueue.logSource, f"In MonitorGetPic, sending message {messageToBeSentToConsumer}", Logger.GENERAL)
            return messageToBeSentToConsumer
        else:
            # printBoldRed(f"Got no command in MonitorGetPicQueue")
            pass
        return None

    def postWorkLoop(self):
        # printBoldBlue(f"Finished thread {self.name}")
        if self.monitorRedisQueueForStopping:
            sendStoppedResponse(self.redisConnectionForMonitoringStop, f"{MonitorGetPicQueue.logSource}.{self.name}")

# *******************************MonitorGetPicQueue end*********************************************

# from utils.CosThetaFileUtils import *
#
# class ImageFeederForTesting():
#
#     def __init__(self):
#         self.indexTable=[]
#         self.currentIndex = 0
#         self.basePath = "C:/PythonProjects/New/Images/Right Disc All/"
#         self.filesInDirectory = getAllFilesInDirectory(self.basePath)
#         self.nFilesInDirectory = len(self.filesInDirectory)
#
#     def getNextImage(self):
#         if self.currentIndex >= self.nFilesInDirectory:
#             return None
#         imagePath = self.basePath + self.filesInDirectory[self.currentIndex]
#         image = cv2.imread(imagePath)
#         self.currentIndex += 1
#         if (self.nFilesInDirectory - self.currentIndex) < 4:
#             self.currentIndex = 0
#         return image

# *******************************Results Tracking start*******************************************

INVALID_RESULT: Union[str, bool] = "Invalid Result"  # Example value

# Define the type for each inner tuple
ResultPair = Tuple[Union[str, bool], Optional[np.ndarray]]

# This list stores the evaluation result (True or False), and the image (None | np.ndarray)
resultsFromPictureAssessment : List[ResultPair] = [(INVALID_RESULT, None), (INVALID_RESULT, None), (INVALID_RESULT, None)]
# This list stores the evaluation result (True or False)
resultsStatus : list[bool] = [False, False, False]
resultsLock = threading.Lock()

def resetResults():
    global resultsFromPictureAssessment, resultsStatus, resultsLock
    # printBold("Entered reset results")
    acquired = resultsLock.acquire()
    if acquired:
        try:
            resultsFromPictureAssessment = [[INVALID_RESULT, None],[INVALID_RESULT, None],[INVALID_RESULT, None]]
            resultsStatus = [False, False, False]
        except:
            pass
        resultsLock.release()
    # printBold("Exiting reset results")

def addAResult(anImage : np.ndarray, aResult : bool, index: int):
    global resultsFromPictureAssessment, resultsStatus, resultsLock
    # acquired = resultsLock.acquire()
    # if acquired:
    #     try:
    #         resultsFromPictureAssessment[index] = (aResult, anImage)
    #         resultsStatus[index] = aResult
    #     except:
    #         pass
    #     resultsLock.release()
    with resultsLock:
        try:
            resultsFromPictureAssessment[index] = (aResult, anImage)
            resultsStatus[index] = aResult
        except:
            pass


# *******************************Results Tracking End*********************************************

# *******************************TakePictures start*********************************************

class TakePictures(GenericQueueProcessor):

    logSource = getFullyQualifiedName(__file__)

    def __init__(self, name: str, consumer: GenericQueueProcessor = None, timeout : int = 1, sleepTime : float = 0.1,
                 monitorRedisQueueForStopping : bool = True, max_size=32, **kwargs):

        GenericQueueProcessor.__init__(self, name=name, consumer=consumer, timeout=timeout, sleepTime=sleepTime, blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping, max_size=max_size, **kwargs)
        TakePictures.logSource = getFullyQualifiedName(__file__, __class__)
        self.cameraID = CosThetaConfigurator.getInstance().getCameraId()
        self.cameraIP = CosThetaConfigurator.getInstance().getCameraIP()
        self.cameraPort = CosThetaConfigurator.getInstance().getCameraPort()
        self.cameraUID = CosThetaConfigurator.getInstance().getCameraUid()
        self.cameraPwd = CosThetaConfigurator.getInstance().getCameraPwd()
        self.gapBetweenPictures = CosThetaConfigurator.getInstance().getTimeBetweenPicturesInMs() * 1.0 / 1000
        self.camera = RTSPCam(IP=self.cameraIP, port=self.cameraPort, uid=self.cameraUID, password=self.cameraPwd, name=self.cameraID)
        self.redisConnectionForHeartbeat = None
        self.clientRedisConnectedForHeartbeat = False
        self.connectToRedisForHeartbeat()
        self.launchThreadForHeartbeat()

    def connectToRedisForHeartbeat(self, forceRenew=False):
        if forceRenew:
            self.redisConnectionForHeartbeat = None
            self.clientRedisConnectedForHeartbeat = False
        if not self.clientRedisConnectedForHeartbeat:
            try:
                self.redisConnectionForHeartbeat = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort, retry_on_timeout=True)
                self.clientRedisConnectedForHeartbeat = True
                logBoth('logInfo', TakePictures.logSource, 'Heartbeat Redis connection established', Logger.SUCCESS)
            except Exception as e:
                self.clientRedisConnectedForHeartbeat = False
                self.redisConnectionForHeartbeat = None
                logBoth('logWarning', TakePictures.logSource,
                        f'Could not get Redis Connection for heartbeat in {TakePictures.logSource} due to {e}',
                        Logger.RISK)

    def addItem(self, item: Any) -> Union[Any, None]:
        if isinstance(item, dict):
            if item[actionKeyString] == takePictureCommand:
                return super().addItem(item)

    def preWorkLoop(self):
        return

    def processItem(self, item : Any) -> Any :
        logBoth('logDebug', TakePictures.logSource, f"In TakePictures, about to process item. Camera status is {self.camera.connected}", Logger.GENERAL)
        if not self.camera.connected:
            return {timeKeyString: None, FIRST_PICTURE: None, SECOND_PICTURE: None,
             THIRD_PICTURE: None, currentMachineStateKeyString: MachineState.INVALID_STATE}
        if item is not None:
            try:
                firstPic: Union[None | np.ndarray] = None
                try:
                    _, firstPic = self.camera.getLatestFrame()
                except Exception as e1:
                    logBoth('logWarning', TakePictures.logSource,
                            f"Exception getting first frame: {e1}", Logger.RISK)

                logBoth('logDebug', TakePictures.logSource, f"Got first picture with shape {firstPic.shape if isinstance(firstPic, np.ndarray) else 'None'}", Logger.GENERAL)

                time.sleep(self.gapBetweenPictures)
                secondPic : Union[None | np.ndarray] = None
                try:
                    _, secondPic = self.camera.getLatestFrame()
                except Exception as e2:
                    logBoth('logWarning', TakePictures.logSource,
                            f"Exception getting second frame: {e2}", Logger.RISK)

                logBoth('logDebug', TakePictures.logSource, f"Got second picture with shape {secondPic.shape if isinstance(secondPic, np.ndarray) else 'None'}", Logger.GENERAL)
                time.sleep(self.gapBetweenPictures)
                thirdPic: Union[None | np.ndarray] = None
                try:
                    _, thirdPic = self.camera.getLatestFrame()
                except Exception as e3:
                    logBoth('logWarning', TakePictures.logSource,
                            f"Exception getting third frame: {e3}", Logger.RISK)

                logBoth('logDebug', TakePictures.logSource, f"Got third picture with shape {thirdPic.shape if isinstance(thirdPic, np.ndarray) else 'None'}", Logger.GENERAL)

                # if isinstance(image, np.ndarray):
                #     if (image.shape[1] == self.targetWidth) and (image.shape[0] == self.targetHeight):
                #         reduced_image = image
                #     else:
                #         reduced_image = cv2.resize(image, (self.targetWidth, self.targetHeight), interpolation=cv2.INTER_LANCZOS4)
                # elif isinstance(image, bytes):
                #     img_array = np.asarray(bytearray(image), dtype=np.uint8)
                #     img = cv2.imdecode(img_array, -1)
                #     if (img.shape[1] == self.targetWidth) and (img.shape[0] == self.targetHeight):
                #         reduced_image = img
                #     else:
                #         reduced_image = cv2.resize(img, (self.targetWidth, self.targetHeight), interpolation=cv2.INTER_AREA)
                return {timeKeyString : item[timeKeyString], FIRST_PICTURE : firstPic, SECOND_PICTURE : secondPic, THIRD_PICTURE : thirdPic, currentMachineStateKeyString : item[currentMachineStateKeyString]}
            except Exception as e:
                if self.debugOtherExceptions:
                    logBoth('logCritical', TakePictures.logSource,
                            f"Could not take pictures in TakePictures.{self.name} due to exception {e}",
                            Logger.CRITICAL)
        else:
            if self.debugOtherExceptions:
                logBoth('logWarning', TakePictures.logSource,
                        f"Could not take pictures in TakePictures.{self.name} as item is None",
                        Logger.RISK)
        return {timeKeyString: None, FIRST_PICTURE: None, SECOND_PICTURE: None,
                THIRD_PICTURE: None, currentMachineStateKeyString: MachineState.INVALID_STATE}

    def postWorkLoop(self):
        if self.monitorRedisQueueForStopping:
            sendStoppedResponse(self.redisConnectionForMonitoringStop, f"{ConverterScalerAndProcessor.logSource}.{self.name}")

    def launchThreadForHeartbeat(self):
        objRef = self
        def reportHeartbeat():
            cameraHeartbeatGap = CosThetaConfigurator.getInstance().getCameraConnectionStatusSleepInterval()
            while not objRef.stopped:
                # print(f"Sending CameraServer heartbeat")
                try:
                    # if objRef.camera is None or objRef.alternateCamera is None:
                    if objRef.camera is None:
                        sendHeartbeatFromCameraServerToHeartbeatServer(redisConnection=objRef.redisConnectionForHeartbeat, status=DEAD)
                    elif not objRef.camera.connected:
                        sendHeartbeatFromCameraServerToHeartbeatServer(redisConnection=objRef.redisConnectionForHeartbeat, status=DEAD)
                    else:
                        sendHeartbeatFromCameraServerToHeartbeatServer(redisConnection=objRef.redisConnectionForHeartbeat, status=ALIVE)
                except:
                    objRef.connectToRedisForHeartbeat(forceRenew=True)
                try:
                    time.sleep(cameraHeartbeatGap)
                except:
                    pass
        heartbeatThread = threading.Thread(name=f"Camera Heartbeat Thread", target=reportHeartbeat, args=(), daemon = True)
        heartbeatThread.start()

# *******************************TakePictures end***************************************************

# *******************************ConverterAndScaler start*******************************************

class ConverterScalerAndProcessor(GenericQueueProcessor):

    logSource = getFullyQualifiedName(__file__)

    def __init__(self, name: str, consumer: GenericQueueProcessor = None, timeout : int = 1, sleepTime : float = 0.1,
                 monitorRedisQueueForStopping : bool = True, max_size=32, **kwargs):
        GenericQueueProcessor.__init__(self, name=name, consumer=consumer, timeout=timeout, sleepTime=sleepTime,
                                       blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping,
                                       max_size=max_size, **kwargs)

        ConverterScalerAndProcessor.logSource = getFullyQualifiedName(__file__, __class__)
        self.redisConnection : Union[Redis,None] = None
        self.clientRedisConnected : bool = False
        self.connectToRedis()
        # reportMessageCount(self.redisConnection)
        # clearQueues(self.redisConnection)
        # reportMessageCount(self.redisConnection)

    def connectToRedis(self, forceRenew = False):
        if forceRenew:
            self.redisConnection = None
            self.clientRedisConnected = False
        if not self.clientRedisConnected:
            try:
                self.redisConnection = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort,
                                             retry_on_timeout=True)
                self.clientRedisConnected = True
                logBoth('logInfo', ConverterScalerAndProcessor.logSource, 'Redis connection established', Logger.SUCCESS)
            except:
                self.clientRedisConnected = False
                logBoth('logCritical', ConverterScalerAndProcessor.logSource, 'Could not get Redis Connection', Logger.PROBLEM)
                # pass


    def addItem(self, item: Any) -> Union[Any, None]:
        # if isinstance(item, dict) and (isinstance(item[FIRST_PICTURE], np.ndarray | None) or isinstance(item[SECOND_PICTURE], np.ndarray | None) or isinstance(item[THIRD_PICTURE], np.ndarray | None)):
        if isinstance(item, dict):
            return super().addItem(item)

    def preWorkLoop(self):
        return

    def getTargetWidthAndHeight(self, currentMachineState : MachineState):
        currentMachineStateAsInt : int = MachineState.getMachineStateAsInt(currentMachineState)
        targetWidth, targetHeight = CosThetaConfigurator.getInstance().getTargetWidthAndHeight(
            currentMachineState=currentMachineStateAsInt)
        return targetWidth, targetHeight

    def processItem(self, item : Any) -> Any :
        global resultsFromPictureAssessment, resultsStatus, resultsLock
        # printBoldGreen(f"Inside processItem() of ConverterScalerAndProcessor got item {item}")
        resetResults()
        if item is not None:

            currentMachineState = item[currentMachineStateKeyString]
            targetWidth, targetHeight = self.getTargetWidthAndHeight(currentMachineState=currentMachineState)

            firstPic = item[FIRST_PICTURE]
            secondPic = item[SECOND_PICTURE]
            thirdPic = item[THIRD_PICTURE]

            modified_FirstPic: Union[np.ndarray, None] = None
            modified_SecondPic: Union[np.ndarray, None] = None
            modified_ThirdPic: Union[np.ndarray, None] = None

            try:
                if (firstPic is not None) and isinstance(firstPic, np.ndarray):
                    if (firstPic.shape[1] == targetWidth) and (firstPic.shape[0] == targetHeight):
                        modified_FirstPic = firstPic
                    else:
                        modified_FirstPic = cv2.resize(firstPic, (targetWidth, targetHeight),
                                                       interpolation=cv2.INTER_LANCZOS4)
                elif (firstPic is not None) and isinstance(firstPic, bytes):
                    img_array = np.asarray(bytearray(firstPic), dtype=np.uint8)
                    img = cv2.imdecode(img_array, -1)
                    if (img.shape[1] == targetWidth) and (img.shape[0] == targetHeight):
                        modified_FirstPic = img
                    else:
                        modified_FirstPic = cv2.resize(img, (targetWidth, targetHeight), interpolation=cv2.INTER_AREA)
            except Exception as e:
                modified_FirstPic = None
                if self.debugOtherExceptions:
                    logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                            f"Could not get the first pic due to exception {e}",
                            Logger.RISK)

            try:
                if (secondPic is not None) and isinstance(secondPic, np.ndarray):
                    if (secondPic.shape[1] == targetWidth) and (secondPic.shape[0] == targetHeight):
                        modified_SecondPic = secondPic
                    else:
                        modified_SecondPic = cv2.resize(secondPic, (targetWidth, targetHeight),
                                                        interpolation=cv2.INTER_LANCZOS4)
                elif (secondPic is not None) and isinstance(secondPic, bytes):
                    img_array = np.asarray(bytearray(secondPic), dtype=np.uint8)
                    img = cv2.imdecode(img_array, -1)
                    if (img.shape[1] == targetWidth) and (img.shape[0] == targetHeight):
                        modified_SecondPic = img
                    else:
                        modified_SecondPic = cv2.resize(img, (targetWidth, targetHeight), interpolation=cv2.INTER_AREA)
            except Exception as e:
                modified_SecondPic = None
                if self.debugOtherExceptions:
                    logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                            f"Could not get the second pic due to exception {e}",
                            Logger.RISK)

            try:
                if (thirdPic is not None) and isinstance(thirdPic, np.ndarray):
                    if (thirdPic.shape[1] == targetWidth) and (thirdPic.shape[0] == targetHeight):
                        modified_ThirdPic = thirdPic
                    else:
                        modified_ThirdPic = cv2.resize(thirdPic, (targetWidth, targetHeight),
                                                       interpolation=cv2.INTER_LANCZOS4)
                elif (thirdPic is not None) and isinstance(thirdPic, bytes):
                    img_array = np.asarray(bytearray(thirdPic), dtype=np.uint8)
                    img = cv2.imdecode(img_array, -1)
                    if (img.shape[1] == targetWidth) and (img.shape[0] == targetHeight):
                        modified_ThirdPic = img
                    else:
                        modified_ThirdPic = cv2.resize(img, (targetWidth, targetHeight), interpolation=cv2.INTER_AREA)
            except Exception as e:
                modified_ThirdPic = None
                if self.debugOtherExceptions:
                    logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                            f"Could not get the third pic due to exception {e}",
                            Logger.RISK)

            imagesToBeProcessed = [
                modified_FirstPic, modified_FirstPic,
                modified_SecondPic, modified_SecondPic,
                modified_ThirdPic, modified_ThirdPic
            ]

            methodToBeExecuted = None
            try:
                methodToBeExecuted = ImageProcessor.methodMapping[currentMachineState]
            except Exception as e:
                logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                        f"Exception getting methodMapping for state {currentMachineState}: {e}",
                        Logger.RISK)

            # Set flags based on currentMachineState directly (not dependent on methodMapping)
            # This ensures batch processing works even when methodMapping entry is None
            is_hub_and_bearing = (
                        currentMachineState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING)
            is_nut_and_washer = (
                        currentMachineState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER)
            is_nocap_bunk = (
                        currentMachineState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS)
            is_bunk = (currentMachineState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS)
            is_no_bunk = (currentMachineState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK)
            is_top_bearing = (
                        currentMachineState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING)

            # Defensive defaults — overwritten by all branches below
            allok = False
            chosenProcessedImage = None
            chosenOriginalImage = None

            # Enter this block if we have a method to execute OR if it's a batch processing state
            if methodToBeExecuted is not None or is_hub_and_bearing or is_nut_and_washer or is_nocap_bunk or is_bunk or is_no_bunk or is_top_bearing:
                nameOfMethod = ""
                try:
                    nameOfMethod : str = str(methodToBeExecuted.__name__) if hasattr(methodToBeExecuted, '__name__') else "unknown"
                    if "checkknuckle" in nameOfMethod.lower():
                        ImageProcessor.currentComponentQRCodeValue = None
                        ImageProcessor.currentModelName = None
                        ImageProcessor.currentSide = None
                        ImageProcessor.clearCurrentPictures()
                        ImageProcessor.clearBearingCentreAndRadii()
                        logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                "Reset ImageProcessor attributes for checkKnuckle method",
                                Logger.SUCCESS)
                except Exception as e:
                    logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                            f"methodToBeExecuted lacks __name__: {methodToBeExecuted}, , error: {e}",
                            Logger.RISK)

                try:
                    if is_hub_and_bearing:
                        # NEW: Use batch processing instead of threading
                        logBoth('logDebug', ConverterScalerAndProcessor.logSource, "Using batch processing for CheckHubAndBottomBearing", Logger.GENERAL)

                        try:
                            # Use the first image (they're all duplicates in imagesToBeProcessed)
                            test_image = imagesToBeProcessed[0]

                            ImageProcessor.currentPictures[hubAndBottomBearingPictureKeyString] = test_image

                            chosenProcessedImage, allok, winning_gamma = \
                                CheckHubAndBottomBearing.checkHubAndBottomBearing(
                                    test_image,
                                    ImageProcessor.currentComponentQRCodeValue,
                                    use_smart_gamma=True  # Enable smart ordering
                                )

                            chosenOriginalImage = test_image

                            if allok:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        f"CheckHubAndBottomBearing PASSED with gamma={winning_gamma}", Logger.SUCCESS)
                            else:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckHubAndBottomBearing FAILED", Logger.ISSUE)

                        except Exception as e:
                            logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                    f"CheckHubAndBottomBearing exception: {e}", Logger.ISSUE)
                            import traceback
                            traceback.print_exc()
                            allok = False
                            chosenProcessedImage = imagesToBeProcessed[0]
                            chosenOriginalImage = imagesToBeProcessed[0]

                    elif is_nut_and_washer:
                        # Use batch processing for CheckNutAndPlateWasher
                        logBoth('logDebug', ConverterScalerAndProcessor.logSource, "Using batch processing for CheckNutAndPlateWasher", Logger.GENERAL)

                        try:
                            test_image = imagesToBeProcessed[0]  # Just need one image

                            ImageProcessor.currentPictures[nutAndPlateWasherPictureKeyString] = test_image

                            chosenProcessedImage, allok = CheckNutAndPlateWasher.checkNutAndPlateWasher(
                                test_image,
                                ImageProcessor.currentPictures,
                                ImageProcessor.currentComponentQRCodeValue,
                                bearing_geometry=ImageProcessor.bearingCentreAndRadii
                            ) # Note: gamma not passed, relies on default

                            chosenOriginalImage = test_image

                            if allok:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckNutAndPlateWasher PASSED", Logger.SUCCESS)
                            else:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckNutAndPlateWasher FAILED", Logger.ISSUE)

                        except Exception as e:
                            logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                    f"CheckNutAndPlateWasher exception: {e}", Logger.ISSUE)
                            import traceback
                            traceback.print_exc()
                            allok = False
                            chosenProcessedImage = imagesToBeProcessed[0]
                            chosenOriginalImage = imagesToBeProcessed[0]

                    elif is_nocap_bunk:
                        # NEW: Use batch processing for CheckNoCapBunk
                        logBoth('logDebug', ConverterScalerAndProcessor.logSource, "Using batch processing for CheckNoCapBunk", Logger.GENERAL)

                        try:
                            # Use the first image (they're all duplicates in imagesToBeProcessed)
                            test_image = imagesToBeProcessed[0]

                            ImageProcessor.currentPictures[componentPressBunkPictureKeyString] = test_image

                            chosenProcessedImage, allok, winning_gamma = CheckNoCapBunk.checkNoCapBunk(
                                test_image,
                                ImageProcessor.currentComponentQRCodeValue,
                                bearing_geometry=ImageProcessor.bearingCentreAndRadii
                            )

                            chosenOriginalImage = test_image

                            if allok:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        f"CheckNoCapBunk PASSED with gamma={winning_gamma}", Logger.SUCCESS)
                            else:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckNoCapBunk FAILED", Logger.ISSUE)

                        except Exception as e:
                            logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                    f"CheckNoCapBunk exception: {e}", Logger.ISSUE)
                            import traceback
                            traceback.print_exc()
                            allok = False
                            chosenProcessedImage = imagesToBeProcessed[0]
                            chosenOriginalImage = imagesToBeProcessed[0]

                    elif is_bunk:
                        # NEW: Use batch processing for CheckBunk
                        logBoth('logDebug', ConverterScalerAndProcessor.logSource, "Using batch processing for CheckBunk", Logger.GENERAL)

                        try:
                            # Use the first image (they're all duplicates in imagesToBeProcessed)
                            test_image = imagesToBeProcessed[0]

                            ImageProcessor.currentPictures[capPressBunkPictureKeyString] = test_image

                            chosenProcessedImage, allok, winning_gamma = CheckBunk.checkBunk(
                                test_image,
                                ImageProcessor.currentComponentQRCodeValue,
                                bearing_geometry=ImageProcessor.bearingCentreAndRadii
                            )

                            chosenOriginalImage = test_image

                            if allok:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        f"CheckBunk PASSED with gamma={winning_gamma}", Logger.SUCCESS)
                            else:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckBunk FAILED", Logger.ISSUE)

                        except Exception as e:
                            logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                    f"CheckBunk exception: {e}", Logger.ISSUE)
                            import traceback
                            traceback.print_exc()
                            allok = False
                            chosenProcessedImage = imagesToBeProcessed[0]
                            chosenOriginalImage = imagesToBeProcessed[0]

                    elif is_no_bunk:
                        # Use batch processing for CheckNoBunk (avoids ThreadPoolExecutor timeout issues)
                        logBoth('logDebug', ConverterScalerAndProcessor.logSource, "Using batch processing for CheckNoBunk", Logger.GENERAL)

                        try:
                            test_image = imagesToBeProcessed[0]

                            ImageProcessor.currentPictures[noBunkPictureKeyString] = test_image

                            chosenProcessedImage, allok = CheckNoBunk.checkNoBunk(
                                anImage=test_image,
                                currentPictures=ImageProcessor.currentPictures,
                                componentQRCode=ImageProcessor.currentComponentQRCodeValue
                            )

                            chosenOriginalImage = test_image

                            if allok:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckNoBunk PASSED", Logger.SUCCESS)
                            else:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckNoBunk FAILED", Logger.ISSUE)

                        except Exception as e:
                            logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                    f"CheckNoBunk exception: {e}", Logger.ISSUE)
                            import traceback
                            traceback.print_exc()
                            allok = False
                            chosenProcessedImage = imagesToBeProcessed[0]
                            chosenOriginalImage = imagesToBeProcessed[0]

                    elif is_top_bearing:
                        logBoth('logDebug', ConverterScalerAndProcessor.logSource, "Using batch processing for CheckTopBearing", Logger.GENERAL)
                        try:
                            test_image = imagesToBeProcessed[0]

                            ImageProcessor.currentPictures[topBearingPictureKeyString] = test_image

                            annotated_img, allok, geometry = CheckTopBearing.checkTopBearing(
                                anImage=test_image,
                                currentPictures=ImageProcessor.currentPictures,
                                componentQRCode=ImageProcessor.currentComponentQRCodeValue
                            )

                            chosenProcessedImage = annotated_img if annotated_img is not None else test_image
                            chosenOriginalImage = test_image

                            if allok:
                                ImageProcessor.bearingCentreAndRadii = geometry
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        f"CheckTopBearing PASSED, geometry={geometry}", Logger.SUCCESS)
                            else:
                                logBoth('logInfo', ConverterScalerAndProcessor.logSource,
                                        "CheckTopBearing FAILED", Logger.ISSUE)

                        except Exception as e:
                            logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                    f"CheckTopBearing exception: {e}", Logger.ISSUE)
                            import traceback
                            traceback.print_exc()
                            allok = False
                            chosenProcessedImage = imagesToBeProcessed[0]
                            chosenOriginalImage = imagesToBeProcessed[0]

                    else:
                        # Original threading logic for other checks (non-hub-bearing)
                        with ThreadPoolExecutor(max_workers=6) as executor:
                            futures = [executor.submit(methodToBeExecuted.__func__, ImageProcessor, anImage, index,
                                                       gamma=index + 1)
                                       for index, anImage in enumerate(imagesToBeProcessed)]

                            wait(futures, timeout=5.0)

                            for index, future in enumerate(futures):
                                processedImage, evaluation = future.result(timeout=3.0)
                                if processedImage is not None:
                                    logBoth('logDebug', ConverterScalerAndProcessor.logSource,
                                            f"Shape of processedImage = {processedImage.shape}, evaluation result is {evaluation}",
                                            Logger.GENERAL)
                                else:
                                    logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                                            "processedImage is None", Logger.ISSUE)
                                addAResult(anImage=processedImage, aResult=evaluation, index=index // 2)

                except Exception as e:
                    logBoth('logCritical', ConverterScalerAndProcessor.logSource,
                            f'Could not complete ThreadPoolExecutor actions due to {e} in CameraProcessorServer',
                            Logger.PROBLEM)
                    pass

            if not is_hub_and_bearing and not is_bunk and not is_nocap_bunk and not is_nut_and_washer and not is_no_bunk and not is_top_bearing:
                allok = False
                # Original voting mechanism
                okcount: int = 0
                for result in resultsStatus:
                    if result:
                        okcount += 1

                chosenProcessedImage = None
                chosenOriginalImage = None

                allok = (okcount >= 2)

                for index, aPair in enumerate(resultsFromPictureAssessment):
                    if aPair[0] == allok:
                        chosenProcessedImage = aPair[1]
                        chosenOriginalImage = imagesToBeProcessed[index * 2]  # Map back to original (0→0, 1→2, 2→4)
                        break
            if allok:
                logBoth('logInfo', ConverterScalerAndProcessor.logSource, f"Final result: OK", Logger.SUCCESS)
            else:
                logBoth('logInfo', ConverterScalerAndProcessor.logSource, f"Final result: FAILED", Logger.ISSUE)
                sendAlarmSignalToHeartbeatServer(redisConnection=self.redisConnection)

            sendDataFromCameraServerToFEServer(redisConnection=self.redisConnection, originalImage=chosenOriginalImage,
                                               processedImage=chosenProcessedImage, result=ok if allok else notok,
                                               currentMachineState=currentMachineState)
            sendDataFromCameraServerToIOServer(redisConnection=self.redisConnection, result=ok if allok else notok,
                                               currentMachineState=currentMachineState)
        else:
            if self.debugOtherExceptions:
                logBoth('logWarning', ConverterScalerAndProcessor.logSource,
                        f"Did not reduce {'None startingImage' if item is None else type(item)} in ConverterScalerAndProcessor.{self.name}",
                        Logger.RISK)
            sendDataFromCameraServerToFEServer(redisConnection=self.redisConnection, originalImage=None,
                                               processedImage=None, result=notok,
                                               currentMachineState=MachineState.INVALID_STATE)
            sendDataFromCameraServerToIOServer(redisConnection=self.redisConnection, result=notok,
                                               currentMachineState=MachineState.INVALID_STATE)

        return None

    def postWorkLoop(self):
        # printBoldBlue(f"Finished thread {self.name}")
        if self.monitorRedisQueueForStopping:
            sendStoppedResponse(self.redisConnectionForMonitoringStop, f"{ConverterScalerAndProcessor.logSource}.{self.name}")

# *******************************ConverterAndScaler end*********************************************

# *******************************ImageProcessor begin***********************************************

class ImageProcessor():

    logSource = getFullyQualifiedName(__file__)

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 1
    greencolor = (0, 255, 0)
    redcolor = (0, 0, 255)
    thickness = 2

    saveTrialPictures : bool = CosThetaConfigurator.getInstance().getSaveAllPicturesBecauseItsInTrialMode()

    mainDirForSavingPictures : str = CosThetaConfigurator.getInstance().getMainPictureSavingDirForModeTrial()

    currentPictures : Dict[str, np.ndarray | None] = {knucklePictureKeyString : None,
                                                      hubAndBottomBearingPictureKeyString : None,
                                                      topBearingPictureKeyString : None,
                                                      nutAndPlateWasherPictureKeyString : None,
                                                      splitPinAndWasherPictureKeyString : None,
                                                      capPictureKeyString : None,
                                                      componentPressBunkPictureKeyString : None,
                                                      noBunkPictureKeyString : None,
                                                      capPressBunkPictureKeyString : None}

    currentComponentQRCodeValue: str | None = None
    currentModelName: str | None = None
    currentSide : str | None = None
    bearingCentreAndRadii: Dict[str, Any] | None = None

    # this lock is needed because 3 threads simultaneously call this function, and only 1 message is in the queue
    getQRCodeLock = threading.Lock()

    redisConnectionQ = None
    clientRedisConnectedQ = False

    @classmethod
    def connectToRedis(cls, forceRenew = False):
        if forceRenew:
            ImageProcessor.redisConnectionQ = None
            ImageProcessor.clientRedisConnectedQ = False
        if not ImageProcessor.clientRedisConnectedQ:
            try:
                ImageProcessor.redisConnectionQ = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort,
                                              retry_on_timeout=True)
                ImageProcessor.clientRedisConnectedQ = True
                logBoth('logInfo', ImageProcessor.logSource, 'Redis connection established', Logger.SUCCESS)
            except:
                ImageProcessor.clientRedisConnectedQ = False
                logBoth('logCritical', ImageProcessor.logSource, 'Could not get Redis Connection', Logger.PROBLEM)
                # pass


    @classmethod
    def getCurrentPictures(cls):
        return ImageProcessor.currentPictures

    @classmethod
    def clearCurrentPictures(cls):
        try:
            ImageProcessor.currentPictures[knucklePictureKeyString] = None
            ImageProcessor.currentPictures[hubAndBottomBearingPictureKeyString] = None
            ImageProcessor.currentPictures[topBearingPictureKeyString] = None
            ImageProcessor.currentPictures[nutAndPlateWasherPictureKeyString] = None
            ImageProcessor.currentPictures[splitPinAndWasherPictureKeyString] = None
            ImageProcessor.currentPictures[capPictureKeyString] = None
            ImageProcessor.currentPictures[componentPressBunkPictureKeyString] = None
            ImageProcessor.currentPictures[noBunkPictureKeyString] = None
            ImageProcessor.currentPictures[capPressBunkPictureKeyString] = None
        except Exception as e:
            logBoth('logWarning', ImageProcessor.logSource,
                    f"Exception in clearCurrentPictures: {e}", Logger.RISK)

    @classmethod
    def clearBearingCentreAndRadii(cls):
        try:
            ImageProcessor.bearingCentreAndRadii = None
        except Exception as e:
            logBoth('logWarning', ImageProcessor.logSource,
                    f"Exception in clearBearingCentreAndRadii: {e}", Logger.RISK)

    @classmethod
    def setCurrentComponentName(cls, qrCodeValue : str | None = None):
        ImageProcessor.currentComponentQRCodeValue = qrCodeValue
        model, side, tonnage  = getModel_LHSRHS_AndTonnage(qrCodeValue)
        ImageProcessor.currentModelName = model
        ImageProcessor.currentSide = side

    @classmethod
    def fetchAndPopulateCurrentComponentQRCode(cls):
        try:
            ImageProcessor.connectToRedis()
        except Exception as e:
            logBoth('logWarning', ImageProcessor.logSource,
                    f"Could not connect to Redis in fetchAndPopulateCurrentComponentQRCode: {e}",
                    Logger.RISK)
            return

        received: bool = False
        startTime = time.time()
        maxPeriodToSeekComponentName = 5  # secs
        while (not received) and ((time.time() - startTime) < maxPeriodToSeekComponentName) and (
                ImageProcessor.currentComponentQRCodeValue is None):
            try:
                comp_QRCode, received = readComponentQRCodeInCameraServerFromQRCodeServer(
                    ImageProcessor.redisConnectionQ)
                if received:
                    ImageProcessor.setCurrentComponentName(qrCodeValue=comp_QRCode)
            except Exception as e:
                logBoth('logWarning', ImageProcessor.logSource,
                        f"Exception reading QR code: {e}", Logger.RISK)
            time.sleep(0.15)

    @classmethod
    def checkKnuckle(cls, anImage: np.ndarray, index: int = -1, gamma : float = 2.0) -> Tuple[np.ndarray, bool]:

        try:
            logBoth('logDebug', ImageProcessor.logSource, "Entered checkKnuckle() of class ImageProcessor", Logger.GENERAL)
            with ImageProcessor.getQRCodeLock:
                if ImageProcessor.currentComponentQRCodeValue is None:
                    ImageProcessor.fetchAndPopulateCurrentComponentQRCode()

            if ImageProcessor.saveTrialPictures:
                currentMethodName = f"{inspect.currentframe().f_code.co_name}"
                currentMethodName = currentMethodName.replace("check", "")
                savingDir = f"{ImageProcessor.mainDirForSavingPictures}{currentMethodName}/"
                fileNameForSaving = f"{savingDir}{getFileNameForSaving(useExtension=False, useNanoSec=True)}"
                if index >= 0:
                    fileNameForSaving = f"{fileNameForSaving}-{index}.png"
                else:
                    fileNameForSaving = f"{fileNameForSaving}.png"
                # printLight(f"Saving image to {fileNameForSaving}")
                saveFileWithFullPath(anImage, fileNameForSaving)

            if index == 0:
                ImageProcessor.currentPictures[knucklePictureKeyString] = anImage

            return CheckKnuckle.checkKnuckle(anImage=anImage, currentPictures=ImageProcessor.currentPictures,
                                             componentQRCode=ImageProcessor.currentComponentQRCodeValue, gamma=gamma)
        except Exception as e:
            logBoth('logCritical', ImageProcessor.logSource,
                    f"Exception in ImageProcessor.checkKnuckle: {e}",
                    Logger.PROBLEM)
            return anImage, False

    @classmethod
    def checkTopBearing(cls, anImage: np.ndarray, index: int = -1, gamma: float = 2.0) -> Tuple[np.ndarray, bool]:
        try:
            if ImageProcessor.saveTrialPictures:
                currentMethodName = f"{inspect.currentframe().f_code.co_name}"
                currentMethodName = currentMethodName.replace("check", "")
                savingDir = f"{ImageProcessor.mainDirForSavingPictures}{currentMethodName}/"
                fileNameForSaving = f"{savingDir}{getFileNameForSaving(useExtension=False, useNanoSec=True)}"
                if index >= 0:
                    fileNameForSaving = f"{fileNameForSaving}-{index}.png"
                else:
                    fileNameForSaving = f"{fileNameForSaving}.png"
                # printLight(f"Saving image to {fileNameForSaving}")
                saveFileWithFullPath(anImage, fileNameForSaving)
            if index == 0:
                ImageProcessor.currentPictures[topBearingPictureKeyString] = anImage

            # Unpack the 3-tuple return value
            annotated_img, is_present, geometry = CheckTopBearing.checkTopBearing(
                anImage=anImage,
                currentPictures=ImageProcessor.currentPictures,
                componentQRCode=ImageProcessor.currentComponentQRCodeValue,
                gamma=gamma
            )

            # Store the geometry dictionary in bearingCentreAndRadii
            ImageProcessor.bearingCentreAndRadii = geometry

            return annotated_img, is_present

        except Exception as e:
            logBoth('logCritical', ImageProcessor.logSource,
                    f"Exception in ImageProcessor.checkTopBearing: {e}",
                    Logger.PROBLEM)
            return anImage, False

    @classmethod
    def checkSplitPinAndWasher(cls, anImage: np.ndarray, index: int = -1, gamma : float = 2.0) -> Tuple[np.ndarray, bool]:
        try:
            if ImageProcessor.saveTrialPictures:
                currentMethodName = f"{inspect.currentframe().f_code.co_name}"
                currentMethodName = currentMethodName.replace("check", "")
                savingDir = f"{ImageProcessor.mainDirForSavingPictures}{currentMethodName}/"
                fileNameForSaving = f"{savingDir}{getFileNameForSaving(useExtension=False, useNanoSec=True)}"
                if index >= 0:
                    fileNameForSaving = f"{fileNameForSaving}-{index}.png"
                else:
                    fileNameForSaving = f"{fileNameForSaving}.png"
                # printLight(f"Saving image to {fileNameForSaving}")
                saveFileWithFullPath(anImage, fileNameForSaving)
            if index == 0:
                ImageProcessor.currentPictures[splitPinAndWasherPictureKeyString] = anImage
            return CheckSplitPinAndWasher.checkSplitPinAndWasher(anImage=anImage,
                                                                 currentPictures=ImageProcessor.currentPictures,
                                                                 componentQRCode=ImageProcessor.currentComponentQRCodeValue,
                                                                 gamma=gamma)
        except Exception as e:
            logBoth('logCritical', ImageProcessor.logSource,
                    f"Exception in ImageProcessor.checkSplitPinAndWasher: {e}",
                    Logger.PROBLEM)
            return anImage, False

    @classmethod
    def checkCap(cls, anImage: np.ndarray, index: int = -1, gamma: float = 2.0) -> Tuple[np.ndarray, bool]:
        try:
            if ImageProcessor.saveTrialPictures:
                currentMethodName = f"{inspect.currentframe().f_code.co_name}"
                currentMethodName = currentMethodName.replace("check", "")
                savingDir = f"{ImageProcessor.mainDirForSavingPictures}{currentMethodName}/"
                fileNameForSaving = f"{savingDir}{getFileNameForSaving(useExtension=False, useNanoSec=True)}"
                if index >= 0:
                    fileNameForSaving = f"{fileNameForSaving}-{index}.png"
                else:
                    fileNameForSaving = f"{fileNameForSaving}.png"
                # printLight(f"Saving image to {fileNameForSaving}")
                saveFileWithFullPath(anImage, fileNameForSaving)
            if index == 0:
                ImageProcessor.currentPictures[capPictureKeyString] = anImage
            return CheckCap.checkCap(anImage=anImage,
                                     currentPictures=ImageProcessor.currentPictures,
                                     componentQRCode=ImageProcessor.currentComponentQRCodeValue,
                                     gamma=gamma)
        except Exception as e:
            logBoth('logCritical', ImageProcessor.logSource,
                    f"Exception in ImageProcessor.checkCap: {e}",
                    Logger.PROBLEM)
            return anImage, False

    @classmethod
    def checkNoBunk(cls, anImage: np.ndarray, index: int = -1, gamma : float = 2.0) -> Tuple[np.ndarray, bool]:
        try:
            if ImageProcessor.saveTrialPictures:
                currentMethodName = f"{inspect.currentframe().f_code.co_name}"
                currentMethodName = currentMethodName.replace("check", "")
                savingDir = f"{ImageProcessor.mainDirForSavingPictures}{currentMethodName}/"
                fileNameForSaving = f"{savingDir}{getFileNameForSaving(useExtension=False, useNanoSec=True)}"
                if index >= 0:
                    fileNameForSaving = f"{fileNameForSaving}-{index}.png"
                else:
                    fileNameForSaving = f"{fileNameForSaving}.png"
                # printLight(f"Saving image to {fileNameForSaving}")
                saveFileWithFullPath(anImage, fileNameForSaving)
            if index == 0:
                ImageProcessor.currentPictures[noBunkPictureKeyString] = anImage
            return CheckNoBunk.checkNoBunk(anImage=anImage,
                                           currentPictures=ImageProcessor.currentPictures,
                                           componentQRCode=ImageProcessor.currentComponentQRCodeValue,
                                           gamma=gamma)
        except Exception as e:
            logBoth('logCritical', ImageProcessor.logSource,
                    f"Exception in ImageProcessor.checkNoBunk: {e}",
                    Logger.PROBLEM)
            return anImage, False

    methodMapping: dict = {
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE: checkKnuckle,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING: None,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING: checkTopBearing,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER: None,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS: None,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK: checkNoBunk,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER: checkSplitPinAndWasher,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP: checkCap,
        MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS: None
    }

    # NOTE: As there are 3 pics being taken, instantiate 3 ImageProcessors per cameraId (==Camera Server)
    # These are to be done with pictureResultIndex = 0, pictureResultIndex = 1, pictureResultIndex = 2
    def __init__(self, name: str, pictureResultIndex : int, consumer: GenericQueueProcessor = None,
                 timeout : int = 1, sleepTime: float = 3.0, monitorRedisQueueForStopping : bool = True, max_size=32, **kwargs):
        GenericQueueProcessor.__init__(self, name=name, consumer=consumer, timeout=timeout, sleepTime=sleepTime,
                                       blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping,
                                       max_size=max_size, **kwargs)
        ImageProcessor.logSource = getFullyQualifiedName(__file__, __class__)
        self.pictureResultIndex = pictureResultIndex

# *******************************ImageProcessor end*************************************************

# *******************************MonitorSendResultQueue start*******************************************

# This is NOT NEEDED FOR Auto Company, because THERE IS NO NEED TO WAIT FOR A REDIS MESSAGE FROM IOSERVER
# BEFORE SENDING THE RETURN RESULT TO THE IOSERVER. This was a need in XYZ, so this thread was needed.

# class MonitorSendResultQueue(GenericQueueProcessor):
#
#     logSource = getFullyQualifiedName(__file__)
#
#     def __init__(self, name: str,  cameraId : int, consumer: GenericQueueProcessor = None, timeout: int = 1,
#                  # sleepTime: float = CosThetaConfigurator.getInstance().getSleepTimeForMonitoringTakePicQ(),
#                  sleepTime: float = 0.0,
#                  blocking: bool = True, monitorRedisQueueForStopping: bool = True, max_size: int = 32, **kwargs):
#         GenericQueueProcessor.__init__(self, name=name, consumer=consumer, sleepTime=sleepTime, blocking=blocking,
#                                        timeout=timeout,
#                                        monitorRedisQueueForStopping=monitorRedisQueueForStopping, max_size=max_size, **kwargs)
#         MonitorSendResultQueue.logSource = getFullyQualifiedName(__file__, __class__)
#         self.cameraId = cameraId
#         self.cameraResultQ = CosThetaConfigurator.getInstance().getCameraRequestResultQueue(cameraId=self.cameraId)
#         self.redisConnectionQ = None
#         self.clientRedisConnectedQ = False
#         self.connectToRedis()
#         # print(f"CameraQ is {self.cameraQ}, which has {getMessageCount(self.redisConnectionQ, self.cameraResultQ)} messages")
#         self.FASTEST_GAP_BETWEEN_TAKEPIC_REQUESTS = CosThetaConfigurator.getInstance().getFastestPossibleTimeBetweenTakePicRequests()
#         self.addItem("monitorQ")
#         # printBold(f"Added item in __init__() to queue {self.cameraResultQ} in MonitorSendResultQueue")
#         # self.setDebug(debugInit=False, debugAddItem= True, debugGetItem= True, debugProcessItem= True, debugWork= False, debugStop= True, debugOtherExceptions= False)
#
#     def connectToRedis(self, forceRenew = False):
#         if forceRenew:
#             self.redisConnectionQ = None
#             self.clientRedisConnectedQ = False
#         if not self.clientRedisConnectedQ:
#             try:
#                 self.redisConnectionQ = Redis(GenericQueueProcessor.redisHost, GenericQueueProcessor.redisPort, retry_on_timeout=True)
#                 self.clientRedisConnectedQ = True
#                 # printLight(f'Redis Connection is {self.redisConnectionLeftCameraPicture}')
#                 # SlaveConsoleLogger.getInstance().logDebug(MonitorSendResultQueue.logSource,
#                 #                                              f'Redis Connection is {self.redisConnectionQ}', Logger.SUCCESS)
#                 SlaveFileLogger.getInstance().logDebug(MonitorSendResultQueue.logSource,
#                                                           f'Redis Connection is {self.redisConnectionQ}', Logger.SUCCESS)
#                 sendCameraResultToIOServer(redisConnection=self.redisConnectionQ, result=notok,
#                                            cameraId=self.cameraId, aProducer=f"Camera_{self.name}", handshake=True)
#             except:
#                 self.clientRedisConnectedQ = False
#                 SlaveConsoleLogger.getInstance().logTakeAction(MonitorSendResultQueue.logSource,
#                                                              f'Could not get Redis Connection', Logger.PROBLEM)
#                 SlaveFileLogger.getInstance().logTakeAction(MonitorSendResultQueue.logSource,
#                                                              f'Could not get Redis Connection', Logger.PROBLEM)
#                 # pass
#
#     def getItem(self, blocking=True) -> Union[Any, None]:
#         # printBoldBlue(f"Added item in MonitorSendResultQueue")
#         return super().getItem()
#
#     def preWorkLoop(self):
#         return
#
#     def processItem(self, item: Any) -> Any:
#         global finalResult
#         # printBoldBlue(f"Entered processItem() in MonitorSendResultQueue")
#         if not self.getStopped():
#             self.addItem("monitorQ")
#         timeOfMessage = None
#         gotCommand = None
#         try:
#             # printBoldBlue(f"Waiting for message in {self.cameraResultQ} in MonitorSendResultQueue")
#             timeOfMessage, gotCommand = getRequestResultCommandFromIOServer(self.redisConnectionQ, self.cameraResultQ, block=5000)
#             # printBold(f"Got {timeOfMessage}, {gotCommand} from Redis in MonitorSendResultQueue {self.cameraResultQ}")
#         except Exception as e:
#             printBoldRed(e)
#             self.connectToRedis()
#         if timeOfMessage is not None:
#             if gotCommand:
#                 # printBold(f"Got {timeOfMessage}, {gotCommand} from Redis in MonitorSendResultQueue {self.cameraResultQ}")
#                 # printBoldGreen(f"Got command in MonitorSendResultQueue")
#                 timeOfMessage = float(timeOfMessage)
#                 if (time.time() - timeOfMessage) > self.FASTEST_GAP_BETWEEN_TAKEPIC_REQUESTS:
#                     printBoldRed(f"Got {timeOfMessage}, {gotCommand} from Redis in MonitorSendResultQueue {self.cameraResultQ} - Delayed by {time.time() - timeOfMessage} secs. Hence, not sending result")
#                 else:
#                     currentTime = time.time()
#                     sendCameraResultToIOServer(redisConnection=self.redisConnectionQ, result=finalResult, cameraId=self.cameraId, aProducer=f"Camera_{self.name}")
#                     timeNow = time.time()
#                     duration = round((timeNow - currentTime) * 1000,2)
#                     # printBold(f"Got {timeOfMessage}, {gotCommand} from Redis in MonitorSendResultQueue {self.cameraResultQ}. Sent result {finalResult} in {duration} ms")
#                     resetResults()
#                     return None
#             else:
#                 # printBoldRed(f"Got no command in MonitorGetPicQueue {self.cameraQ}")
#                 pass
#         return None
#
#     def postWorkLoop(self):
#         # printBoldBlue(f"Finished thread {self.name}")
#         if self.monitorRedisQueueForStopping:
#             sendStoppedResponse(self.redisConnectionForMonitoringStop, f"{MonitorGetPicQueue.logSource}.{self.name}")

# *******************************MonitorSendResultQueue end*********************************************



# **************************************************************************************************

def CameraServer(mode : str = "Test"):

    # imageWriter : GenericQueueProcessor = None
    # if mode.upper() == "TEST":
    #     imageWriter = ImageWriter(name="ImageWriter", savingDir=CosThetaConfigurator.getInstance().getMainPictureSavingDirForModeTrial())
    #     converterScalerAndProcessor = ConverterScalerAndProcessor(name="ConverterAndScaler", consumer=imageWriter)
    # else:
    try:
        converterScalerAndProcessor = ConverterScalerAndProcessor(name="Converter Scaler And Processor", consumer=None)
        # takePictures = TakePictures(name="TakePictures", cameraId=camId, consumer=converterScalerAndProcessor)
        takePictures = TakePictures(name="TakePictures", consumer=converterScalerAndProcessor)
        monitorGetPic = MonitorGetPicQueue(name="MonitorGetPicQueue", consumer=takePictures)
        converterScalerAndProcessor.start()
        logBoth('logInfo', logSource, f"Started thread ConverterScalerAndProcessor", Logger.SUCCESS)
        takePictures.start()
        logBoth('logInfo', logSource, f"Started thread TakePictures", Logger.SUCCESS)
        monitorGetPic.start()
        logBoth('logInfo', logSource, f"Started thread MonitorGetPicQ", Logger.SUCCESS)
        logBoth('logCritical', logSource, f"************", Logger.SUCCESS)
        logBoth('logCritical', logSource, f"Started Camera Server", Logger.SUCCESS)
        logBoth('logCritical', logSource, f"************", Logger.SUCCESS)
        monitorGetPic.join()
        takePictures.join()
        converterScalerAndProcessor.join()
    except Exception as e:
        logBoth('logCritical', logSource, f"Got Exception {e} while declaring Processors in Camera Server", Logger.PROBLEM)
    logBoth('logInfo', logSource, "About to exit Camera Server", Logger.GENERAL)
    sys.exit(0)

# **************************************************************************************************

def startCameraServer(mode: str = "Test"):
    CameraServer(mode=mode)

# startCameraServer()