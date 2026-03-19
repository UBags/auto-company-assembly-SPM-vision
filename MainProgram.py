import signal
import sys
import typing

from frontend.SimplePopups import showApplicationStartingScreen, chooseMode, showErrorMessage, showMessage, \
    flashSimpleMessage, login
from persistence.Persistence import setDatabaseName, makeFoldersForImages, getDataSubFolder
from utils.RedisUtils import *
from logutils.Logger import MessageType

# Keys matching AbstractSlaveLogger.TEXT_KEY / MESSAGE_TYPE_KEY
_LOG_TEXT_KEY:  str = "text"
_LOG_MTYPE_KEY: str = "message_type"


# # Python 3.10 compatibility patch
# if sys.version_info < (3, 11):
#     try:
#         from typing_extensions import Self
#
#         typing.Self = Self
#         print("✓ typing.Self patched")
#     except ImportError:
#         typing.Self = typing.TypeVar('Self')

# Python 3.10 compatibility patch
if sys.version_info < (3, 11):
    typing.Self = typing.TypeVar('Self')
    print("✓ typing.Self patched")


import multiprocessing
import sys
from multiprocessing import Process

from utils.IPUtils import checkIP

# Set spawn method explicitly for Windows compatibility
if "win32" in sys.platform:
    multiprocessing.set_start_method('spawn', force=True)
else:
    multiprocessing.set_start_method('fork', force=True)

from Configuration import *
CosThetaConfigurator.getInstance()

from utils.CosThetaPrintUtils import *
from persistence.PostgresBackupUtility import *
# from VerifyIntegrity import *

hostname = CosThetaConfigurator.getInstance().getRedisHost()
port = CosThetaConfigurator.getInstance().getRedisPort()
redisConnection : Redis | None = None

tryAgain : bool = False
try:
    redisConnection = Redis(hostname, port, retry_on_timeout=True)
    redisConnection.ping()  # Test connection
    printBoldGreen(f"Connected successfully to Redis in MainProgram")
except Exception as e:
    printBoldRed(f"Failed to connect to Redis in MainProgram : {e}")
    redisConnection = None
    printBoldBlue(f"Waiting for a short while for other components to come up")
    tryAgain = True
    time.sleep(10)

if tryAgain:
    try:
        redisConnection = Redis(hostname, port, retry_on_timeout=True)
        redisConnection.ping()  # Test connection
        tryAgain = False
        printBoldGreen(f"Connected successfully to Redis in MainProgram")
    except Exception as e:
        printBoldRed(f"Failed to connect to Redis in MainProgram : {e}")
        redisConnection = None
        printBoldBlue(f"Waiting for a short while more for other components to come up")
        tryAgain = True
        time.sleep(10)

if tryAgain:
    try:
        redisConnection = Redis(hostname, port, retry_on_timeout=True)
        redisConnection.ping()  # Test connection
        tryAgain = False
        printBoldGreen(f"Connected successfully to Redis in MainProgram")
    except Exception as e:
        printBoldRed(f"Failed to connect to Redis in MainProgram : {e}")
        redisConnection = None
        printBoldRed(f"Redis is an important component for the machine. Contact the manufacturer - CosTheta Technologies for a resolution")
        sys.exit(1)

# try:
#     redisConnection.flushdb()
#     printBoldBlue(f"Flushed the redis db")
#     clearQueues(redisConnection)
#     printBoldBlue(f"Cleared redis queues")
# except:
#     printBoldRed(f"Could not flush the redis db")

def startTheLoggingServer():
    from logutils.CentralLoggers import startLoggers
    startLoggers()

def startTheHeartbeatServer():
    from monitorAllConnections.HeartbeatAndAlarmServer import startHeartbeatAndAlarmServer
    startHeartbeatAndAlarmServer()

def startTheDBServer(mode : str, username : str):
    from persistence.DBServer import startDBServer
    startDBServer(mode=mode, username=username)

def startTheQRCodeServer(mode : str):
    from costhetaio.QRCodeScanningServer import startQRCodeServer
    startQRCodeServer(mode=mode)

