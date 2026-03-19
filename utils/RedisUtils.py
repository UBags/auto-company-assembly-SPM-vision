import os
import queue
import time
from typing import Literal, Union, Tuple

import numpy as np
import cv2
import redis.client
from redis import Redis, ConnectionPool, ConnectionError

from logutils import Logger
from logutils.Logger import LogLevel
import inspect

# From statemachine
from statemachine.StateMachine import MachineState

# From utils
from utils.CosThetaPrintUtils import (
    printBoldRed,
    printBoldGreen,
    printBoldBlue,
    printBold,
    printPlain
)

# From BaseUtils
from BaseUtils import (
    getFullyQualifiedName,
    getCurrentTimeInMS,
    getPostgresDatetimeFromString,
)

# From Configuration
from Configuration import CosThetaConfigurator

CosThetaConfigurator.getInstance()
logSource = getFullyQualifiedName(__file__)

# Various states
EMPTY_IMAGE_STRING : str = ""
UNKNOWN : str = "Unknown"
INVALID_STATE : str  = "Invalid State"
INVALID_RESULT : str  = "Invalid Result"
TAKE_NEXT_PICTURE : str  = "Take Next Picture"
HANDSHAKE : str  = "Handshake"
ALIVE : str  = "Alive"
DEAD : str = "Dead"
ABORT : str = "Abort"
DOST : str = "DOST"
DOSTPLUS : str = "DOSTPLUS"
GARUDA : str = "GARUDA"

# Various keys
commonStreamKey: str = "genericstream"
succesKeyString: str = "successStatus"
timeKeyString: str = "timestamp"
producerKeyString: str = "producer"
originalImageKeyString: str = "originalImage"
processedImageKeyString: str = "processedImage"
resultKeyString: str = "result"
genericdataKeyString: str = "data"
idKeyString: str = "id"
qrCodeKeyString: str = "qrCode"
qrCodeStatusKeyString: str = "qrCodeStatus"
qrCodeDisplayKeyString: str = "qrCodeDisplay"
componentQRCodeKeyString: str = "componentQRCode"
currentMachineStateKeyString: str = "currentMachineState"
actionKeyString : str = "action"
move2StateKeyString : str = "moveToState"
valueKeyString : str = "value"
knucklePictureKeyString : str = "knucklePicture"
knuckleCheckResultKeyString : str = "knuckleCheckResult"
knuckleDatetimeKeyString : str = "knuckleDatetime"
hubAndBottomBearingPictureKeyString : str = "hubAndBottomBearingPicture"
hubAndBottomBearingCheckResultKeyString : str = "hubAndBottomBearingCheckResult"
hubAndBottomBearingDatetimeKeyString : str = "hubAndBottomBearingDatetime"
topBearingPictureKeyString : str = "topBearingPicture"
topBearingCheckResultKeyString : str = "topBearingCheckResult"
topBearingDatetimeKeyString : str = "topBearingDatetime"
nutAndPlateWasherPictureKeyString : str = "nutAndPlateWasherPicture"
nutAndPlateWasherCheckResultKeyString : str = "nutAndPlateWasherCheckResult"
nutAndPlateWasherDatetimeKeyString : str = "nutAndPlateWasherDatetime"
tighteningTorque1ValueKeyString : str = "tight1Value"
tighteningTorque1ResultKeyString : str = "tight1Result"
tighteningTorque1DatetimeKeyString : str = "tighteningTorque1Datetime"
freeRotationDoneKeyString : str = "freeRotationDone"
freeRotationDatetimeKeyString : str = "freeRotationDatetime"
componentPressBunkPictureKeyString : str = "componentPressBunkPicture"
componentPressBunkCheckResultKeyString : str = "componentPressBunkCheckResult"
componentPressBunkCheckDatetimeKeyString : str = "componentPressBunkCheckDatetime"
componentPressDoneResultKeyString : str = "componentPressDoneResult"
componentPressDoneDatetimeKeyString : str = "componentPressDoneDatetime"
noBunkPictureKeyString : str = "noBunkPicture"
noBunkCheckResultKeyString : str = "noBunkCheckResult"
noBunkCheckDatetimeKeyString : str = "noBunkCheckDatetime"
tighteningTorque2ValueKeyString : str = "tight2Value"
tighteningTorque2ResultKeyString : str = "tight2Result"
tighteningTorque2DatetimeKeyString : str = "tighteningTorque2Datetime"
splitPinAndWasherPictureKeyString : str = "splitpinAndWasherPicture"
splitPinAndWasherCheckResultKeyString : str = "splitPinAndWasherCheckResult"
splitPinAndWasherCheckDatetimeKeyString : str = "splitPinAndWasherCheckDatetime"
capPictureKeyString : str = "capPicture"
capCheckResultKeyString : str = "capCheckResult"
capCheckDatetimeKeyString : str = "capCheckDatetime"
capPressBunkPictureKeyString : str = "capPressBunkPicture"
capPressBunkCheckResultKeyString : str = "capPressBunkCheckResult"
capPressBunkCheckDatetimeKeyString : str = "capPressBunkCheckDatetime"
capPressDoneResultKeyString : str = "pressDoneResult"
capPressDoneDatetimeKeyString : str = "capPressDatetime"
freeRotationTorque1ValueKeyString : str = "rotation1Value"
freeRotationTorque1ResultKeyString : str = "rotation1Result"
freeRotationTorque1DatetimeKeyString : str = "rotationTorque1Datetime"
overallResultKeyString : str = "overallResult"
connectionStatusKeyString : str = "connectionStatus"

cameraServerStatusKeyString : str = "camerastatus"
ioServerStatusKeyString : str = "iostatus"
qrCodeServerStatusKeyString : str = "qrcodestatus"
dbServerStatusKeyString : str = "dbstatus"
alarmStatusKeyString : str = "alarmstatus"
emergencyStatusKeyString : str = "emergencystatus"

# Various commands
ok : str = CosThetaConfigurator.getInstance().getOkCommand()
notok : str = CosThetaConfigurator.getInstance().getNotOKCommand()

startCommand : str = CosThetaConfigurator.getInstance().getStartCommand()
stopCommand : str = CosThetaConfigurator.getInstance().getStopCommand()
exitCommand : str = CosThetaConfigurator.getInstance().getExitCommand()
requestCommand : str = CosThetaConfigurator.getInstance().getRequestCommand()
updateValueCommand : str = CosThetaConfigurator.getInstance().getUpdateValueCommand()
takePictureCommand : str = CosThetaConfigurator.getInstance().getTakePictureCommand()
readQRCodeCommand : str = CosThetaConfigurator.getInstance().getReadQRCodeCommand()
noActionCommand : str = CosThetaConfigurator.getInstance().getNoActionCommand()
moveAheadToNextComponent : str = CosThetaConfigurator.getInstance().getMoveAheadToNextComponentCommand()
# beepCommand = CosThetaConfigurator.getInstance().getDiscInterlockMessage()

stoppedResponse : str = CosThetaConfigurator.getInstance().getStoppedResponse()
rejectResponse : str = CosThetaConfigurator.getInstance().getRejectResponse()

# Various queues

io2feq : str = CosThetaConfigurator.getInstance().getIOToFrontEndQueue()
io2cameraq : str = CosThetaConfigurator.getInstance().getIOToCameraQueue()
io2qrcodeq : str = CosThetaConfigurator.getInstance().getIOToQRCodeQueue()
io2qrcodeabortq : str = CosThetaConfigurator.getInstance().getIOToQRCodeAbortQueue()
io2hbq : str = CosThetaConfigurator.getInstance().getIOToHeartbeatQueue()
qrcode2ioq : str = CosThetaConfigurator.getInstance().getQRCodeToIOQueue()
qrcode2feq : str = CosThetaConfigurator.getInstance().getQRCodeToFrontendQueue()
qrcode2hbq : str = CosThetaConfigurator.getInstance().getQRCodeToHeartbeatQueue()
qrcode2cameraq : str = CosThetaConfigurator.getInstance().getQRCodeToCameraQueue()
fe2ioq : str = CosThetaConfigurator.getInstance().getFrontendToIOQueue()
fe2dbq : str = CosThetaConfigurator.getInstance().getFrontendToDatabaseQueue()
fe2hbq : str = CosThetaConfigurator.getInstance().getFrontendToHeartbeatQueue()
camera2ioq : str = CosThetaConfigurator.getInstance().getCameraToIOQueue()
camera2feq : str = CosThetaConfigurator.getInstance().getCameraToFrontendQueue()
camera2hbq : str = CosThetaConfigurator.getInstance().getCameraToHeartbeatQueue()
db2hbq : str = CosThetaConfigurator.getInstance().getDatabaseToHeartbeatQueue()
hb2feq : str = CosThetaConfigurator.getInstance().getHeartbeatToFrontendQueue()
hb2ioq : str = CosThetaConfigurator.getInstance().getHeartbeatToIOQueue()
alarmq : str = CosThetaConfigurator.getInstance().getAlarmQueue()
emergencyq : str = CosThetaConfigurator.getInstance().getEmergencyQueue()
stopQ : str = CosThetaConfigurator.getInstance().getStopCommandQueue()
stoppedResponseQ : str = CosThetaConfigurator.getInstance().getStoppedResponseQueue()

# Empty Image

blankWhiteImage = 255 * np.ones(shape=(720, 1280, 3), dtype=np.uint8)
blankWhiteImage = cv2.putText(blankWhiteImage, f"Picture Not Received", (500, 300), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (255,0,0), 2, cv2.LINE_AA)

ActionType = Literal[updateValueCommand, takePictureCommand, readQRCodeCommand, noActionCommand, moveAheadToNextComponent, ABORT]
ResultType = Literal[ok,notok]
ConnectionStatusType = Literal[DEAD, ALIVE]
ComponentName = Literal[DOST, DOSTPLUS, GARUDA]

# Redis Connection For Clearing Key Queues
redisHostname: str = CosThetaConfigurator.getInstance().getRedisHost()
redisPort: int = CosThetaConfigurator.getInstance().getRedisPort()
redisPoolForClearingKeyQueues = redis.ConnectionPool(host=redisHostname, port=redisPort, max_connections=3)

# ***********************************************************************************

def validate_image(image: Union[np.ndarray, None]) -> bool:
    """Validate that an image is a valid NumPy array for OpenCV."""
    if image is None:
        # printBoldRed("Image is None")
        return False
    if not isinstance(image, np.ndarray):
        # printBoldRed(f"Image is not a NumPy array, got {type(image)}")
        return False
    if image.size == 0:
        # printBoldRed(f"Image is empty: {image.shape}")
        return False
    if image.dtype != np.uint8:
        # printBoldRed(f"Invalid image dtype: {image.dtype}, expected np.uint8")
        return False
    return True

# ***********************************************************************************

