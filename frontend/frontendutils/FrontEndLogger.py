from datetime import datetime
from logutils.Logger import *
from Configuration import *
from utils.RedisUtils import *
from redis import Redis

CONSOLE : int = 1
FILE : int = 2

consoleLoggingQ = CosThetaConfigurator.getInstance().getConsoleLoggingQueue()
fileLoggingQ = CosThetaConfigurator.getInstance().getFileLoggingQueue()
logSource = getFullyQualifiedName(__file__)

redisConnection = Redis(CosThetaConfigurator.getInstance().getRedisHost(), CosThetaConfigurator.getInstance().getRedisPort(), retry_on_timeout=True)
currentConsoleLoggingLevel = Logger.getLoggingLevelInt(CosThetaConfigurator.getInstance().getConsoleLoggingLevel())
currentFileLoggingLevel = Logger.getLoggingLevelInt(CosThetaConfigurator.getInstance().getFileLoggingLevel())

# print(currentFileLoggingLevel, currentFileLoggingLevel)

def makeLoggingMessage(loggingLevel : str, source : str, message : str, messageType : int = Logger.GENERAL):
    # printBoldYellow(loggingLevel, source, message, ";", messageType)
    if messageType < Logger.GENERAL:
        messageType = Logger.GENERAL
    if messageType > Logger.PROBLEM:
        messageType = Logger.PROBLEM

    currentFrame = inspect.currentframe()
    # print(currentFrame)
    try:
        callerFrame = currentFrame.f_back.f_back.f_back
        # print(callerFrame)
        # prevFrame = callerFrame.f_back.f_back
        # print(prevFrame)
        co = callerFrame.f_code
        func_name = co.co_name
        lno = callerFrame.f_lineno
    except:
        # if not hasattr(self, func_name):
        func_name = ""
        lno = ""
    msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
    (dt, ms) = msTime.split('.')
    ms = int(ms) // 1000
    currentTime = f'{dt}.{ms:03}'
    # printBoldYellow(currentTime, loggingLevel, func_name, lno)
    mtText = Logger.getMessageTypeText(messageType)
    messageToBeLogged = f'{currentTime}: {loggingLevel}->{mtText}->{source.strip() if source is not None else ""}{"." if source is not None else ""}{func_name.strip()}:{lno}->{message}'
    # printBoldYellow(messageToBeLogged)
    return messageToBeLogged

def logMessage(messageLogLevel : int, source : str, message : str, messageType : int):
    message = makeLoggingMessage(loggingLevel=Logger.getLoggingLevelText(messageLogLevel), source=source, message=message, messageType=messageType)
    return message

def logDebug(target : int, source : str, message : str, messageType : int = Logger.GENERAL):
    logMessage(Logger.DEBUG, source, message, messageType)

def logInfo(target : int, source : str, message : str, messageType : int = Logger.SUCCESS):
    logMessage(Logger.INFO, source, message, messageType)

def logTakeNote(target : int, source : str, message : str, messageType : int = Logger.RISK):
    logMessage(Logger.TAKENOTE, source, message, messageType)

def logConsiderAction(target : int, source : str, message : str, messageType : int = Logger.ISSUE):
    logMessage(Logger.CONSIDERACTION, source, message, messageType)

def logTakeAction(target : int, source : str, message : str, messageType : int = Logger.PROBLEM):
    logMessage(Logger.TAKEACTION, source, message, messageType)

def logToConsole(messageLogLevel : int, source : str, message : str, messageType : int):
    global consoleLoggingQ, logSource
    message = makeLoggingMessage(Logger.getLoggingLevelText(messageLogLevel), source, message, messageType)
    sendData(redisConnection, {genericdataKeyString : message}, consoleLoggingQ, aProducer=logSource)

def logToFile(data):
    global fileLoggingQ, logSource
    sendData(redisConnection, data, fileLoggingQ, aProducer=logSource)

def sendStopToAll():
    sendStopCommand(redisConnection=redisConnection, aProducer="FrontEnd")