def startTheIOServer(mode : str):
    from costhetaio.IOServer import startIOServer
    startIOServer(mode = mode)

def startTheCameraServer(mode : str):
    from camera.CameraProcessorServer import startCameraServer
    startCameraServer(mode=mode)

def startTheFrontendServer(mode : str, username : str, role : str):
    from frontend.AutoCompanyFrontEnd import startFrontEnd
    startFrontEnd(mode=mode,username=username, role=role)

# def startTheWebServiceEndpoints():
#     from endpoints.AutoCompanyWebService import startWebService
#     startWebService()

# def startTheMIService():
#     from endpoints.AutoCompany_MI_Panel import startMIServer
#     startMIServer()

def checkIPs():
    _src = getFullyQualifiedName(__file__, checkIPs)
    cameraIP = CosThetaConfigurator.getInstance().getCameraIP()
    allenBradleyPLC_IP = CosThetaConfigurator.getInstance().getPlcIP()
    cameraReachable = checkIP(cameraIP)
    allenBradleyPLC_Reachable = checkIP(allenBradleyPLC_IP)

    if cameraReachable:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Camera is reachable at IP {cameraIP}. OK.", _LOG_MTYPE_KEY: MessageType.SUCCESS}, _src, level=LogLevel.CRITICAL)
    else:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Camera is not reachable at IP {cameraIP}. Please check power to the camera and RJ45 connection from the camera to the system.", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    if allenBradleyPLC_Reachable:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"I/O Module - PLC is reachable at IP {allenBradleyPLC_IP}. OK.", _LOG_MTYPE_KEY: MessageType.SUCCESS}, _src, level=LogLevel.CRITICAL)
    else:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"I/O Module - PLC is not reachable at IP {allenBradleyPLC_IP}. Please check power to the PLC and RJ45 connection from the PLc to the system.", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)
        # raise Exception("IOModule not reachable")

# printBoldBlue(f"MainProgram process is {os.getpid()}")
# os.system(f"start /B start /wait cmd.exe @cmd /k python MainSubProgram.py {currentMode} {currentBatchNumber} {username} {rolename}")

def stopProcesses(currentProcessPIDs: list, endingSplashScreenBeingShown : bool = True):
    _src = getFullyQualifiedName(__file__, stopProcesses)
    global redisConnection
    if endingSplashScreenBeingShown:
        time.sleep(CosThetaConfigurator.getInstance().getEndScreenTime() + 2)
    sendStopCommand(redisConnection, aProducer="MainProgram")
    time.sleep(2.0)
    for pid in currentProcessPIDs:
        try:
            if psutil.pid_exists(pid):
                os.kill(pid, signal.SIGTERM)
                # printBoldBlue(f"Closed process {pid}")
                # p = psutil.Process(pid)
                # p.terminate()
        except:
            pass
        # Close Redis connections
        try:
            if redisConnection:
                redisConnection.close()
        except:
            pass
    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "All processes shut down. Closing terminal window.", _LOG_MTYPE_KEY: MessageType.SUCCESS}, _src, level=LogLevel.CRITICAL)
    sys.exit(1)