def sendImageWithResult(redisConnection: redis.client.Redis, anImage: Union[np.ndarray, None], queueName: str = commonStreamKey,
                        aProducer: str = "Producer", result: ResultType = ok, trackTime: bool = False, handshake : bool = False):
    # print(f'Image shape is {anImage.shape} and anImage dtype is {anImage.dtype}')
    # printBoldBlue(f"Redis connection is of type : {type(redisConnectionLeftCameraPicture)}")
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot send image.")
        # raise Exception("Redis Connection is None")
        return False
    if anImage is None:
        printBoldRed(f"Image is None. Cannot send image.")
        return False
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot send image.")
        return False
    if trackTime:
        time1 : float = time.time()
    buffer = None
    try:
        if isinstance(anImage, np.ndarray) and anImage is not None:
            retval, buffer = cv2.imencode('.png', anImage)
    except Exception as e:
        # raise e
        return False
    imageAsMessage = ""
    if buffer is not None:
        imageAsMessage = np.array(buffer).tobytes()
    # printBoldBlue(f"Encoded startingImage is of type : {type(message)}")
    data = {
        timeKeyString: getCurrentTimeInMS(),
        producerKeyString: aProducer,
        originalImageKeyString: imageAsMessage,
        resultKeyString: result if not handshake else HANDSHAKE
    }
    try:
        resp = redisConnection.xadd(queueName, data)
        if trackTime:
            time2 : float = time.time()
            timeTaken = round((time2 - time1) * 1000, 2)
            # printPlain(f'{queueName} : Producer sent anImage in {timeTaken} ms')
        return True
    except ConnectionError as e1:
        # raise e1
        # return False
        pass
    return False

# ***********************************************************************************

def sendData(redisConnection: redis.client.Redis, data: dict, queueName: str = commonStreamKey,
             aProducer: str = "Producer", trackTime: bool = False):
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot send data.")
        # raise Exception("Redis Connection is None")
        return False
    if data is None:
        printBoldRed(f"Data is None. Cannot send data.")
        return False
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot send data.")
        return False
    else:
        # printLight(f"Queue Name is {queueName}")
        pass
    if trackTime:
        time1 : float = time.time()
    data[timeKeyString] = getCurrentTimeInMS()
    data[producerKeyString] = aProducer
    try:
        resp = redisConnection.xadd(queueName, data)
        if trackTime:
            time2 : float = time.time()
            timeTaken = round((time2 - time1) * 1000, 2)
            # printPlain(f'{queueName} : Producer sent data in {timeTaken} ms')
        if ("hb" not in queueName) and ("alarmQ" not in queueName) and ("logging" not in queueName):
            # printPlain(f'{queueName} : Producer sent {data = }')
            pass
        return True
    except ConnectionError as e1:
        printBoldRed(f"Error {e1} while sending data from {aProducer}")
        # raise e1
    return False

# ***********************************************************************************

def sendStopCommand(redisConnection: redis.client.Redis, aProducer : str = "Producer"):
    # printBoldRed(f"Sending stop command from process {os.getpid()}")
    sendData(redisConnection=redisConnection, data={genericdataKeyString: stopCommand}, queueName=stopQ, aProducer=aProducer)

def sendStoppedResponse(redisConnection: redis.client.Redis, aProducer: str = "Producer"):
    sendData(redisConnection=redisConnection, data={genericdataKeyString: stoppedResponse}, queueName=stoppedResponseQ, aProducer=aProducer)


# ***********************************************************************************

sleep_ms: int = 5000

# RETURNS timestamp, producer, and ndarray
def getImage(redisConnection: redis.client.Redis, queueName: str = commonStreamKey, block : int = sleep_ms, trackTime: bool = False):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, None, None
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot receive data.")
        return None, None, None
    last_id = 0
    decodedImage = None
    timeOfMessage = None
    aProducer = None
    try:
        resp = redisConnection.xread(
            {queueName: last_id}, count=1, block=block
        )
        if resp:
            if trackTime:
                time1 : float = time.time()
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            newData = {}
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value
            timeOfMessage = newData[timeKeyString].decode('utf-8')
            aProducer = newData[producerKeyString].decode('utf-8')
            decodedImage = blankWhiteImage
            try:
                if newData[originalImageKeyString] is not None:
                    decodedImage = cv2.imdecode(np.frombuffer(newData[originalImageKeyString], np.uint8), 1)
            except:
                printBoldRed("Facing problem in decoding image from byte stream")
                pass
            redisConnection.xdel(queueName, last_id)
            # printBoldBlue(f"{timeOfMessage = }; {aProducer = }; {decodedImage.shape}")
            if trackTime:
                time2 : float = time.time()
                timeTaken = round((time2 - time1) * 1000, 2)
                # printPlain(f'{queueName} : REDIS ID --> {last_id} got from redis queue in {timeTaken} ms')
                # printPlain(f'{queueName} : Consumer received data in {timeTaken} ms')
            # if isinstance(decodedImage, np.ndarray):
            #     printBoldBlue(f'Decoded startingImage has shape {decodedImage.shape} and type {decodedImage.dtype}')
    except ConnectionError as e1:
        printBoldRed(f"Error while receiving startingImage : {e1}")
        # raise e1
        # return None, None, None
    return timeOfMessage, aProducer, decodedImage

# RETURNS timestamp, producer, result, and ndarray
def getImageWithResult(redisConnection: redis.client.Redis, queueName: str = commonStreamKey, block : int = sleep_ms, trackTime: bool = False):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, None, None, None
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot receive data.")
        return None, None, None, None
    last_id = 0
    decodedImage = None
    decodedResult = None
    timeOfMessage = None
    aProducer = None
    try:
        redisConnection.xtrim(queueName, 1)
        resp = redisConnection.xread(
            {queueName: last_id}, count=1, block=block
        )
        if resp:
            if trackTime:
                time1 : float = time.time()
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            newData = {}
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value
            decodedResult = newData[resultKeyString].decode('utf-8')
            timeOfMessage = newData[timeKeyString].decode('utf-8')
            aProducer = newData[producerKeyString].decode('utf-8')
            decodedImage = blankWhiteImage
            if decodedResult != HANDSHAKE:
                try:
                    if newData[originalImageKeyString] is not None:
                        decodedImage = cv2.imdecode(np.frombuffer(newData[originalImageKeyString], np.uint8), 1)
                except:
                    printBoldRed("Facing problem in decoding image from byte stream")
                    pass
            redisConnection.xdel(queueName, last_id)
            # printBoldBlue(f"{decodedResult = }; {timeOfMessage = }; {aProducer = }; {decodedImage.shape}")
            if trackTime:
                time2 : float = time.time()
                timeTaken = round((time2 - time1) * 1000, 2)
                # printPlain(f'{queueName} : REDIS ID --> {last_id} got from redis queue in {timeTaken} ms')
                # printPlain(f'{queueName} : Consumer received data in {timeTaken} ms')
            # if isinstance(decodedImage, np.ndarray):
            #     printBoldBlue(f'Decoded startingImage has shape {decodedImage.shape} and type {decodedImage.dtype}')
    except ConnectionError as e1:
        printBoldRed(f"Error while receiving image with result : {e1}")
        # raise e1
    if decodedResult == HANDSHAKE:
        return timeOfMessage, aProducer, None, None
    return timeOfMessage, aProducer, decodedResult, decodedImage

# RETURNS timestamp, and data as a dictionary
def getData(redisConnection: redis.client.Redis, queueName: str = commonStreamKey, trackTime: bool = False, block : int = sleep_ms):
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, None
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot receive data.")
        return None, None
    last_id = 0
    # done: bool = False
    newData = {}
    timeOfMessage = None
    # while not done:
    try:
        resp = redisConnection.xread(
            {queueName: last_id}, count=1, block=block
        )
        if resp:
            if trackTime:
                time1 = time.time()
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key].decode('utf-8')
                newData[key.decode("utf-8")] = value
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(queueName, last_id)
            if trackTime:
                time2 = time.time()
                timeTaken = round((time2 - time1) * 1000, 2)
                # printPlain(f'{queueName} : Consumer received data in {timeTaken} ms')
                # printPlain(f'{queueName} : REDIS ID --> {last_id}; data --> {data} got from redis queue in {timeTaken} ms')
            # done = True
    except ConnectionError as e1:
        printBoldRed(f"Error while receiving data : {e1}")
        # raise e1
        pass
    return timeOfMessage, newData

# RETURNS timestamp and boolean
def getStopCommandFromQueue(redisConnection: redis.client.Redis, block : int = 1):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, None
    # printBoldRed(f"{getGeneralLoggingMessage(getFullyQualifiedName(__file__), 'getStopCommand() invoked')}")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        resp = redisConnection.xread({stopQ: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value
            timeOfMessage = newData[timeKeyString].decode("utf-8")
    except ConnectionError as e1:
        printBoldRed(f"Error while receiving stop command : {e1}")
        # raise e1
        return None, None
    stopNow = None
    try:
        stopNow = newData[genericdataKeyString].decode('utf-8')
    except:
        pass
    # printBoldRed(f"{getGeneralLoggingMessage(getFullyQualifiedName(__file__), 'in getStopCommand()')} {stopNow =}")
    if stopNow is not None:
        if stopNow == stopCommand:
            # printBoldRed(f"Got stop command in process {os.getpid()}")
            return timeOfMessage, True
    return timeOfMessage, False