def monitorStop(redisConnectionForMonitoringStop: redis.client.Redis, currentProcesses: list, startingTime: float):
    _src = getFullyQualifiedName(__file__, monitorStop)
    global houLimit, mouLimit
    lastUpdateOfStartingTime: float = startingTime
    while True:
        try:
            _, shallStop = getStopCommandFromQueue(redisConnectionForMonitoringStop)
            if shallStop:
                # printBoldRed("Got stop signal in MainProgram")
                # time.sleep(CosThetaConfigurator.getInstance().getEndScreenTime() + 2)
                # for pid in currentProcesses:
                #     try:
                #         if psutil.pid_exists(pid):
                #             os.kill(pid, signal.SIGTERM)
                #             # p = psutil.Process(pid)
                #             # p.terminate()
                #     except:
                #         pass
                # printBoldGreen("All processes shut down.")
                stopProcesses(currentProcesses)
                break
        except Exception as e:
            logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: str(e), _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.WARNING)
            pass
        # if mouLimit < 12 and houLimit < 4800:
        #     currentTime = time.time()
        #     if (currentTime - lastUpdateOfStartingTime) > 60:
        #         # nHours = round((currentTime - lastUpdateOfStartingTime) / 3600,2)
        #         lastUpdateOfStartingTime = currentTime
        #         valid = False
        #         try:
        #             valid = updateAndEncryptHoU(False)
        #             # print(f"updateAndEncryptHoU(False) executed with result as {valid}")
        #         except:
        #             pass
        #         if not valid:
        #             stopProcesses(currentProcesses)
        #             break
        #         try:
        #             encryptAndStoreCurrentDate()
        #             # print(f"encryptAndStoreCurrentDate() executed")
        #         except:
        #             pass

        # allKeys = redisConnectionForMonitoringStop.scan_iter()
        # if allKeys is not None:
        #     printBoldYellow(f"The keys in queue are:")
        #     for aKey in allKeys:
        #         aKeyAsString = aKey.decode("utf-8")
        #         printBoldYellow(f"{aKeyAsString} : {redisConnectionForMonitoringStop.get(aKeyAsString)}")

        # printRedisQueueLengths(redis_connection=redisConnectionForMonitoringStop)

        time.sleep(10)
    doBackup()
    # try:
    #     updateAndEncryptHoU(False)
    # except:
    #     pass


def printRedisQueueLengths(redis_connection):
    """
    Check the number of messages in all Redis list queues.

    Args:
        redis_connection: Redis connection object (e.g., redis.Redis)

    Returns:
        dict: Dictionary mapping queue names to their message counts
    """
    _src = getFullyQualifiedName(__file__, printRedisQueueLengths)
    queue_lengths = {}
    try:
        # Iterate over all keys in Redis
        for key in redis_connection.scan_iter():
            key_str = key.decode("utf-8")
            # Check the type of the key
            key_type = redis_connection.type(key).decode("utf-8")

            if key_type == "list":
                # Get the length of the list (number of messages in the queue)
                length = redis_connection.llen(key)
                if length > 0:
                    queue_lengths[key_str] = length
                # printBoldYellow(f"Queue {key_str}: {length} messages")
            elif key_type == "string":
                value = redis_connection.get(key)
                # printBoldYellow(f"String key {key_str}: {value}")
            elif key_type == "hash":
                value = redis_connection.hgetall(key)
                # printBoldYellow(f"Hash key {key_str}: {value}")
                # # Log non-list keys for debugging (optional)
            elif key_type == "stream":
                # Get the length of the stream (number of entries)
                length = redis_connection.xlen(key)
                if length > 0:
                    queue_lengths[key_str] = length
                    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Stream Queue {key_str}: {length} entries", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.INFO)
            else:
                logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Key {key_str}: Type {key_type} (not a queue)", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.INFO)

        if not queue_lengths or len(queue_lengths) == 0:
            logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "No list queues found in Redis", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.INFO)
        else:
            logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Total messages in redis = {len(queue_lengths)}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.INFO)

        return queue_lengths

    except redis.exceptions.ResponseError as e:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Redis error: {e}", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)
        return {}
    except Exception as e:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Unexpected error: {e}", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)
        return {}

def main():
    _src = getFullyQualifiedName(__file__, main)

    printBoldBlue("Clearing up queues. Please wait...")

    try:
        clearQueues(redisConnection)
        printBoldGreen(f"Cleared up all queues")
    except Exception as e:
        printBoldRed(f"Couldn't clear queues because of {e}")
        printBoldRed(f"Queues have to work properly for the application to work. Hence, exiting...")
        sys.exit(0)

    currentProcessPIDs = []

    # printBoldBlue(f"MainProgram process is {os.getpid()}")

    P1 = Process(target=startTheLoggingServer, args=())
    P1.start()
    time.sleep(3)
    printBoldBlue("Started Loggers")
    currentProcessPIDs.append(P1.pid)

    printBoldBlue(f"Logger process is {P1.pid}")

    # Logging server is now up — switch to logMessageToConsoleAndFile from here on
    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Verifying Integrity...", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    # verifyIntegrity(processPIDs = currentProcessPIDs)

    showApplicationStartingScreen("Starting Hub and Disc Processing Application", auto_close_duration=1)

    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Backing up database...", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    try:
        doBackup()
    except Exception as e:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Could not backup database due to {e}", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Checking connection to the Camera and IO module. Please wait...", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    checkIPs()

    # time.sleep(1)cd
    currentMode = "Test"
    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Choosing mode (TEST or PRODUCTION). Default mode is TEST...", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)

    submitted, currentMode = chooseMode()

    if not submitted:
        showErrorMessage("Shutting down system, as no mode was selected")
        try:
            stopProcesses(currentProcessPIDs, endingSplashScreenBeingShown=False)
            os.system("taskkill /f /im cmd.exe")
        except:
            pass
        sys.exit(0)

    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Ensuring databases and file folders are created and available for saving data...", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    # Depending on mode, first do Test and then Production; else, vice-versa. Ensures that database name is properly populated for getting
    # the correct login ids populated in the login() dropdown
    if (currentMode.upper() == "TEST") or (currentMode.upper().startswith("TEST")):
        setDatabaseName(mode="Production")
        makeFoldersForImages(mode_data_subfolder=getDataSubFolder())
    else:
        setDatabaseName(mode="Test")
        makeFoldersForImages(mode_data_subfolder=getDataSubFolder())

    setDatabaseName(mode=currentMode)
    makeFoldersForImages(mode_data_subfolder=getDataSubFolder())

    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Initiating login...", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    loginTries = 0
    loginSubmitted = False
    successfullyLoggedIn = False
    currentUser = None
    password = ''
    currentRole = None
    while (not successfullyLoggedIn) and (loginTries < 5):
        submitted, successfullyLoggedIn, currentUser, password, currentRole = login(currentMode)
        if not successfullyLoggedIn:
            loginTries += 1
            logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Consecutive {loginTries} unsuccessful login attempts", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)
            if submitted:
                showErrorMessage("Login cancelled. Exiting the program.")
                stopProcesses(currentProcessPIDs, endingSplashScreenBeingShown=False)
                try:
                    os.system("taskkill /f /im cmd.exe")
                except:
                    pass
                sys.exit(0)

    if not successfullyLoggedIn:
        showErrorMessage("5 unsuccessful login tries. Exiting the program")
        stopProcesses(currentProcessPIDs, endingSplashScreenBeingShown=False)
        try:
            os.system("taskkill /f /im cmd.exe")
        except:
            pass
        sys.exit(0)

    # if currentRole == allowed_roles[2] and currentMode.upper() == "TEST":
    #     showErrorMessage(f"Only Administrator and Supervisor can run the system in TEST mode.\nUser {currentUser}'s role is {currentRole}\n. System will exit in 5 secs.", auto_close_duration=5)
    #     try:
    #         dbName = getDatabaseName()
    #     except:
    #         pass
    #     stopProcesses(currentProcessPIDs, endingSplashScreenBeingShown=False)
    #     try:
    #         os.system("taskkill /f /im cmd.exe")
    #     except:
    #         pass
    #     sys.exit(0)

    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"User {currentUser} logged in successfully into {currentMode}", _LOG_MTYPE_KEY: MessageType.SUCCESS}, _src, level=LogLevel.CRITICAL)
    showMessage(f"User {currentUser} logged in successfully into {currentMode}")

    # At this stage, the user has successfully logged in
    message: str = f"Running application in {currentMode} mode"
    flashSimpleMessage(message, auto_close_duration=2)
    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: message, _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)

    # showMessage("Starting cameras, IO module, and other componenets", auto_close_duration=4)
    showApplicationStartingScreen("Starting Camera Servers, IO Server, DB Server, and Logging Server", auto_close_duration=1)

    try:
        P2 = Process(target=startTheCameraServer, args=(currentMode,))
        P2.start()
        time.sleep(1)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Started Camera", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
        currentProcessPIDs.append(P2.pid)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Camera process is {P2.pid}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    except Exception as e:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Could not start Camera Server", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Exception {e} while starting CameraServer", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    try:
        P3 = Process(target=startTheQRCodeServer, args=(currentMode,))
        P3.start()
        time.sleep(1)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Started QR Code Server", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
        currentProcessPIDs.append(P3.pid)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"QR Code process 1 is {P3.pid}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    except:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Could not start QR Code Server", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    try:
        P4 = Process(target=startTheIOServer, args=(currentMode,))
        P4.start()
        time.sleep(1)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Started IO Server", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
        currentProcessPIDs.append(P4.pid)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"IO process is {P4.pid}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    except:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Could not start IO Server", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    # The following message is needed to get rid of the previous pop-up from line 303
    # flashSimpleMessage("Done starting Camera Server, QRCode Server, IO Server, and Database Server", auto_close_duration=1)
    flashSimpleMessage("Done starting Camera Server, QRCode Server, and IO Server", auto_close_duration=1)

    try:
        P6 = Process(target=startTheFrontendServer, args=(currentMode, currentUser, currentRole))
        P6.start()
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Started Frontend server", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
        time.sleep(1)
        currentProcessPIDs.append(P6.pid)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Frontend process is {P6.pid}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    except:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Could not start Front End Server", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    try:
        P7 = Process(target=startTheHeartbeatServer, args=())
        P7.start()
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Started Heartbeat Monitoring Service", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
        currentProcessPIDs.append(P7.pid)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Heartbeat Monitoring process is {P7.pid}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    except:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Could not start the HeartbeatServer", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    try:
        P5 = Process(target=startTheDBServer, args=(currentMode, currentUser,))
        P5.start()
        time.sleep(1)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Started DB Server", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
        currentProcessPIDs.append(P5.pid)
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"DB process is {P5.pid}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    except:
        logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: "Could not start DB Server", _LOG_MTYPE_KEY: MessageType.ISSUE}, _src, level=LogLevel.CRITICAL)

    # try:
    #     P8 = Process(target=startTheWebServiceEndpoints, args=())
    #     P8.start()
    #     # printBoldBlue("Started WebService")
    #     time.sleep(1)
    #     currentProcessPIDs.append(P8.pid)
    #     # printBoldBlue(f"Web Service process is {P7.pid}")
    # except:
    #     printBoldRed("Could not start Web Service Endpoints")

    # try:
    #     P9 = Process(target=startTheMIService, args=())
    #     P9.start()
    #     # printBoldBlue("Started MI Service")
    #     time.sleep(1)
    #     currentProcessPIDs.append(P9.pid)
    #     # printBoldBlue(f"MI Service process is {P8.pid}")
    # except:
    #     printBoldRed("Could not start the MI Service")


    redisConnectionForMonitoringStop = Redis(CosThetaConfigurator.getInstance().getRedisHost(),
                                             CosThetaConfigurator.getInstance().getRedisPort(), retry_on_timeout=True)

    startingTime: float = time.time()

    stopMonitoringThread = threading.Thread(name="Stop Monitoring Thread", target=monitorStop,
                                            args=(redisConnectionForMonitoringStop, currentProcessPIDs, startingTime),
                                            daemon=True)
    stopMonitoringThread.start()
    stopMonitoringThread.join()

    # printBoldBlue(f"Main Program shutting down gracefully at {datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')}")
    logMessageToConsoleAndFile(redisConnection, {_LOG_TEXT_KEY: f"Main Program shutting down at {datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}", _LOG_MTYPE_KEY: MessageType.GENERAL}, _src, level=LogLevel.CRITICAL)
    try:
        os.system("taskkill /f /im cmd.exe")
    except:
        pass
    time.sleep(3)
    sys.exit(0)

if __name__ == '__main__':
    main()
    sys.exit(0)