# RETURNS timestamp, sender of the stopped response, and the stopped response
def getStoppedResponseFromQueue(redisConnection: redis.client.Redis, block : int = 1):
    # Note that there is no 'while not done' loop in this code. This ensures that this doesn't block in the calling program.
    # The calling program will need to implement a loop to call this functions
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, "", ""
    last_id = 0
    newData = {}
    timeOfMessage = None

    try:
        resp = redisConnection.xread({stoppedResponseQ: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value
            timeOfMessage = newData[timeKeyString].decode("utf-8")
            redisConnection.xdel(stoppedResponseQ, last_id)
    except ConnectionError as e1:
        printBoldRed(f"Error while receiving data : {e1}")
        return timeOfMessage, "", ""
        # raise e1
    producer = None
    stoppedNow = None
    try:
        producer = newData[producerKeyString].decode('utf-8')
        stoppedNow = newData[genericdataKeyString].decode('utf-8')
    except:
        pass
    if (producer is not None) and (stoppedNow is not None):
        if stoppedNow == stoppedResponse:
            return timeOfMessage, producer, stoppedResponse
    return timeOfMessage, "", ""


def getMessageCount(redisConnection: redis.client.Redis, queueName: str = commonStreamKey):
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot get count.")
        return -1
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot receive data.")
        return -1
    try:
        numberOfEntries = redisConnection.xlen(queueName)
    except ConnectionError as e1:
        printBoldRed(f"Error while getting message count : {e1}")
        return -1
    return numberOfEntries

# RETURNS timestamp and boolean
def getTakeNextPictureCommandFromCameraId(redisConnection: redis.client.Redis, cameraId : int = 1, block : int = 1):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    cameraQ = CosThetaConfigurator.getInstance().getCameraTakePicQueue(cameraId=cameraId)
    try:
        redisConnection.xtrim(cameraQ, 1)
        resp = redisConnection.xread({cameraQ: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(cameraQ, last_id)
    except ConnectionError as e1:
        printBoldRed(f"Error while getting next picture command : {e1}")
        # raise e1
        return None, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == TAKE_NEXT_PICTURE):
            return timeOfMessage, True
    except:
        return timeOfMessage, False
    return timeOfMessage, False

# RETURNS timestamp and boolean
def getRequestResultCommandFromIOServer(redisConnection: redis.client.Redis, requestResultQ : str, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(requestResultQ, 1)
        resp = redisConnection.xread({requestResultQ: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(requestResultQ, last_id)
    except ConnectionError as e1:
        printBoldRed(f"Error while receiving request-result command : {e1}")
        # raise e1
        return None, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return None, False
    except:
        pass
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == requestCommand):
            return timeOfMessage, True
    except:
        return timeOfMessage, False
    return timeOfMessage, False

def getTakeNextPictureCommandFromCameraQ(redisConnection: redis.client.Redis, cameraQ : str, block : int = 1):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return None, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(cameraQ, 1)
        # printBold(f"After trimming {cameraQ} to 1")
        resp = redisConnection.xread({cameraQ: last_id}, count=1, block=block)
        # printBold(f"Got resp in {cameraQ} as {resp}")
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(cameraQ, last_id)
    except ConnectionError as e1:
        printBoldRed(f"Error while getting next picture command : {e1}")
        # raise e1
        return None, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return None, False
    except:
        pass
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == TAKE_NEXT_PICTURE):
            return timeOfMessage, True
    except:
        return timeOfMessage, False
    return timeOfMessage, False


# ********************************** RECORDING COMMANDS START - RARELY USED *************************

def sendRecordingStart(redisConnection: redis.client.Redis, cameraId: int = 1):
    queueName = CosThetaConfigurator.getInstance().getRecordingQueue(cameraId=cameraId)
    sendData(redisConnection, {genericdataKeyString: startCommand}, queueName=queueName)

def sendRecordingStop(redisConnection: redis.client.Redis, cameraId: int = 1):
    queueName = CosThetaConfigurator.getInstance().getRecordingQueue(cameraId=cameraId)
    sendData(redisConnection, {genericdataKeyString: stopCommand}, queueName=queueName)

def sendRecordingExit(redisConnection: redis.client.Redis, cameraId: int = 1):
    queueName = CosThetaConfigurator.getInstance().getRecordingQueue(cameraId=cameraId)
    sendData(redisConnection, {genericdataKeyString: exitCommand}, queueName=queueName)

def getRecordingCommand(redisConnection: redis.client.Redis, recordingQueueName: str, block : int = 2):
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        raise Exception("Redis Connection is None")
    last_id = 0
    newData = {}
    try:
        resp = redisConnection.xread({recordingQueueName: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
        else:
            return ""
    except ConnectionError as e1:
        # printBoldRed(f"Error while receiving data : {e1}")
        raise e1
    return newData[genericdataKeyString]

# ********************************** RECORDING COMMANDS END *************************

def getDiscInterlockMessage(redisConnection: redis.client.Redis, block : int = 1):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot receive data.")
        raise Exception("Redis Connection is None")
    # printBoldRed(f"{getGeneralLoggingMessage(getFullyQualifiedName(__file__), 'getStopCommand() invoked')}")
    last_id = 0
    newData = {}
    timeOfMessage = None
    producer = None
    connAlarmQ = CosThetaConfigurator.getInstance().getConnectionAlarmQueue()
    try:
        resp = redisConnection.xread({connAlarmQ: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value
            timeOfMessage = newData[timeKeyString].decode("utf-8")
            producer = newData[producerKeyString].decode("utf-8")
            # xtrim removed, because trimming the queue leads to a delay as well as missing timely updates
            # redisConnection.xtrim(connAlarmQ, 0)
            redisConnection.xdel(connAlarmQ, last_id)
    except ConnectionError as e1:
        # SlaveFileLogger.getInstance().logTakeAction(logSource,
        #                                             f"Could not get stop command due to {e1}",
        #                                             Logger.PROBLEM)
        # SlaveConsoleLogger.getInstance().logTakeAction(logSource,
        #                                             f"Could not get stop command due to {e1}",
        #                                             Logger.PROBLEM)
        # printBoldRed(f"Error while receiving data : {e1}")
        raise e1
    currentStatus = False
    try:
        currentStatus = newData[genericdataKeyString].decode('utf-8')
    except:
        pass
    # printBoldRed(f"{getGeneralLoggingMessage(getFullyQualifiedName(__file__), 'in getStopCommand()')} {stopNow =}")
    if currentStatus is not None:
        if currentStatus == ok:
            # printBoldRed(f"Got stop command in process {os.getpid()}")
            return timeOfMessage, producer, False
    return timeOfMessage, producer, True

# ********************************** COMMUNICATION OUTWARD FROM IO SERVER *************************

def sendDataFromIOServerToFEServer(redisConnection : redis.client.Redis, currentMachineState : MachineState, moveToState : MachineState = MachineState.INVALID_STATE, result : ResultType = ok, action : ActionType = updateValueCommand, value : Union[str, float] = -1., aProducer : str = "IOServer", handshake : bool = False):
    data = {currentMachineStateKeyString: currentMachineState, move2StateKeyString: moveToState, actionKeyString: action, valueKeyString: value, resultKeyString : result}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=io2feq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=io2feq, aProducer=f"{aProducer}")

def sendDataFromIOServerToCameraServer(redisConnection : redis.client.Redis, currentMachineState : MachineState, action : ActionType = takePictureCommand, aProducer : str = "IOServer", handshake : bool = False):
    data = {currentMachineStateKeyString: currentMachineState, actionKeyString: action}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=io2cameraq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=io2cameraq, aProducer=f"{aProducer}")

def sendDataFromIOServerToQRCodeServer(redisConnection : redis.client.Redis, currentMachineState : MachineState = MachineState.READ_QR_CODE, action : ActionType = readQRCodeCommand, aProducer : str = "IOServer", handshake : bool = False):
    data = {currentMachineStateKeyString: currentMachineState, actionKeyString: action}
    return sendData(redisConnection=redisConnection, data=data, queueName=io2qrcodeq, aProducer=f"{aProducer}")

def sendAbortFromIOServerToQRCodeServer(redisConnection : redis.client.Redis, currentMachineState : MachineState = MachineState.READ_QR_CODE, action : ActionType = ABORT, aProducer : str = "IOServer", handshake : bool = False):
    # printBoldBlue(f"Inside sendAbortFromIOServerToQRCodeServer()...")
    data = {currentMachineStateKeyString: currentMachineState, actionKeyString: action}
    # printBoldBlue(f"...where about to send data {data}")
    return sendData(redisConnection=redisConnection, data=data, queueName=io2qrcodeabortq, aProducer=f"{aProducer}")

def sendHeartbeatFromIOServerToHeartbeatServer(redisConnection : redis.client.Redis, status : ConnectionStatusType, aProducer : str = "IOServer"):
    return sendData(redisConnection=redisConnection, data={connectionStatusKeyString: status}, queueName=io2hbq, aProducer=f"{aProducer}")

def sendEmergencyAbortFromIOServerToFEServer(redisConnection : redis.client.Redis, status : ResultType = ok, aProducer : str = "IOServer"):
    return sendData(redisConnection=redisConnection, data={emergencyStatusKeyString: status}, queueName=emergencyq, aProducer=f"{aProducer}")

# ********************************** COMMUNICATION INWARD INTO IO SERVER *************************

def readDataInIOServerFromCameraServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInIOServerFromCameraServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInIOServerFromCameraServer()")
        return MachineState.INVALID_STATE, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(camera2ioq, 1)
        resp = redisConnection.xread({camera2ioq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(camera2ioq, last_id)
            redisConnection.xtrim(camera2ioq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return MachineState.INVALID_STATE, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return MachineState.INVALID_STATE, False
    except:
        pass

    try:
        if (newData[currentMachineStateKeyString] is not None) and (newData[resultKeyString] is not None):
            currentMachineState = MachineState.getMachineStateFromString(newData[currentMachineStateKeyString])
            result = (newData[resultKeyString] == ok)
            # print(f"In readDataInIOServerFromCameraServer(), {currentMachineState = } and {result = }")
            return currentMachineState, result
    except:
        return MachineState.INVALID_STATE, False

    return MachineState.INVALID_STATE, False

def readDataInIOServerFromQRCodeServer(redisConnection: redis.client.Redis, block : int = 500) -> Tuple[bool, str]:
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    # Returns a tuple: (qrCodeIsOK: bool, qrCode: str)
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInIOServerFromCameraServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInIOServerFromQRCodeServer()")
        return False, ""
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(qrcode2ioq, 1)
        resp = redisConnection.xread({qrcode2ioq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(qrcode2ioq, last_id)
            redisConnection.xtrim(qrcode2ioq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False, ""
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return False, ""
    except:
        pass

    try:
        if (newData[qrCodeStatusKeyString] is not None):
            qrCodeIsOK = (newData[qrCodeStatusKeyString] == ok)
            qrCode = newData.get(qrCodeKeyString, "")
            return qrCodeIsOK, qrCode
    except:
        return False, ""

    return False, ""

def readDataInIOServerFromFEServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInIOServerFromFEServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInIOServerFromQRCodeServer()")
        return False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(fe2ioq, 1)
        resp = redisConnection.xread({fe2ioq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(fe2ioq, last_id)
            redisConnection.xtrim(fe2ioq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return False
    except:
        pass

    try:
        if (newData[connectionStatusKeyString] is not None):
            connStatus = (newData[connectionStatusKeyString] == ok)
            return connStatus
    except:
        return False

    return False

def readCombinedHeartbeatInIOServerFromHeartbeatServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readCombinedHeartbeatInIOServerFromHeartbeatServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInCameraServerFromIOServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(hb2ioq, 1)
        resp = redisConnection.xread({hb2ioq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(hb2ioq, last_id)
            redisConnection.xtrim(hb2ioq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[connectionStatusKeyString] is not None) and (newData[connectionStatusKeyString] == ALIVE):
            return True
    except:
        return False
    return False


# ********************************** COMMUNICATION OUTWARD FROM FE SERVER *************************

def sendDataFromFEServerToDatabaseServer(redisConnection : redis.client.Redis,
                                         qrCode : str,
                                         knucklePicture : Union[np.ndarray, None], knuckleResult : ResultType, knuckleDatetime : str,
                                         hubAndBottomBearingPicture : Union[np.ndarray, None], hubAndBottomBearingResult : ResultType, hubAndBottomBearingDatetime : str,
                                         topBearingPicture : Union[np.ndarray, None], topBearingResult : ResultType, topBearingDatetime : str,
                                         nutAndPlateWasherPicture : Union[np.ndarray, None], nutAndPlateWasherResult : ResultType, nutAndPlateWasherDatetime : str,
                                         tighteningTorque1 : Union[str, float], tighteningTorque1Result : ResultType, tighteningTorque1Datetime : str,
                                         freeRotationDone :  ResultType, freeRotationDatetime : str,
                                         componentPressBunkCheckingPicture: Union[np.ndarray, None], componentPressBunkCheckingResult : ResultType, componentPressBunkCheckDatetime : str,
                                         componentPressDone :  ResultType, componentPressDoneDatetime : str,
                                         noBunkCheckingPicture: Union[np.ndarray, None], noBunkCheckingResult : ResultType, noBunkCheckDatetime : str,
                                         tighteningTorque2 : Union[str, float], tighteningTorque2Result : ResultType, tighteningTorque2Datetime : str,
                                         splitPinAndWasherPicture: Union[np.ndarray, None], splitPinAndWasherResult : ResultType, splitPinAndWasherDatetime : str,
                                         capCheckingPicture: Union[np.ndarray, None], capCheckingResult : ResultType, capCheckingDatetime : str,
                                         bunkCheckingPicture: Union[np.ndarray, None], capPressBunkCheckingResult : ResultType, capPressBunkCheckDatetime : str,
                                         pressDone: ResultType, capPressDoneDatetime : str,
                                         freeRotationTorque1: Union[str, float], freeRotationTorque1Result: ResultType, freeRotationTorque1Datetime : str,
                                         overallResult : ResultType,
                                         aProducer : str = "FEServer"):

    # print("Reached here - 1")
    if (qrCode is None) or (qrCode == ""):
        return

    knucklePictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(knucklePicture):
            retval, buffer = cv2.imencode('.png', knucklePicture)
            if buffer is not None:
                knucklePictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting knuckle picture - {e}")
        pass

    # print("Reached here - 2")

    hubAndBottomBearingPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(hubAndBottomBearingPicture):
            retval, buffer = cv2.imencode('.png', hubAndBottomBearingPicture)
            if buffer is not None:
                hubAndBottomBearingPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting hub and first bearing picture - {e}")
        pass

    # print("Reached here - 3")

    topBearingPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(topBearingPicture):
            retval, buffer = cv2.imencode('.png', topBearingPicture)
            if buffer is not None:
                topBearingPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting second bearing picture - {e}")
        pass

    # print("Reached here - 4")

    nutAndPlateWasherPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(nutAndPlateWasherPicture):
            retval, buffer = cv2.imencode('.png', nutAndPlateWasherPicture)
            if buffer is not None:
                nutAndPlateWasherPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting nut and plate washer picture - {e}")
        pass

    # print("Reached here - 5")

    componentPressBunkCheckingPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(componentPressBunkCheckingPicture):
            retval, buffer = cv2.imencode('.png', componentPressBunkCheckingPicture)
            if buffer is not None:
                componentPressBunkCheckingPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting bunk check picture before component press - {e}")
        pass

    noBunkCheckingPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(noBunkCheckingPicture):
            retval, buffer = cv2.imencode('.png', noBunkCheckingPicture)
            if buffer is not None:
                noBunkCheckingPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting no bunk check picture after component press - {e}")
        pass

    splitPinAndWasherPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(splitPinAndWasherPicture):
            retval, buffer = cv2.imencode('.png', splitPinAndWasherPicture)
            if buffer is not None:
                splitPinAndWasherPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting split pin and washer picture - {e}")
        pass

    # print("Reached here - 6")

    capCheckingPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(capCheckingPicture):
            retval, buffer = cv2.imencode('.png', capCheckingPicture)
            if buffer is not None:
                capCheckingPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting cap check picture - {e}")
        pass

    # print("Reached here - 7")

    capPressBunkCheckingPictureAsMessage = bytes(EMPTY_IMAGE_STRING, "utf-8")
    try:
        if validate_image(bunkCheckingPicture):
            retval, buffer = cv2.imencode('.png', bunkCheckingPicture)
            if buffer is not None:
                capPressBunkCheckingPictureAsMessage = np.array(buffer).tobytes()
    except Exception as e:
        printBoldRed(f"Problem in getting bunk check picture before cap press - {e}")
        pass

    # print("Reached here - 8")

    data = {
        qrCodeKeyString : qrCode,
        knucklePictureKeyString : knucklePictureAsMessage, knuckleCheckResultKeyString : knuckleResult,
        knuckleDatetimeKeyString: knuckleDatetime,
        hubAndBottomBearingPictureKeyString : hubAndBottomBearingPictureAsMessage, hubAndBottomBearingCheckResultKeyString : hubAndBottomBearingResult,
        hubAndBottomBearingDatetimeKeyString : hubAndBottomBearingDatetime,
        topBearingPictureKeyString : topBearingPictureAsMessage, topBearingCheckResultKeyString : topBearingResult,
        topBearingDatetimeKeyString : topBearingDatetime,
        nutAndPlateWasherPictureKeyString : nutAndPlateWasherPictureAsMessage, nutAndPlateWasherCheckResultKeyString : nutAndPlateWasherResult,
        nutAndPlateWasherDatetimeKeyString : nutAndPlateWasherDatetime,
        tighteningTorque1ValueKeyString : str(tighteningTorque1), tighteningTorque1ResultKeyString : tighteningTorque1Result,
        tighteningTorque1DatetimeKeyString : tighteningTorque1Datetime,
        freeRotationDoneKeyString : freeRotationDone,
        freeRotationDatetimeKeyString : freeRotationDatetime,
        componentPressBunkPictureKeyString: componentPressBunkCheckingPictureAsMessage, componentPressBunkCheckResultKeyString: componentPressBunkCheckingResult,
        componentPressBunkCheckDatetimeKeyString : componentPressBunkCheckDatetime,
        componentPressDoneResultKeyString : componentPressDone,
        componentPressDoneDatetimeKeyString : componentPressDoneDatetime,
        noBunkPictureKeyString : noBunkCheckingPictureAsMessage, noBunkCheckResultKeyString : noBunkCheckingResult,
        noBunkCheckDatetimeKeyString : noBunkCheckDatetime,
        tighteningTorque2ValueKeyString : str(tighteningTorque2), tighteningTorque2ResultKeyString : tighteningTorque2Result,
        tighteningTorque2DatetimeKeyString: tighteningTorque2Datetime,
        splitPinAndWasherPictureKeyString : splitPinAndWasherPictureAsMessage, splitPinAndWasherCheckResultKeyString : splitPinAndWasherResult,
        splitPinAndWasherCheckDatetimeKeyString: splitPinAndWasherDatetime,
        capPictureKeyString : capCheckingPictureAsMessage, capCheckResultKeyString : capCheckingResult,
        capCheckDatetimeKeyString: capCheckingDatetime,
        capPressBunkPictureKeyString : capPressBunkCheckingPictureAsMessage, capPressBunkCheckResultKeyString : capPressBunkCheckingResult,
        capPressBunkCheckDatetimeKeyString: capPressBunkCheckDatetime,
        capPressDoneResultKeyString : pressDone,
        capPressDoneDatetimeKeyString: capPressDoneDatetime,
        freeRotationTorque1ValueKeyString: str(freeRotationTorque1), freeRotationTorque1ResultKeyString: freeRotationTorque1Result,
        freeRotationTorque1DatetimeKeyString: freeRotationTorque1Datetime,
        overallResultKeyString : overallResult
    }
    # print(f"size of data is {sys.getsizeof(data)}")
    # print(f"{data = }")
    return sendData(redisConnection=redisConnection, data=data, queueName=fe2dbq, aProducer=f"{aProducer}")

def sendDataFromFEServerToIOServer(redisConnection : redis.client.Redis, connectionStatus : ResultType, aProducer : str = "FEServer", handshake : bool = False):
    if not handshake:
        return sendData(redisConnection=redisConnection, data={connectionStatusKeyString : connectionStatus}, queueName=fe2ioq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=fe2ioq, aProducer=f"{aProducer}")

def sendHeartbeatFromFEServerToHeartbeatServer(redisConnection : redis.client.Redis, status : ConnectionStatusType = ok, aProducer : str = "FEServer"):
    return sendData(redisConnection=redisConnection, data={connectionStatusKeyString: status}, queueName=fe2hbq, aProducer=f"{aProducer}")

# ********************************** COMMUNICATION INWARD INTO FE SERVER *************************

# returns 3 things - actual qrcode, qrcode display string, qrcode status
def readDataInFEServerFromQRCodeServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInFEServerFromQRCodeServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInFEServerFromQRCodeServer()")
        return None, None, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(qrcode2feq, 1)
        resp = redisConnection.xread({qrcode2feq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(qrcode2feq, last_id)
            redisConnection.xtrim(qrcode2feq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return None, None, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return None, None, False
    except:
        pass

    try:
        if (newData[qrCodeKeyString] is not None) and (newData[qrCodeDisplayKeyString] is not None):
            validQRCode = (newData[qrCodeStatusKeyString] == ok)
            actualQRCodeValue = newData[qrCodeKeyString]
            qrCodeDisplayString = newData[qrCodeDisplayKeyString]
            return actualQRCodeValue, qrCodeDisplayString, validQRCode
    except:
        return None, None, False

    return None, None, False

# returns 5 things - timeOfMessage, original image as an ndarray, processed image as an ndarray,
#                    the result of the evaluation (decodedResult) as an ok or notok, and the current machine state for which the evaluation was done
# IF decodedResult IS None, it is interpreted as if there is no message in the queue and therefore, the result should be ignored

def readDataInFEServerFromCameraServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call

    decodedOriginalImage = None
    decodedProcessedImage = None
    decodedResult = None
    timeOfMessage = None
    aProducer = None
    currentMachineState = MachineState.INVALID_STATE

    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInFEServerFromCameraServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return timeOfMessage, decodedOriginalImage, decodedProcessedImage, decodedResult, currentMachineState

    last_id = 0
    try:
        redisConnection.xtrim(camera2feq, 1)
        resp = redisConnection.xread(
            {camera2feq: last_id}, count=1, block=block
        )
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            newData = {}
            for key in keys:
                value = data[key]
                # NOTE : Since this message carries image bytes, DO NOT apply .decode('utf-8') to all the data
                newData[key.decode("utf-8")] = value

            decodedResult = newData[resultKeyString].decode('utf-8')
            timeOfMessage = newData[timeKeyString].decode('utf-8')
            currentMachineState = newData[currentMachineStateKeyString].decode('utf-8')
            currentMachineState = MachineState.getMachineStateFromString(currentMachineState)
            aProducer = newData[producerKeyString].decode('utf-8')
            decodedOriginalImage = blankWhiteImage
            decodedProcessedImage = blankWhiteImage
            if decodedResult != HANDSHAKE:
                try:
                    if newData[originalImageKeyString] is not None:
                        decodedOriginalImage = cv2.imdecode(np.frombuffer(newData[originalImageKeyString], np.uint8), 1)
                except:
                    printBoldRed("Facing problem in decoding original image from byte stream in readDataInFEServerFromCameraServer()")
                    pass
                try:
                    if newData[processedImageKeyString] is not None:
                        decodedProcessedImage = cv2.imdecode(np.frombuffer(newData[processedImageKeyString], np.uint8), 1)
                except:
                    printBoldRed(
                        "Facing problem in decoding processed image from byte stream in readDataInFEServerFromCameraServer()")
                    pass
            redisConnection.xdel(camera2feq, last_id)
            redisConnection.xtrim(camera2feq, 0)
            # printBoldBlue(f"{decodedResult = }; {timeOfMessage = }; {aProducer = }; {decodedImage.shape}")
            # if isinstance(decodedImage, np.ndarray):
            #     printBoldBlue(f'Decoded startingImage has shape {decodedImage.shape} and type {decodedImage.dtype}')
    except ConnectionError as e1:
        return timeOfMessage, None, None, None, MachineState.INVALID_STATE
    if decodedResult == HANDSHAKE:
        return timeOfMessage, None, None, None, MachineState.INVALID_STATE
    return timeOfMessage, decodedOriginalImage, decodedProcessedImage, decodedResult, currentMachineState

# returns 4 things - cameraServerStatus, qrCodeServerStatus, ioServerStatus, dbServerStatus as booleans, in that order
def readHeartbeatsInFEServerFromHeartbeatServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInFEServerFromHeartbeatServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return False, False, False, False
    last_id = 0
    cameraServerStatus = False
    qrCodeServerStatus = False
    ioServerStatus = False
    dbServerStatus = False
    newData = {}

    try:
        redisConnection.xtrim(hb2feq, 1)
        resp = redisConnection.xread({hb2feq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode('utf-8')
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(hb2feq, last_id)
            redisConnection.xtrim(hb2feq, 0)
    except ConnectionError as e1:
        return cameraServerStatus, qrCodeServerStatus, ioServerStatus, dbServerStatus

    try:
        cameraServerStatus = (newData[cameraServerStatusKeyString] == ALIVE)
        qrCodeServerStatus = (newData[qrCodeServerStatusKeyString] == ALIVE)
        ioServerStatus = (newData[ioServerStatusKeyString] == ALIVE)
        dbServerStatus = (newData[dbServerStatusKeyString] == ALIVE)
        return cameraServerStatus, qrCodeServerStatus, ioServerStatus, dbServerStatus
    except:
        return cameraServerStatus, qrCodeServerStatus, ioServerStatus, dbServerStatus


def readDataInFEServerFromIOServer(redisConnection: redis.client.Redis, block : int = 500):
    # returns 5 things - currentMachineState, moveToState, action, value, result

    # If 'moveToState' != -1, it implies that this message is ONLY for changing the currentMachineState of the machine to the new state.
    # Ignore the other values.

    # If 'moveToState' == -1, and action == updateValueCommand, it implies that this message is to update the result of the outcome
    # container for the current state with 'value'

    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInFEServerFromIOServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return MachineState.INVALID_STATE, MachineState.INVALID_STATE, None, None, notok

    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(io2feq, 1)
        resp = redisConnection.xread({io2feq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(io2feq, last_id)
            redisConnection.xtrim(io2feq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return MachineState.INVALID_STATE, MachineState.INVALID_STATE, None, None, notok

    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return MachineState.INVALID_STATE, MachineState.INVALID_STATE, None, None, notok
    except:
        pass

    try:
        if (newData[currentMachineStateKeyString] is not None):
            currentMachineState = MachineState.getMachineStateFromString(newData[currentMachineStateKeyString])
            moveToState = MachineState.getMachineStateFromString(newData[move2StateKeyString])
            action = newData[actionKeyString]
            value = newData[valueKeyString]
            result = newData[resultKeyString]
            try:
                value = float(value)
            except:
                pass

            return currentMachineState, moveToState, action, value, result
    except:
        return MachineState.INVALID_STATE, MachineState.INVALID_STATE, None, None, notok

    return MachineState.INVALID_STATE, MachineState.INVALID_STATE, None, None, notok

# returns a boolean value indicating that emergency button has been pressed
def readEmergencyAbortInFEServerFromIOServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readEmergencyAbortInCameraServerFromIOServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInCameraServerFromIOServer()")
        return False
    last_id = 0
    newData = {}
    timeOfMessage = None

    try:
        redisConnection.xtrim(emergencyq, 1)
        resp = redisConnection.xread({emergencyq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            try:
                redisConnection.xdel(emergencyq, last_id)
                redisConnection.xtrim(emergencyq, 0)
            except:
                pass
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return False
    except:
        pass

    try:
        if (newData[emergencyStatusKeyString] is not None) and (newData[emergencyStatusKeyString] == ok):
            return True
    except:
        return False

    return False

# ********************************** COMMUNICATION OUTWARD FROM QRCODE SERVER *************************

def sendDataFromQRCodeServerToFEServer(redisConnection : redis.client.Redis, qrCode : str, displayString : str, qrCodeStatus : ResultType = ok, aProducer : str = "QRCodeServer", handshake : bool = False):
    data = {qrCodeKeyString: qrCode, qrCodeDisplayKeyString : displayString, qrCodeStatusKeyString : qrCodeStatus}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=qrcode2feq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=qrcode2feq, aProducer=f"{aProducer}")

def sendDataFromQRCodeServerToIOServer(redisConnection : redis.client.Redis, qrCode : str = "", qrCodeStatus : ResultType = ok, aProducer : str = "QRCodeServer", handshake : bool = False):
    data = {qrCodeStatusKeyString: qrCodeStatus, qrCodeKeyString: qrCode}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=qrcode2ioq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=qrcode2ioq, aProducer=f"{aProducer}")

def sendComponentQRCodeFromQRCodeServerToCameraServer(redisConnection : redis.client.Redis, componentQRCode : str, aProducer : str = "QRCodeServer"):
    rValue =  sendData(redisConnection=redisConnection, data={componentQRCodeKeyString: componentQRCode}, queueName=qrcode2cameraq, aProducer=f"{aProducer}")
    return rValue

def sendHeartbeatFromQRCodeServerToHeartbeatServer(redisConnection : redis.client.Redis, status : ConnectionStatusType, aProducer : str = "QRCodeServer"):
    return sendData(redisConnection=redisConnection, data={connectionStatusKeyString: status}, queueName=qrcode2hbq, aProducer=f"{aProducer}")

# ********************************** COMMUNICATION INWARD INTO QRCODE SERVER *************************

# returns 2 values - timeOfMessage in milliseconds and a boolean whether the request is to read a newwidgets QR Code
def readDataInQRCodeServerFromIOServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInQRCodeServerFromIOServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInQRCodeServerFromIOServer()")
        return None, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(io2qrcodeq, 1)
        resp = redisConnection.xread({io2qrcodeq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(io2qrcodeq, last_id)
            redisConnection.xtrim(io2qrcodeq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return None, False

    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return None, False
    except:
        pass

    try:
        if (newData[actionKeyString] is not None) and (newData[actionKeyString] == readQRCodeCommand):
            return timeOfMessage, True
    except:
        return None, False

    return None, False


# returns 1 values - a boolean, whether to abort a read or not
def readAbortDataInQRCodeServerFromIOServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readAbortDataInQRCodeServerFromIOServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInQRCodeServerFromIOServer()")
        return False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(io2qrcodeabortq, 1)
        resp = redisConnection.xread({io2qrcodeabortq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            try:
                redisConnection.xdel(io2qrcodeabortq, last_id)
                redisConnection.xtrim(io2qrcodeabortq, 0)
            except:
                pass
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False

    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return False
    except:
        pass

    try:
        if (newData[actionKeyString] is not None) and (newData[actionKeyString] == ABORT):
            return True
    except:
        pass

    return False

# ********************************** COMMUNICATION OUTWARD FROM CAMERA SERVER *************************

def sendDataFromCameraServerToFEServer(redisConnection : redis.client.Redis, originalImage : Union[np.ndarray, None], processedImage : Union[np.ndarray, None], result : ResultType, currentMachineState : MachineState, aProducer : str = "CameraServer", handshake : bool = False):
    originalImageAsMessage = ""
    try:
        if validate_image(originalImage):
            retval, buffer = cv2.imencode('.png', originalImage)
            if buffer is not None:
                originalImageAsMessage = np.array(buffer).tobytes()
    except:
        pass

    processedImageAsMessage = ""
    try:
        if validate_image(processedImage):
            retval, buffer = cv2.imencode('.png', processedImage)
            if buffer is not None:
                processedImageAsMessage = np.array(buffer).tobytes()
    except:
        pass

    data = {originalImageKeyString: originalImageAsMessage, processedImageKeyString: processedImageAsMessage, resultKeyString : result, currentMachineStateKeyString : currentMachineState}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=camera2feq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=camera2feq, aProducer=f"{aProducer}")

def sendDataFromCameraServerToIOServer(redisConnection : redis.client.Redis, result : ResultType, currentMachineState : MachineState, aProducer : str = "CameraServer", handshake : bool = False):
    data = {resultKeyString: result, currentMachineStateKeyString : currentMachineState}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=camera2ioq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=camera2ioq, aProducer=f"{aProducer}")

def sendHeartbeatFromCameraServerToHeartbeatServer(redisConnection : redis.client.Redis, status : ConnectionStatusType, aProducer : str = "CameraServer"):
    return sendData(redisConnection=redisConnection, data={connectionStatusKeyString: status}, queueName=camera2hbq, aProducer=f"{aProducer}")

# ********************************** COMMUNICATION INWARD INTO CAMERA SERVER *************************

# returns 3 values - 1. timeOfMessage in milliseconds, 2. what state the machine is in, so that the appropriate
# routine can be called for evaluation of the picture, and 3. a boolean, whether the request is to take and evaluate a newwidgets picture
def readDataInCameraServerFromIOServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInCameraServerFromIOServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInCameraServerFromIOServer()")
        return None, None, False
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(io2cameraq, 1)
        resp = redisConnection.xread({io2cameraq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(io2cameraq, last_id)
            redisConnection.xtrim(io2cameraq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return None, None, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return None, None, False
    except:
        pass

    try:
        if (newData[actionKeyString] is not None) and (newData[actionKeyString] == takePictureCommand):
            currentMachineState = MachineState.getMachineStateFromString(newData[currentMachineStateKeyString])
            # printLight(f"Current state is {currentMachineState} and type is {type(currentMachineState)}")
            return timeOfMessage, currentMachineState, True
    except:
        return None, None, False

    return None, None, False

# data = {currentMachineStateKeyString: currentMachineState, move2StateKeyString: moveToState, actionKeyString: action, valueKeyString: value}

# returns component qrCode and a boolean value indicating that a valid component name has been found
def readComponentQRCodeInCameraServerFromQRCodeServer(redisConnection: redis.client.Redis, block : int = 500) -> Tuple[str | None, bool]:
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInCameraServerFromFEServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None in readDataInCameraServerFromIOServer()")
        return None, False
    last_id = 0
    newData = {}
    timeOfMessage = None

    try:
        # print(f"In readDataInCameraServerFromFEServer()")
        redisConnection.xtrim(qrcode2cameraq, 1)
        resp = redisConnection.xread({qrcode2cameraq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(qrcode2cameraq, last_id)
            redisConnection.xtrim(qrcode2cameraq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return None, False
    try:
        if (newData[genericdataKeyString] is not None) and (newData[genericdataKeyString] == HANDSHAKE):
            return None, False
    except:
        pass

    try:
        if (newData[componentQRCodeKeyString] is not None):
            return newData[componentQRCodeKeyString], True
    except:
        return None, False

    return None, False


# ********************************** COMMUNICATION OUTWARD FROM HEARTBEAT SERVER *************************

def sendHeartbeatsFromHeartbeatServerToFEServer(redisConnection : redis.client.Redis,
                                                qrCodeServerStatus : ConnectionStatusType,
                                                cameraServerStatus : ConnectionStatusType,
                                                ioServerStatus : ConnectionStatusType,
                                                dbServerStatus : ConnectionStatusType,
                                                aProducer : str = "HeartbeatServer", handshake : bool = False):
    data = {cameraServerStatusKeyString: cameraServerStatus, qrCodeServerStatusKeyString : qrCodeServerStatus,
            ioServerStatusKeyString : ioServerStatus, dbServerStatusKeyString : dbServerStatus}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=hb2feq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=hb2feq, aProducer=f"{aProducer}")

def sendCombinedHeartbeatFromHeartbeatServerToIOServer(redisConnection : redis.client.Redis,
                                                combinedConnectionStatus : ConnectionStatusType,
                                                aProducer : str = "HeartbeatServer", handshake : bool = False):
    # if combinedConnectionStatus == ALIVE:
    #     # printBoldGreen(f"About to send combined connection status as ALIVE")
    #     pass
    # else:
    #     printBoldRed(f"About to send combined connection status as DEAD from RedisUtils")
    data = {connectionStatusKeyString: combinedConnectionStatus}
    if not handshake:
        return sendData(redisConnection=redisConnection, data=data, queueName=hb2ioq, aProducer=f"{aProducer}")
    else:
        return sendData(redisConnection=redisConnection, data={genericdataKeyString: HANDSHAKE}, queueName=hb2ioq, aProducer=f"{aProducer}")

# ********************************** COMMUNICATION INWARD INTO HEARTBEAT SERVER *************************

def readDataInHeartbeatServerFromIOServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInHeartbeatServerFromIOServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInCameraServerFromIOServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(io2hbq, 1)
        resp = redisConnection.xread({io2hbq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(io2hbq, last_id)
            redisConnection.xtrim(io2hbq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[connectionStatusKeyString] is not None) and (newData[connectionStatusKeyString] == ALIVE):
            return True
    except:
        return False
    return False

def readDataInHeartbeatServerFromQRCodeServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInHeartbeatServerFromQRCodeServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInHeartbeatServerFromQRCodeServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(qrcode2hbq, 1)
        resp = redisConnection.xread({qrcode2hbq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(qrcode2hbq, last_id)
            redisConnection.xtrim(qrcode2hbq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[connectionStatusKeyString] is not None) and (newData[connectionStatusKeyString] == ALIVE):
            return True
    except:
        return False
    return False

def readDataInHeartbeatServerFromFEServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInHeartbeatServerFromFEServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInHeartbeatServerFromFEServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(fe2hbq, 1)
        resp = redisConnection.xread({fe2hbq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(fe2hbq, last_id)
            redisConnection.xtrim(fe2hbq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[connectionStatusKeyString] is not None) and (newData[connectionStatusKeyString] == ALIVE):
            return True
    except:
        return False
    return False

def readDataInHeartbeatServerFromDatabaseServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInHeartbeatServerFromDatabaseServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInHeartbeatServerFromDatabaseServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(db2hbq, 1)
        resp = redisConnection.xread({db2hbq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(db2hbq, last_id)
            redisConnection.xtrim(db2hbq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[connectionStatusKeyString] is not None) and (newData[connectionStatusKeyString] == ALIVE):
            return True
    except:
        return False
    return False

def readDataInHeartbeatServerFromCameraServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInHeartbeatServerFromCameraServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInHeartbeatServerFromCameraServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(camera2hbq, 1)
        resp = redisConnection.xread({camera2hbq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(camera2hbq, last_id)
            redisConnection.xtrim(camera2hbq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[connectionStatusKeyString] is not None) and (newData[connectionStatusKeyString] == ALIVE):
            return True
    except:
        return False
    return False

def readAlarmInHeartbeatServer(redisConnection: redis.client.Redis, block : int = 500):
    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call
    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readAlarmInHeartbeatServer(). Cannot receive data.")
        return False
        # raise Exception("Redis Connection is None in readDataInCameraServerFromIOServer()")
    last_id = 0
    newData = {}
    timeOfMessage = None
    try:
        redisConnection.xtrim(alarmq, 1)
        resp = redisConnection.xread({alarmq: last_id}, count=1, block=block)
        if resp:
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            for key in keys:
                value = data[key]
                newData[key.decode("utf-8")] = value.decode("utf-8")
            timeOfMessage = newData[timeKeyString]
            redisConnection.xdel(alarmq, last_id)
            redisConnection.xtrim(alarmq, 0)
            # printBoldGreen(f"Got data = {newData}")
    except Exception as e1:
        printBoldRed(f"Got exception - {e1}")
        return False
    try:
        if (newData[alarmStatusKeyString] is not None) and (newData[alarmStatusKeyString] == ok):
            return True
    except:
        return False
    return False

def readAllHeartbeatsInHeartbeatServer(
    redisConnection: redis.client.Redis,
    block: int = 500,
) -> dict:
    """
    Read one heartbeat from each of the 5 inbound heartbeat streams in a
    single blocking Redis call.

    xread blocks for at most ``block`` ms total, returning as soon as any
    stream has data. Streams with no data by the time xread returns map to
    False in the result (missed heartbeat for this cycle).

    Returns:
        dict with keys 'io', 'qrcode', 'camera', 'db', 'fe'.
        Each value is True (ALIVE received) or False.
    """
    _queue_to_key = {
        io2hbq:     'io',
        qrcode2hbq: 'qrcode',
        camera2hbq: 'camera',
        db2hbq:     'db',
        fe2hbq:     'fe',
    }

    result = {k: False for k in _queue_to_key.values()}

    if redisConnection is None:
        printBoldRed("Redis connection is None in readAllHeartbeatsInHeartbeatServer()")
        return result

    # Step 1: trim each queue to 1 entry — single pipeline round-trip
    try:
        pipe = redisConnection.pipeline(transaction=False)
        for q in _queue_to_key:
            pipe.xtrim(q, 1)
        pipe.execute()
    except Exception as e:
        printBoldRed(f"readAllHeartbeatsInHeartbeatServer(): xtrim pipeline failed: {e}")
        return result

    # Step 2: single multi-stream xread
    # count=5 because each of the 5 streams has at most 1 entry after xtrim
    # (count=1 would only read from ONE stream — that would be wrong)
    try:
        resp = redisConnection.xread(
            {q: 0 for q in _queue_to_key},
            count=5,
            block=block
        )
    except Exception as e:
        printBoldRed(f"readAllHeartbeatsInHeartbeatServer(): xread failed: {e}")
        return result

    if not resp:
        return result

    # Step 3: parse results and delete consumed entries — single pipeline round-trip
    pipe = redisConnection.pipeline(transaction=False)
    for stream_name, messages in resp:
        q = stream_name.decode('utf-8') if isinstance(stream_name, bytes) else stream_name
        if q not in _queue_to_key:
            continue
        entry_id, raw = messages[0]
        decoded = {}
        for k, v in raw.items():
            try:
                decoded[k.decode('utf-8')] = v.decode('utf-8')
            except Exception:
                pass
        if decoded.get(connectionStatusKeyString) == ALIVE:
            result[_queue_to_key[q]] = True
        pipe.xdel(q, entry_id)
        pipe.xtrim(q, 0)   # clear any entry that arrived during processing

    try:
        pipe.execute()
    except Exception as e:
        printBoldRed(f"readAllHeartbeatsInHeartbeatServer(): xdel pipeline failed: {e}")

    return result

# ********************************** COMMUNICATION INWARD INTO DATABASE SERVER *************************

def readDataInDatabaseServerFromFEServer(redisConnection : redis.client.Redis, block : int = 500, printStatements : bool = False):

    # Note this is not in a 'while not done' loop. This ensures that this function call does not block
    # Calling programs will need to implement a loop, if needed. Or, run this as an aync call

    genuineDataReceived : bool = False
    qrCode : str = ""
    knucklePicture: Union[np.ndarray, None] = None
    knuckleCheckResult : str = notok
    knuckleCheckDatetime : str = '1970-01-01 00:00:00'
    hubAndBottomBearingPicture: Union[np.ndarray, None] = None
    hubAndBottomBearingCheckResult : str = notok
    hubAndBottomBearingCheckDatetime : str = '1970-01-01 00:00:00'
    topBearingPicture: Union[np.ndarray, None] = None
    topBearingCheckResult : str = notok
    topBearingCheckDatetime : str = '1970-01-01 00:00:00'
    nutAndPlateWasherPicture: Union[np.ndarray, None] = None
    nutAndPlateWasherCheckResult : str = notok
    nutAndPlateWasherCheckDatetime : str = '1970-01-01 00:00:00'
    tighteningTorque1: float = 0.
    tighteningTorque1Result: str = notok
    tighteningTorque1Datetime : str = '1970-01-01 00:00:00'
    freeRotationDone : str = notok
    freeRotationDatetime : str = '1970-01-01 00:00:00'
    componentPressBunkPicture: Union[np.ndarray, None] = None
    componentPressBunkCheckResult : str = notok
    componentPressBunkCheckDatetime : str = '1970-01-01 00:00:00'
    componentPressDone : str = notok
    componentPressDoneDatetime : str = '1970-01-01 00:00:00'
    noBunkPicture: Union[np.ndarray, None] = None
    noBunkCheckResult : str = notok
    noBunkCheckDatetime : str = '1970-01-01 00:00:00'
    tighteningTorque2: float = 0.
    tighteningTorque2Result: str = notok
    tighteningTorque2Datetime : str = '1970-01-01 00:00:00'
    splitPinAndWasherPicture: Union[np.ndarray, None] = None
    splitPinAndWasherCheckResult : str = notok
    splitPinAndWasherCheckDatetime : str = '1970-01-01 00:00:00'
    capPicture: Union[np.ndarray, None] = None
    capCheckResult : str = notok
    capCheckDatetime : str = '1970-01-01 00:00:00'
    capPressBunkPicture: Union[np.ndarray, None] = None
    capPressBunkCheckResult : str = notok
    capPressBunkCheckDatetime : str = '1970-01-01 00:00:00'
    capPressDone : str = notok
    capPressDoneDatetime : str = '1970-01-01 00:00:00'
    freeRotationTorque1: float = 0.
    freeRotationTorque1Result: str = notok
    freeRotationTorque1Datetime : str = '1970-01-01 00:00:00'
    overallResult: str = notok
    timeOfMessage = None
    aProducer = None

    if redisConnection is None:
        printBoldRed(f"Redis connection is None in readDataInDatabaseServerFromFEServer(). Cannot receive data.")
        # raise Exception("Redis Connection is None")
        return     (genuineDataReceived, timeOfMessage, qrCode,
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
                    overallResult)

    last_id = 0

    try:
        redisConnection.xtrim(fe2dbq, 1)
        resp = redisConnection.xread(
            {fe2dbq: last_id}, count=1, block=block
        )
        if resp:
            genuineDataReceived = True
            key, messages = resp[0]
            last_id, data = messages[0]
            keys = data.keys()
            newData = {}
            for key in keys:
                value = data[key]
                # NOTE : Since this message carries image bytes, DO NOT indiscriminately use .decode('utf-8') on the values
                newData[key.decode("utf-8")] = value

            timeOfMessage = newData[timeKeyString].decode('utf-8')
            aProducer = newData[producerKeyString].decode('utf-8')

            try:
                qrCode = str(newData[qrCodeKeyString].decode('utf-8'))
            except:
                qrCode = UNKNOWN

            try:
                knucklePicture = cv2.imdecode(np.frombuffer(newData[knucklePictureKeyString], np.uint8), 1)
                if printStatements:
                    print(knucklePicture.shape)
            except:
                printBoldRed(f"Couldn't get knucklePicture")
                knucklePicture = None

            try:
                if knucklePicture is not None:
                    knuckleCheckResult = str(newData[knuckleCheckResultKeyString].decode('utf-8'))
            except:
                knuckleCheckResult = notok

            try:
                knuckleCheckDatetime = str(newData[knuckleDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get knuckleCheckDatetime")
                knuckleCheckDatetime = '1970-01-01 00:00:00'

            try:
                hubAndBottomBearingPicture = cv2.imdecode(np.frombuffer(newData[hubAndBottomBearingPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(hubAndBottomBearingPicture.shape)
            except:
                printBoldRed(f"Couldn't get hubAndBottomBearingPicture")
                hubAndBottomBearingPicture = None

            try:
                if hubAndBottomBearingPicture is not None:
                    hubAndBottomBearingCheckResult = str(newData[hubAndBottomBearingCheckResultKeyString].decode('utf-8'))
            except:
                hubAndBottomBearingCheckResult = notok

            try:
                hubAndBottomBearingCheckDatetime = str(newData[hubAndBottomBearingDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get hubAndBottomBearingCheckDatetime")
                hubAndBottomBearingCheckDatetime = '1970-01-01 00:00:00'

            try:
                topBearingPicture = cv2.imdecode(np.frombuffer(newData[topBearingPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(topBearingPicture.shape)
            except:
                printBoldRed(f"Couldn't get topBearingPicture")
                topBearingPicture = None

            try:
                if topBearingPicture is not None:
                    topBearingCheckResult = str(newData[topBearingCheckResultKeyString].decode('utf-8'))
            except:
                topBearingCheckResult = notok

            try:
                topBearingCheckDatetime = str(newData[topBearingDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get topBearingCheckDatetime")
                topBearingCheckDatetime = '1970-01-01 00:00:00'

            try:
                nutAndPlateWasherPicture = cv2.imdecode(np.frombuffer(newData[nutAndPlateWasherPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(nutAndPlateWasherPicture.shape)
            except:
                printBoldRed(f"Couldn't get nutAndPlateWasherPicture")
                nutAndPlateWasherPicture = None

            try:
                if nutAndPlateWasherPicture is not None:
                    nutAndPlateWasherCheckResult = str(newData[nutAndPlateWasherCheckResultKeyString].decode('utf-8'))
            except:
                nutAndPlateWasherCheckResult = notok

            try:
                nutAndPlateWasherCheckDatetime = str(newData[nutAndPlateWasherDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get nutAndPlateWasherCheckDatetime")
                nutAndPlateWasherCheckDatetime = '1970-01-01 00:00:00'

            try:
                tighteningTorque1 = float(newData[tighteningTorque1ValueKeyString].decode('utf-8'))
            except:
                tighteningTorque1 = 0.0

            try:
                tighteningTorque1Result = str(newData[tighteningTorque1ResultKeyString].decode('utf-8'))
            except:
                tighteningTorque1Result = notok

            try:
                tighteningTorque1Datetime = str(newData[tighteningTorque1DatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get tighteningTorque1CheckDatetime")
                tighteningTorque1Datetime = '1970-01-01 00:00:00'

            try:
                freeRotationDone = str(newData[freeRotationDoneKeyString].decode('utf-8'))
            except:
                freeRotationDone = notok

            try:
                freeRotationDatetime = str(newData[freeRotationDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get freeRotationCheckDatetime")
                freeRotationDatetime = '1970-01-01 00:00:00'

            try:
                componentPressBunkPicture = cv2.imdecode(np.frombuffer(newData[componentPressBunkPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(componentPressBunkPicture.shape)
            except:
                componentPressBunkPicture = None

            try:
                if componentPressBunkPicture is not None:
                    componentPressBunkCheckResult = str(newData[componentPressBunkCheckResultKeyString].decode('utf-8'))
            except:
                componentPressBunkCheckResult = notok

            try:
                componentPressBunkCheckDatetime = str(newData[componentPressBunkCheckDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get componentPressBunkCheckDatetime")
                componentPressBunkCheckDatetime = '1970-01-01 00:00:00'

            try:
                componentPressDone = str(newData[componentPressDoneResultKeyString].decode('utf-8'))
            except:
                componentPressDone = notok

            try:
                componentPressDoneDatetime = str(newData[componentPressDoneDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get componentPressDatetime")
                componentPressDoneDatetime = '1970-01-01 00:00:00'

            try:
                noBunkPicture = cv2.imdecode(np.frombuffer(newData[noBunkPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(noBunkPicture.shape)
            except:
                noBunkPicture = None

            try:
                if noBunkPicture is not None:
                    noBunkCheckResult = str(newData[noBunkCheckResultKeyString].decode('utf-8'))
            except:
                noBunkCheckResult = notok

            try:
                noBunkCheckDatetime = str(newData[noBunkCheckDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get noBunkCheckDatetime")
                noBunkCheckDatetime = '1970-01-01 00:00:00'

            try:
                tighteningTorque2 = float(newData[tighteningTorque2ValueKeyString].decode('utf-8'))
            except:
                tighteningTorque2 = 0.0

            try:
                tighteningTorque2Result = str(newData[tighteningTorque2ResultKeyString].decode('utf-8'))
            except:
                tighteningTorque2Result = notok

            try:
                tighteningTorque2Datetime = str(newData[tighteningTorque2DatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get tighteningTorque2Datetime")
                tighteningTorque2Datetime = '1970-01-01 00:00:00'

            try:
                splitPinAndWasherPicture = cv2.imdecode(np.frombuffer(newData[splitPinAndWasherPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(splitPinAndWasherPicture.shape)
            except:
                splitPinAndWasherPicture = None

            try:
                if splitPinAndWasherPicture is not None:
                    splitPinAndWasherCheckResult = str(newData[splitPinAndWasherCheckResultKeyString].decode('utf-8'))
            except:
                splitPinAndWasherCheckResult = notok

            try:
                splitPinAndWasherCheckDatetime = str(newData[splitPinAndWasherCheckDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get splitPinAndWasherCheckDatetime")
                splitPinAndWasherCheckDatetime = '1970-01-01 00:00:00'

            try:
                capPicture = cv2.imdecode(np.frombuffer(newData[capPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(capPicture.shape)
            except:
                capPicture = None

            try:
                if capPicture is not None:
                    capCheckResult = str(newData[capCheckResultKeyString].decode('utf-8'))
            except:
                capCheckResult = notok

            try:
                capCheckDatetime = str(newData[capCheckDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get capCheckDatetime")
                capCheckDatetime = '1970-01-01 00:00:00'

            try:
                capPressBunkPicture = cv2.imdecode(np.frombuffer(newData[capPressBunkPictureKeyString], np.uint8), 1)
                if printStatements:
                    print(capPressBunkPicture.shape)
            except:
                capPressBunkPicture = None

            try:
                if capPressBunkPicture is not None:
                    capPressBunkCheckResult = str(newData[capPressBunkCheckResultKeyString].decode('utf-8'))
            except:
                capPressBunkCheckResult = notok

            try:
                capPressBunkCheckDatetime = str(newData[capPressBunkCheckDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get capPressBunkCheckDatetime")
                capPressBunkCheckDatetime = '1970-01-01 00:00:00'

            try:
                capPressDone = str(newData[capPressDoneResultKeyString].decode('utf-8'))
            except:
                capPressDone = notok

            try:
                capPressDoneDatetime = str(newData[capPressDoneDatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get capPressDoneDatetime")
                capPressDoneDatetime = '1970-01-01 00:00:00'

            try:
                freeRotationTorque1 = float(newData[freeRotationTorque1ValueKeyString].decode('utf-8'))
            except:
                freeRotationTorque1 = 0.0

            try:
                freeRotationTorque1Result = str(newData[freeRotationTorque1ResultKeyString].decode('utf-8'))
            except:
                freeRotationTorque1Result = notok

            try:
                freeRotationTorque1Datetime = str(newData[freeRotationTorque1DatetimeKeyString].decode('utf-8'))
            except:
                printBoldRed(f"Couldn't get freeRotationTorque1Datetime")
                freeRotationTorque1Datetime = '1970-01-01 00:00:00'

            try:
                overallResult = str(newData[overallResultKeyString].decode('utf-8'))
            except:
                overallResult = notok

            redisConnection.xdel(fe2dbq, last_id)
            redisConnection.xtrim(fe2dbq, 0)

    except ConnectionError as e1:
        printBoldRed(f"There was a connection error - {e1}")
        return     (genuineDataReceived, timeOfMessage, qrCode,
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
                    overallResult)

    return (genuineDataReceived, timeOfMessage, qrCode,
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
            overallResult)


# ********************************** COMMUNICATION OUTWARD FROM DB SERVER *************************

def sendHeartbeatFromDBServerToHeartbeatServer(redisConnection : redis.client.Redis, status : ConnectionStatusType, aProducer : str = "DBServer"):
    return sendData(redisConnection=redisConnection, data={connectionStatusKeyString: status}, queueName=db2hbq, aProducer=f"{aProducer}")

# *********************************************** CLEAR QUEUES and GET MESSAGE COUNT ****************

def clearQueues(redisConnection: redis.client.Redis, reportCounts : bool = False):
    queues = [io2feq, io2cameraq, io2qrcodeq, io2qrcodeabortq, io2hbq, qrcode2ioq, qrcode2feq, qrcode2hbq, qrcode2cameraq,
              fe2ioq, fe2dbq, fe2hbq, camera2ioq, camera2feq, camera2hbq, db2hbq, hb2feq, hb2ioq,
              alarmq, emergencyq, stopQ, stoppedResponseQ]
    try:
        redisConnection.flushdb()
    except Exception as e:
        print(f"Encountered {e} while clearing queues")

    try:
        for queue in queues:
            # print(f"Initial Message Count: {getMessageCount(self.redisConnection, queue)} entries in queue {queue}")
            redisConnection.xtrim(queue,0)
    except Exception as e:
        print(f"Encountered {e} while trimming queues to 0")

    if reportCounts:
        reportMessageCount(redisConnection=redisConnection)

def reportMessageCount(redisConnection: redis.client.Redis):
    queues = [io2feq, io2cameraq, io2qrcodeq, io2hbq, qrcode2ioq, qrcode2feq, qrcode2hbq, qrcode2cameraq,
              fe2ioq, fe2dbq, fe2hbq, camera2ioq, camera2feq, camera2hbq, db2hbq, hb2feq, hb2ioq,
              alarmq, emergencyq, stopQ, stoppedResponseQ]
    try:
        for queue in queues:
            print(f"{getMessageCount(redisConnection, queue)} entries in queue {queue}")
    except Exception as e:
        print(f"Encountered {e} while reporting message count in queues")


# *********************************************** OTHER METHODS ***************************************

def sendAlarmSignalToHeartbeatServer(redisConnection : redis.client.Redis, status : ResultType = ok, aProducer : str = "CameraServer"):
    return sendData(redisConnection=redisConnection, data={alarmStatusKeyString: status}, queueName=alarmq, aProducer=f"{aProducer}")

def sendImage(redisConnection: redis.client.Redis, anImage: Union[np.ndarray, None], queueName: str = commonStreamKey,
              aProducer: str = "Producer", trackTime: bool = False):
    # print(f'Image shape is {anImage.shape} and anImage dtype is {anImage.dtype}')
    # printBoldBlue(f"Redis connection is of type : {type(redisConnectionLeftCameraPicture)}")
    if redisConnection is None:
        printBoldRed(f"Redis connection is None. Cannot send image.")
        raise Exception("Redis Connection is None")
    if anImage is None:
        printBoldRed(f"Image is None. Cannot send image.")
        return False
    if queueName is None:
        printBoldRed(f"Queue Name is None. Cannot send image.")
        return False
    if trackTime:
        time1 : float = time.time()
    buffer = None
    try:
        if isinstance(anImage, np.ndarray) and anImage is not None:
            retval, buffer = cv2.imencode('.png', anImage)
    except Exception as e:
        printBoldRed(f"Could not encode startingImage.  Cannot send startingImage : {e}")
        raise e
        # return False
    imageAsMessage = ""
    if buffer is not None:
        imageAsMessage = np.array(buffer).tobytes()
    # printBoldBlue(f"Encoded startingImage is of type : {type(message)}")
    data = {
        timeKeyString: getCurrentTimeInMS(),
        producerKeyString: aProducer,
        originalImageKeyString: imageAsMessage
    }
    try:
        resp = redisConnection.xadd(queueName, data)
        if trackTime:
            time2 : float = time.time()
            timeTaken = round((time2 - time1) * 1000, 2)
            # printPlain(f'{queueName} : Producer sent anImage in {timeTaken} ms')
        return True
    except ConnectionError as e1:
        raise e1
    # return False

def sendOkImage(redisConnection: redis.client.Redis, anImage: Union[np.ndarray, None], queueName: str = commonStreamKey,
                aProducer: str = "Producer", trackTime: bool = False):
    return sendImageWithResult(redisConnection=redisConnection, anImage=anImage, queueName=queueName, aProducer=aProducer, result=ok, trackTime=trackTime)

def sendNotOkImage(redisConnection: redis.client.Redis, anImage: Union[np.ndarray, None], queueName: str = commonStreamKey,
                   aProducer: str = "Producer", trackTime: bool = False):
    return sendImageWithResult(redisConnection=redisConnection, anImage=anImage, queueName=queueName, aProducer=aProducer, result=notok, trackTime=trackTime)

def sendOkData(redisConnection: redis.client.Redis, queueName: str = commonStreamKey, aProducer : str = "Producer"):
    return sendData(redisConnection=redisConnection, data={resultKeyString: ok}, queueName=queueName, aProducer=aProducer)

def sendNotOkData(redisConnection: redis.client.Redis, queueName: str = commonStreamKey, aProducer : str = "Producer"):
    return sendData(redisConnection=redisConnection, data={resultKeyString: notok}, queueName=queueName, aProducer=aProducer)

def sendTakeNextPictureCommandToCamera(redisConnection: redis.client.Redis, cameraId: int = 1, aProducer : str = "IOServer", handshake : bool = False):
    queueName = CosThetaConfigurator.getInstance().getCameraTakePicQueue(cameraId=cameraId)
    if not handshake:
        return sendData(redisConnection=redisConnection, data={idKeyString: f"{cameraId}", genericdataKeyString: TAKE_NEXT_PICTURE}, queueName=queueName, aProducer=f"{aProducer}_{cameraId}")
    else:
        return sendData(redisConnection=redisConnection,
                 data={idKeyString: f"{cameraId}", genericdataKeyString: HANDSHAKE}, queueName=queueName,
                 aProducer=f"{aProducer}_{cameraId}")
    # printBold(f"Sending data to {queueName}")

def sendMessageToDiscInterlockAndConnectionAlarm(redisConnection: redis.client.Redis, status : ConnectionStatusType, aProducer : str = "IOServer"):
    queueName = CosThetaConfigurator.getInstance().getConnectionAlarmQueue()
    return sendData(redisConnection=redisConnection, data={genericdataKeyString: status}, queueName=queueName, aProducer=f"{aProducer}")

def clearKeyCommunicationQueuesOnAbort():
    redisConnection = redis.Redis(connection_pool=redisPoolForClearingKeyQueues, retry_on_timeout=True)
    queues = [io2cameraq, io2qrcodeq, qrcode2ioq, qrcode2feq, qrcode2cameraq,
              camera2ioq, camera2feq]
    for q in queues:
        try:
            redisConnection.xtrim(q,0)
        except:
            pass

# ================================================================================
# INDEPENDENT LOGGING METHODS THAT HELP LOG TO THE MASTER CONSOLE AND MASTER FILE
# THIS DOES NOT INVOKE THE QUEUED AND THREADED APPROACH OF MCL AMD MFL
# THEREFORE, THIS MAKES IT FIT FOR USAGE IN PYSIDE FRONT ENDS, BECAUSE IT ELIMINATES THE
# POSSIBILITY OF CLASH BETWEEN THREADS AND QTHREADS.
# ================================================================================

# ---------------------------------------------------------------------------
# Redis connection pool for Logging
# ---------------------------------------------------------------------------

_POOL_SIZE    : int             = 15
_logSource    : str             = getFullyQualifiedName(__file__)
_redisPool    : queue.Queue     = queue.Queue(maxsize=_POOL_SIZE)
_poolReady    : bool            = False

def _buildConnection() -> Redis | None:
    """Create a single Redis connection using project-standard config."""
    try:
        cfg = CosThetaConfigurator.getInstance()
        return Redis(cfg.getRedisHost(), cfg.getRedisPort(), retry_on_timeout=True)
    except Exception as e:
        printBoldRed(f"[RedisUtils] Failed to create Redis connection: {e}")
        return None


def initialiseRedisPool() -> None:
    """
    Fill the pool with _POOL_SIZE connections.
    Safe to call multiple times — will not add beyond pool capacity.
    """
    global _poolReady
    created = 0
    for _ in range(_POOL_SIZE - _redisPool.qsize()):
        conn = _buildConnection()
        if conn is not None:
            _redisPool.put_nowait(conn)
            created += 1
    _poolReady = _redisPool.qsize() > 0
    printBoldGreen(f"[RedisUtils] Redis pool initialised: {_redisPool.qsize()}/{_POOL_SIZE} connections available")

initialiseRedisPool()

def borrowRedisConnection(timeoutSeconds: float = 2.0) -> Redis | None:
    """
    Draw a connection from the pool.
    Returns None if the pool is empty after timeoutSeconds.
    Always pair with returnRedisConnection() in a try/finally block.
    """
    if not _poolReady:
        initialiseRedisPool()
    try:
        return _redisPool.get(block=True, timeout=timeoutSeconds)
    except queue.Empty:
        printBoldRed(f"[RedisUtils] Redis pool exhausted — no connection available after {timeoutSeconds}s")
        return None


def returnRedisConnection(conn: Redis | None) -> None:
    """
    Return a borrowed connection back to the pool.
    If the connection is None or broken, a fresh one is substituted
    so the pool never shrinks below its intended size.
    """
    if conn is not None:
        try:
            conn.ping()          # cheap — confirms the connection is alive
        except Exception:
            conn = _buildConnection()   # replace broken with fresh
    else:
        conn = _buildConnection()       # replace None with fresh
    try:
        _redisPool.put_nowait(conn)
    except queue.Full:
        pass

# import re as _re
# _TIMESTAMP_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{3}')

# def _ensure_timestamp(data: dict) -> dict:
#     """Return a copy of data with a timestamp prepended to 'text' if absent."""
#     from logutils.AbstractSlaveLogger import TEXT_KEY
#     from utils.CosThetaPrintUtils import getCurrentTime
#     text = data.get(TEXT_KEY, "")
#     if isinstance(text, bytes):
#         text = text.decode('utf-8')
#     if not _TIMESTAMP_RE.match(text):
#         data = dict(data)          # don't mutate caller's dict
#         data[TEXT_KEY] = f"{getCurrentTime()} :  {text}"
#     return data

def getFrontendLoggingLevel() -> int:
    """Return the current frontend logging threshold, reloading config if needed."""
    return Logger.getLoggingLevelInt(
        CosThetaConfigurator.getFrontendLoggingLevel()
    )

def _get_caller_info(stackdepth: int = 2) -> str:
    """Return 'filename.method:lineno' climbing stackdepth frames above the caller."""
    try:
        frame = inspect.currentframe()
        for _ in range(stackdepth):
            if frame is None:
                break
            frame = frame.f_back
        if frame is not None:
            filename = os.path.basename(frame.f_code.co_filename)
            method   = frame.f_code.co_name
            lineno   = frame.f_lineno
            return f"{filename}.{method}:{lineno}"
    except (AttributeError, TypeError):
        pass
    finally:
        del frame
    return ""

def _ensure_timestamp(data: dict, caller_info: str = "", level: int = LogLevel.INFO) -> dict:
    """Return a copy of data with a formatted prefix prepended to 'text'."""
    from utils.CosThetaPrintUtils import getCurrentTime
    from logutils.Logger import Logger, MessageType

    TEXT_KEY         = "text"
    MESSAGE_TYPE_KEY = "message_type"

    text = data.get(TEXT_KEY, "")
    if isinstance(text, bytes):
        text = text.decode('utf-8')

    data = dict(data)   # don't mutate caller's dict

    level_str    = Logger.getLoggingLevelText(level)
    raw_mtype    = data.get(MESSAGE_TYPE_KEY, MessageType.GENERAL)
    try:
        mtype_str = Logger.getMessageTypeText(int(raw_mtype))
    except (ValueError, TypeError):
        mtype_str = "GENERAL"

    prefix = f"{getCurrentTime()} :  {level_str}->{mtype_str}->{caller_info}"
    data[TEXT_KEY] = f"{prefix} :: {text}"
    return data

def logMessageToConsole(
    redisConnection: Redis,
    data: dict,
    aProducer: str = "Producer",
    level: int = LogLevel.INFO,
    _stackdepth: int = 2,           # internal — callers don't touch this
) -> None:
    if level < getFrontendLoggingLevel():
        return
    returnConnection: bool = False
    if redisConnection is None:
        redisConnection = borrowRedisConnection()
        if redisConnection is not None:
            returnConnection = True
    data = _ensure_timestamp(data, _get_caller_info(_stackdepth), level)
    sendData(
        redisConnection=redisConnection,
        data=data,
        queueName=CosThetaConfigurator.getInstance().getConsoleLoggingQueue(),
        aProducer=aProducer,
    )
    if returnConnection:
        returnRedisConnection(redisConnection)


def logMessageToFile(
    redisConnection: Redis,
    data: dict,
    aProducer: str = "Producer",
    level: int = LogLevel.INFO,
    _stackdepth: int = 2,
) -> None:
    if level < getFrontendLoggingLevel():
        return
    returnConnection: bool = False
    if redisConnection is None:
        redisConnection = borrowRedisConnection()
        if redisConnection is not None:
            returnConnection = True
    data = _ensure_timestamp(data, _get_caller_info(_stackdepth), level)
    sendData(
        redisConnection=redisConnection,
        data=data,
        queueName=CosThetaConfigurator.getInstance().getFileLoggingQueue(),
        aProducer=aProducer,
    )
    if returnConnection:
        returnRedisConnection(redisConnection)


def logMessageToConsoleAndFile(
    redisConnection: Redis,
    data: dict,
    aProducer: str = "Producer",
    level: int = LogLevel.INFO,
) -> None:
    if level < getFrontendLoggingLevel():
        return
    returnConnection: bool = False
    if redisConnection is None:
        redisConnection = borrowRedisConnection()
        if redisConnection is not None:
            returnConnection = True
    # _stackdepth=3: actual caller → logMessageToConsoleAndFile → logMessageToConsole/File → _get_caller_info
    logMessageToConsole(redisConnection=redisConnection, data=data, aProducer=aProducer, level=level, _stackdepth=3)
    logMessageToFile(redisConnection=redisConnection, data=data, aProducer=aProducer, level=level, _stackdepth=3)
    if returnConnection:
        returnRedisConnection(redisConnection)

# ================================================================================

# TESTING CAMERASERVER

# trialRedisConnection = Redis("localhost", 6379)
# clearQueues(trialRedisConnection)
# sendDataFromIOServerToCameraServer(trialRedisConnection, currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE)
# print("===================")
# print(readDataInFEServerFromCameraServer(trialRedisConnection))
# print("===================")
# print(readDataInIOServerFromCameraServer(trialRedisConnection))
# print(readDataInFEServerFromIOServer(trialRedisConnection))

# ================================================================================