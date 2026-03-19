import random
import sys
import threading
import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from pycomm3 import LogixDriver
from pycomm3 import DINT, SHORT_STRING, Struct, STRING, REAL
from pycomm3.logger import configure_default_logger, LOG_VERBOSE
from psycopg2.pool import ThreadedConnectionPool

from logutils import Logger
from logutils.SlaveLoggers import logBoth
from utils.CosThetaPrintUtils import *
from utils.RedisUtils import *

from Configuration import CosThetaConfigurator
from statemachine.StateMachine import MachineState, MachineStateMachine
from processors.GenericQueueProcessor import GenericQueueProcessor
from utils.QRCodeHelper import getModel_LHSRHS_AndTonnage
from persistence.Persistence import getMachineSettings, getDatabaseName, setDatabaseName

TIME_WAIT_BEFORE_RESETTING_TORQUE2_VALUES_AFTER_READING_THEM: float = 1.5
TIME_WAIT_BEFORE_RESETTING_TORQUE3_VALUES_AFTER_READING_THEM: float = 2.0

# ==================== Global Reference for UpdateTagsToDefaultProcessor ====================
# This global reference allows other threads to add items to the processor's queue.
# Set after IOServer instantiation in startIOServer()
_updateTagsProcessor: Optional["UpdateTagsToDefaultProcessor"] = None


def getUpdateTagsProcessor() -> Optional["UpdateTagsToDefaultProcessor"]:
    """
    Get the global UpdateTagsToDefaultProcessor instance.

    Returns:
        The global processor instance, or None if not yet initialized.
    """
    global _updateTagsProcessor
    return _updateTagsProcessor


def addTagUpdateRequest(request: Dict[str, Any]) -> bool:
    """
    Add a tag update request to the UpdateTagsToDefaultProcessor queue.

    This is a convenience function for other threads to schedule delayed tag writes.

    Args:
        request: A dictionary in the following format:
            {
                "sleepTimeForDelay": <float>,  # Seconds to wait before writing tags
                "tag1": {"tag": <str>, "type": <"bool"|"float">, "value": <bool|float>},
                "tag2": {"tag": <str>, "type": <"bool"|"float">, "value": <bool|float>},
                ...  # Can have any number of tagN entries
            }

    Returns:
        True if request was added successfully, False otherwise.

    Examples:
        # Example 1: Reset a single bool tag after 1.5 seconds
        addTagUpdateRequest({
            "sleepTimeForDelay": 1.5,
            "tag1": {"tag": "PLC_PC_CheckQRCode", "type": "bool", "value": False}
        })

        # Example 2: Reset multiple tags after 2 seconds
        addTagUpdateRequest({
            "sleepTimeForDelay": 2.0,
            "tag1": {"tag": "PLC_PC_Station2TorqueValueSet", "type": "bool", "value": False},
            "tag2": {"tag": "PLC_PC_Station2TorqueValue", "type": "float", "value": 0.0}
        })

        # Example 3: Set multiple bool tags to True after 0.5 seconds
        addTagUpdateRequest({
            "sleepTimeForDelay": 0.5,
            "tag1": {"tag": "PC_PLC_KnuckleCheckOK", "type": "bool", "value": True},
            "tag2": {"tag": "PC_PLC_KnuckleCheckDone", "type": "bool", "value": True},
            "tag3": {"tag": "PLC_PC_CheckKnuckle", "type": "bool", "value": False}
        })
    """
    global _updateTagsProcessor
    if _updateTagsProcessor is not None:
        result = _updateTagsProcessor.addItem(request)
        logBoth('logDebug', UpdateTagsToDefaultProcessor.logSource, f"Added item {request} in UpdateTagsToDefaultProcessor", Logger.GENERAL)
        return result is not None
    return False


class UpdateTagsToDefaultProcessor(GenericQueueProcessor):
    """
    A processor that handles delayed tag write operations to the PLC.

    This processor runs in a separate thread and processes queued tag update requests.
    Each request specifies a delay time and one or more tags to write.

    Queue Item Format:
        {
            "sleepTimeForDelay": <float>,  # Seconds to wait before writing tags
            "tag1": {"tag": <str>, "type": <"bool"|"float">, "value": <bool|float>},
            "tag2": {"tag": <str>, "type": <"bool"|"float">, "value": <bool|float>},
            ...  # Additional tags as needed (tag3, tag4, etc.)
        }

    Supported Types:
        - "bool": Writes boolean value using IOServer.write_bool()
        - "float": Writes float value using IOServer.write_float()

    Usage Examples:
        # Get the processor instance
        processor = getUpdateTagsProcessor()

        # Or use the convenience function
        addTagUpdateRequest({
            "sleepTimeForDelay": 1.0,
            "tag1": {"tag": "MyTag", "type": "bool", "value": False}
        })
    """

    logSource = getFullyQualifiedName(__file__)

    def __init__(self, ioServerInstance: "IOServer", name: str = "UpdateTagsToDefaultProcessor"):
        """
        Initialize the UpdateTagsToDefaultProcessor.

        Args:
            ioServerInstance: Reference to the IOServer instance for writing tags.
            name: Name for this processor thread.
        """
        super().__init__(
            name=name,
            consumer=None,
            timeout=1,
            sleepTime=0.25,  # 250 ms sleep time
            blocking=False,  # Non-blocking to allow periodic wake-up
            monitorRedisQueueForStopping=False,
            max_size=64
        )
        UpdateTagsToDefaultProcessor.logSource = getFullyQualifiedName(__file__, __class__)
        self.ioServer = ioServerInstance

    def preWorkLoop(self):
        """No pre-work needed."""
        pass

    def postWorkLoop(self):
        """No post-work needed."""
        pass

    def processItem(self, item: Dict[str, Any]) -> Any:
        """
        Process a tag update request.

        Waits for the specified delay time, then writes each tag with its value.

        Args:
            item: Dictionary containing sleepTimeForDelay and tag entries.

        Returns:
            True if all tags were written successfully, False otherwise.
        """
        if item is None:
            return False

        try:
            # Get the sleep delay time
            sleepTimeForDelay = item.get("sleepTimeForDelay", 0.0)
            logBoth('logDebug', UpdateTagsToDefaultProcessor.logSource, f"UpdateTagProcessor sleeping for {sleepTimeForDelay} secs", Logger.GENERAL)
            if sleepTimeForDelay > 0:
                time.sleep(sleepTimeForDelay)

            allSuccess = True

            # Process all tag entries (tag1, tag2, tag3, etc.)
            for key, tagInfo in item.items():
                if key == "sleepTimeForDelay":
                    continue

                if not isinstance(tagInfo, dict):
                    continue

                tagName = tagInfo.get("tag")
                tagType = tagInfo.get("type")
                tagValue = tagInfo.get("value")

                logBoth('logDebug', UpdateTagsToDefaultProcessor.logSource, f"Got tag as {tagName}, which is of type {tagType}, which needs to be assigned value {tagValue}", Logger.GENERAL)
                if tagName is None or tagType is None or tagValue is None:
                    logBoth('logWarning', UpdateTagsToDefaultProcessor.logSource, f"UpdateTagsToDefaultProcessor: Invalid tag entry {key}: {tagInfo}", Logger.ISSUE)
                    allSuccess = False
                    continue

                success = False
                logBoth('logDebug', UpdateTagsToDefaultProcessor.logSource, f"About to call write_bool() or write_float() for tag {tagName}", Logger.GENERAL)
                if tagType == "bool":
                    success = self.ioServer.write_bool(tagName, bool(tagValue))
                elif tagType == "float":
                    success = self.ioServer.write_float(tagName, float(tagValue))
                else:
                    logBoth('logWarning', UpdateTagsToDefaultProcessor.logSource, f"UpdateTagsToDefaultProcessor: Unknown type '{tagType}' for tag '{tagName}'", Logger.ISSUE)
                    allSuccess = False
                    continue

                if success:
                    logBoth('logDebug', UpdateTagsToDefaultProcessor.logSource, f"UpdateTagsToDefaultProcessor: Wrote {tagValue} to {tagName}", Logger.SUCCESS)
                else:
                    logBoth('logWarning', UpdateTagsToDefaultProcessor.logSource, f"UpdateTagsToDefaultProcessor: Failed to write {tagValue} to {tagName}", Logger.PROBLEM)
                    allSuccess = False

            return allSuccess

        except Exception as e:
            logBoth('logCritical', UpdateTagsToDefaultProcessor.logSource, f"UpdateTagsToDefaultProcessor: Exception processing item: {e}", Logger.PROBLEM)
            return False


class IOServer:
    # ==================== QR Code Tags (Step 0) ====================
    PLC_PC_CheckQRCode: str = CosThetaConfigurator.getInstance().getPlcPcCheckQRCodeTagName()
    PC_PLC_QRCodeCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcQRCodeOKTagName()
    PC_PLC_QRCodeCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcQRCodeDoneTagName()

    # ==================== Knuckle Tags (Step 1) ====================
    PLC_PC_CheckKnuckle: str = CosThetaConfigurator.getInstance().getPlcPcCheckKnuckleTagName()
    PC_PLC_KnuckleCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcKnuckleCheckOKTagName()
    PC_PLC_KnuckleCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcKnuckleCheckDoneTagName()

    # ==================== Hub Tags (Step 2) ====================
    PLC_PC_CheckHub: str = CosThetaConfigurator.getInstance().getPlcPcCheckHubTagName()
    PC_PLC_HubCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcHubCheckOKTagName()
    PC_PLC_HubCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcHubCheckDoneTagName()

    # ==================== Hub and Second Bearing Tags (Step 3) ====================
    PLC_PC_CheckHubAndSecondBearing: str = CosThetaConfigurator.getInstance().getPlcPcCheckHubAndSecondBearingTagName()
    PC_PLC_HubAndSecondBearingCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcHubAndSecondBearingCheckOKTagName()
    PC_PLC_HubAndSecondBearingCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcHubAndSecondBearingCheckDoneTagName()

    # ==================== Nut and Plate Washer Tags (Step 4) ====================
    PLC_PC_CheckNutAndPlateWasher: str = CosThetaConfigurator.getInstance().getPlcPcCheckNutAndPlateWasherTagName()
    PC_PLC_NutAndPlateWasherCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcNutAndPlateWasherOKTagName()
    PC_PLC_NutAndPlateWasherCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcNutAndPlateWasherDoneTagName()

    # ==================== Station 2 Torque (Tightening) Tags (Step 5 and 10) ====================
    PLC_PC_Station2TorqueValueSet: str = CosThetaConfigurator.getInstance().getPlcPcStation2TorqueValueSetTagName()
    PLC_PC_Station2TorqueValue: str = CosThetaConfigurator.getInstance().getPlcPcStation2TorqueValueTagName()

    # ==================== Station 3 Free Rotation Done Tag (Step 6) ====================
    PLC_PC_Station3RotationDone: str = CosThetaConfigurator.getInstance().getPlcPcStation3RotationDoneTagName()

    # ==================== No Cap Bunk Tags (Step 7) ====================
    PLC_PC_CheckNoCapBunk: str = CosThetaConfigurator.getInstance().getPlcPcCheckNoCapBunkTagName()
    PC_PLC_NoCapBunkCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcNoCapBunkCheckOKTagName()
    PC_PLC_NoCapBunkCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcNoCapBunkCheckDoneTagName()

    # ==================== Component Press Done Tag (Step 8) ====================
    PLC_PC_ComponentPressDone: str = CosThetaConfigurator.getInstance().getPlcPcComponentPressDoneTagName()

    # ==================== No Bunk Tags (Step 9) ====================
    PLC_PC_CheckNoBunk: str = CosThetaConfigurator.getInstance().getPlcPcCheckNoBunkTagName()
    PC_PLC_NoBunkCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcNoBunkCheckOKTagName()
    PC_PLC_NoBunkCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcNoBunkCheckDoneTagName()

    # ==================== Split Pin and Washer Tags (Step 11) ====================
    PLC_PC_CheckSplitPinAndWasher: str = CosThetaConfigurator.getInstance().getPlcPcCheckSplitPinAndWasherTagName()
    PC_PLC_SplitPinAndWasherCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcSplitPinAndWasherCheckOKTagName()
    PC_PLC_SplitPinAndWasherCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcSplitPinAndWasherCheckDoneTagName()

    # ==================== Cap Tags (Step 12) ====================
    PLC_PC_CheckCap: str = CosThetaConfigurator.getInstance().getPlcPcCheckCapTagName()
    PC_PLP_CapCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcCapCheckOKTagName()
    PC_PLC_CapCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcCapCheckDoneTagName()

    # ==================== Bunk Tags (Step 13) ====================
    PLC_PC_CheckBunk: str = CosThetaConfigurator.getInstance().getPlcPcCheckBunkTagName()
    PC_PLC_BunkCheckOK: str = CosThetaConfigurator.getInstance().getPcPlcBunkCheckOKTagName()
    PC_PLC_BunkCheckDone: str = CosThetaConfigurator.getInstance().getPcPlcBunkCheckDoneTagName()

    # ==================== Cap Press Done Tag (Step 14) ====================
    PLC_PC_CapPressDone: str = CosThetaConfigurator.getInstance().getPlcPcCapPressDoneTagName()

    # ==================== Station 3 Free Rotation Torque Tags (Step 15) ====================
    PLC_PC_Station3TorqueValueSet: str = CosThetaConfigurator.getInstance().getPlcPcStation3TorqueValueSetTagName()
    PLC_PC_Station3TorqueValue: str = CosThetaConfigurator.getInstance().getPlcPcStation3TorqueValueTagName()

    # ==================== Rotation Settings Tags (PC writes to PLC) ====================
    PC_PLC_NoOfRotation1CCW: str = CosThetaConfigurator.getInstance().getPcPlcNoOfRotation1CCWTagName()
    PC_PLC_NoOfRotation1CW: str = CosThetaConfigurator.getInstance().getPcPlcNoOfRotation1CWTagName()
    PC_PLC_NoOfRotation2CCW: str = CosThetaConfigurator.getInstance().getPcPlcNoOfRotation2CCWTagName()
    PC_PLC_NoOfRotation2CW: str = CosThetaConfigurator.getInstance().getPcPlcNoOfRotation2CWTagName()
    PC_PLC_LH_RH_Selection: str = CosThetaConfigurator.getInstance().getPcPlcLHRHSelectionTagName()
    PC_PLC_RotationUnitRPM: str = CosThetaConfigurator.getInstance().getPcPlcRotationUnitRPMTagName()

    # ==================== System Tags ====================
    PLC_PC_EmergencyAbort: str = CosThetaConfigurator.getInstance().getPlcPcEmergencyAbortTagName()
    PLC_PC_WatchTag: str = CosThetaConfigurator.getInstance().getPlcPcWatchTagName()
    PC_PLC_ConnectionStatusTag: str = CosThetaConfigurator.getInstance().getPcPlcConnectionStatusTagName()

    # ==================== Configuration Values ====================
    PLC_IP: str = CosThetaConfigurator.getInstance().getPlcIP()
    PLC_DEBUG: bool = CosThetaConfigurator.getInstance().getPlcDebug()
    PLC_SLEEPTIME_BETWEEN_OK_AND_DONE: float = CosThetaConfigurator.getInstance().getPlcSleepTimeBetweenOKAndDone()

    # ==================== Constants ====================
    FALSE_FLOAT_VALUE: float = -1234.
    FALSE_INT_VALUE: int = -1234
    WATCH_TAG_VALUE: int = 1234
    NO_CONNECTION: int = -1986754392
    CONSECUTIVE_CONNECTION_DOWN_COUNT: int = 0

    logSource = getFullyQualifiedName(__file__)
    LAST_CONNECTION_STATUS_UPDATED: bool = False
    LOG_CONNECTION_PROBLEM_EVERY_N_SECS = CosThetaConfigurator.getInstance().getLogDisconnectionsAfterNSecs()

    def __init__(self, plc_ip: Union[str, None] = None, mode : str = "TEST", mockInstance: bool = False):
        # Class variables
        IOServer.logSource = getFullyQualifiedName(__file__, __class__)
        self.machineState = MachineStateMachine()  # Instance of MachineStateMachine
        self.shutdown = False

        self.mode = mode
        setDatabaseName(mode = self.mode, createDB=False)

        self.read_interval = CosThetaConfigurator.getInstance().getPlcReadInterval()  # 200 ms
        self.write_loop_interval = CosThetaConfigurator.getInstance().getPlcWriteInterval()  # 100 ms
        self.CONNECTION_CHECK_INTERVAL = CosThetaConfigurator.getInstance().getPlcConnectionCheckInterval()  # seconds

        self.redisHostname: str = CosThetaConfigurator.getInstance().getRedisHost()
        self.redisPort: int = CosThetaConfigurator.getInstance().getRedisPort()

        self.redisConnectionForReads: Union[Redis, None] = None
        self.clientRedisConnectedForReads: bool = False
        self.redisConnectionForWrites: Union[Redis, None] = None
        self.clientRedisConnectedForWrites: bool = False
        self.heartbeatRedisConnection: Union[Redis, None] = None
        self.heartbeatRedisConnected: bool = False
        self.combinedHeartbeatRedisConnection: Union[Redis, None] = None
        self.combinedHeartbeatRedisConnected: bool = False
        self.emergencyRedisConnection: Union[Redis, None] = None
        self.emergencyRedisConnected: bool = False

        self.connectToRedis(True)
        self.connectToRedisForHeartbeatAndEmergencyMonitoring(True)

        self.plc_ip = plc_ip if plc_ip is not None else IOServer.PLC_IP
        self.mockInstance = mockInstance

        self.clientForReads: Union[LogixDriver, None] = None
        self.clientForWrites: Union[LogixDriver, None] = None

        self.readingLock = threading.Lock()
        self.writingLock = threading.Lock()

        # Database connection pool for reading machine settings
        self.dbConnectionPool: Union[ThreadedConnectionPool, None] = None
        self._initDatabaseConnectionPool()

        # Cycle time tracking
        # _opTimestamps holds {key: [start_time, end_time]} for each measured operation.
        # Keys are the OP_* constants defined in _resetOpTimestamps().
        self._opTimestamps: Dict[str, List[Optional[float]]] = {}
        self._cycleInProgress: bool = False
        self._resetOpTimestamps()

        # Current QR Code for this cycle
        self.currentQRCode: str = ""

        # Initialize logging
        self.logger = logging.getLogger("pycomm3")
        self.logger.setLevel(logging.CRITICAL)

        # Start PLC connection and threads
        self.connectionInProgress: bool = False
        self.connectionAttempts: int = 0
        self.connectPLC()

        time.sleep(2)
        self.resetAll()

        time.sleep(3)
        self.startThreads()

    def connectToRedis(self, forceRenew=False):
        if forceRenew:
            self.redisConnectionForReads = None
            self.clientRedisConnectedForReads = False
            self.redisConnectionForWrites = None
            self.clientRedisConnectedForWrites = False

        if not self.clientRedisConnectedForReads:
            try:
                self.redisConnectionForReads = Redis(self.redisHostname, self.redisPort,
                                                     retry_on_timeout=True)
                self.clientRedisConnectedForReads = True
                logBoth('logInfo', IOServer.logSource, 'Redis connection established for Reads', Logger.SUCCESS)
            except:
                self.clientRedisConnectedForReads = False
                logBoth('logCritical', IOServer.logSource, f'Could not get Redis Connection for Reads', Logger.PROBLEM)

        if not self.clientRedisConnectedForWrites:
            try:
                self.redisConnectionForWrites = Redis(self.redisHostname, self.redisPort,
                                                      retry_on_timeout=True)
                self.clientRedisConnectedForWrites = True
                logBoth('logInfo', IOServer.logSource, 'Redis connection established for Writes', Logger.SUCCESS)
            except:
                self.clientRedisConnectedForWrites = False
                logBoth('logCritical', IOServer.logSource, f'Could not get Redis Connection for Writes', Logger.PROBLEM)

    def connectToRedisForHeartbeatAndEmergencyMonitoring(self, forceRenew=False):
        if forceRenew:
            self.heartbeatRedisConnection = None
            self.heartbeatRedisConnected = False
            self.combinedHeartbeatRedisConnection = None
            self.combinedHeartbeatRedisConnected = False
            self.emergencyRedisConnection = None
            self.emergencyRedisConnected = False

        if not self.heartbeatRedisConnected:
            try:
                self.heartbeatRedisConnection = Redis(self.redisHostname, self.redisPort, retry_on_timeout=True)
                self.heartbeatRedisConnected = True
                logBoth('logInfo', IOServer.logSource, 'Heartbeat Redis connection established', Logger.SUCCESS)
            except:
                self.heartbeatRedisConnected = False
                logBoth('logCritical', IOServer.logSource, f'Could not get Heartbeat Redis Connection', Logger.PROBLEM)

        if not self.combinedHeartbeatRedisConnected:
            try:
                self.combinedHeartbeatRedisConnection = Redis(self.redisHostname, self.redisPort, retry_on_timeout=True)
                self.combinedHeartbeatRedisConnected = True
                logBoth('logInfo', IOServer.logSource, 'Combined Heartbeat Redis connection established', Logger.SUCCESS)
            except:
                self.combinedHeartbeatRedisConnected = False
                logBoth('logCritical', IOServer.logSource, f'Could not get Heartbeat Redis Connection', Logger.PROBLEM)

        if not self.emergencyRedisConnected:
            try:
                self.emergencyRedisConnection = Redis(self.redisHostname, self.redisPort, retry_on_timeout=True)
                self.emergencyRedisConnected = True
                logBoth('logInfo', IOServer.logSource, 'Emergency Redis connection established', Logger.SUCCESS)
            except:
                self.emergencyRedisConnected = False
                logBoth('logCritical', IOServer.logSource, f'Could not get Emergency Redis Connection', Logger.PROBLEM)

    def _initDatabaseConnectionPool(self):
        """Initialize a connection pool for database reads."""
        try:
            self.dbConnectionPool = ThreadedConnectionPool(
                minconn=1,
                maxconn=3,
                user="postgres",
                password="postgres",
                host="127.0.0.1",
                port="5432",
                database=getDatabaseName()
            )
            logBoth('logInfo', IOServer.logSource, f"Database connection pool initialized for {getDatabaseName()}", Logger.SUCCESS)
        except Exception as e:
            logBoth('logCritical', IOServer.logSource, f"Failed to initialize database connection pool: {e}", Logger.PROBLEM)
            self.dbConnectionPool = None

    def writeRotationSettingsToPLC(self, qrCode: str) -> bool:
        """
        Write rotation settings to PLC based on QR code (LHS vs RHS).

        Args:
            qrCode: The scanned QR code string

        Returns:
            True if settings were written successfully, False otherwise
        """
        if not qrCode:
            logBoth('logWarning', IOServer.logSource, "Cannot write rotation settings: QR code is empty", Logger.ISSUE)
            return False

        try:
            # Parse QR code to get LHS/RHS designation
            modelName, lhs_rhs, tonnage = getModel_LHSRHS_AndTonnage(qrCode)

            if lhs_rhs == "UNKNOWN":
                logBoth('logWarning', IOServer.logSource, f"Cannot determine LHS/RHS from QR code: {qrCode}", Logger.ISSUE)
                return False

            # Get machine settings from database
            settings = getMachineSettings(getDatabaseName())
            if not settings:
                logBoth('logCritical', IOServer.logSource, "Failed to get machine settings from database", Logger.PROBLEM)
                return False

            noOfRotation1CCW_db = settings.get('NoOfRotation1CCW', 5)
            noOfRotation1CW_db = settings.get('NoOfRotation1CW', 5)
            noOfRotation2CCW_db = settings.get('NoOfRotation2CCW', 5)
            noOfRotation2CW_db = settings.get('NoOfRotation2CW', 5)
            rotationUnitRPM = settings.get('RotationUnitRPM', 60)

            # Determine values based on LHS/RHS
            if lhs_rhs.upper() == "LHS":
                noOfRotation1CCW = 0
                noOfRotation1CW = noOfRotation1CW_db
                noOfRotation2CCW = 0
                noOfRotation2CW = noOfRotation2CW_db
                lhRhSelection = 1
                logBoth('logInfo', IOServer.logSource, f"LHS detected - Setting CW rotations: R1CW={noOfRotation1CW}, R2CW={noOfRotation2CW}, lhRhSelection={lhRhSelection}", Logger.SUCCESS)
            elif lhs_rhs.upper() == "RHS":
                noOfRotation1CCW = noOfRotation1CCW_db
                noOfRotation1CW = 0
                noOfRotation2CCW = noOfRotation2CCW_db
                noOfRotation2CW = 0
                lhRhSelection = 2
                logBoth('logInfo', IOServer.logSource, f"RHS detected - Setting CCW rotations: R1CCW={noOfRotation1CCW}, R2CCW={noOfRotation2CCW}, lhRhSelection={lhRhSelection}", Logger.SUCCESS)
            else:
                logBoth('logWarning', IOServer.logSource, f"Unknown LHS/RHS value: {lhs_rhs}", Logger.ISSUE)
                return False

            # Write all values to PLC
            success = True
            success = success and self.write_int(IOServer.PC_PLC_NoOfRotation1CCW, noOfRotation1CCW)
            success = success and self.write_int(IOServer.PC_PLC_NoOfRotation1CW, noOfRotation1CW)
            success = success and self.write_int(IOServer.PC_PLC_NoOfRotation2CCW, noOfRotation2CCW)
            success = success and self.write_int(IOServer.PC_PLC_NoOfRotation2CW, noOfRotation2CW)
            success = success and self.write_int(IOServer.PC_PLC_LH_RH_Selection, lhRhSelection)
            success = success and self.write_int(IOServer.PC_PLC_RotationUnitRPM, rotationUnitRPM)

            if success:
                logBoth('logInfo', IOServer.logSource, f"Successfully wrote rotation settings to PLC for {lhs_rhs}", Logger.SUCCESS)
            else:
                logBoth('logWarning', IOServer.logSource, "Failed to write some rotation settings to PLC", Logger.PROBLEM)

            return success

        except Exception as e:
            logBoth('logCritical', IOServer.logSource, f"Exception writing rotation settings to PLC: {e}", Logger.PROBLEM)
            return False

    # ==================== Cycle Time Tracking ====================
    #
    # Strategy: record wall-clock timestamps at the precise moments that bound
    # pure machine/camera work, ignoring all manual-operator wait time.
    #
    # Each operation has a START (PLC trigger received → camera command sent)
    # and an END (Done tag written back to PLC, or PLC signals completion).
    #
    # _opTimestamps  : Dict[str, List[Optional[float]]]
    #   key  → OP_* constant string
    #   value → [start_time, end_time]   (None until recorded)

    # ── Operation key constants ────────────────────────────────────────────
    OP_KNUCKLE        = "T1_Knuckle"
    OP_HUB_BEARING    = "T2_HubAndBottomBearing"
    OP_TOP_BEARING    = "T3_TopBearing"
    OP_NUT_WASHER     = "T4_NutAndPlateWasher_to_FreeRotations"
    OP_NOCAP_BUNK     = "T5_NoCapBunk"
    OP_TORQUE2        = "T6_NoCapBunkStart_to_Torque2Done"
    OP_SPLITPIN       = "T7_SplitPinAndWasher"
    OP_CAP            = "T8_Cap"
    OP_BUNK_CAP_PRESS = "T9_BunkCapPress_to_Station3TorqueValueSet"

    ALL_OP_KEYS = [
        OP_KNUCKLE, OP_HUB_BEARING, OP_TOP_BEARING, OP_NUT_WASHER,
        OP_NOCAP_BUNK, OP_TORQUE2, OP_SPLITPIN, OP_CAP, OP_BUNK_CAP_PRESS,
    ]

    def _resetOpTimestamps(self) -> None:
        """Initialise / clear all operation timestamps to [None, None]."""
        self._opTimestamps = {key: [None, None] for key in IOServer.ALL_OP_KEYS}
        self._cycleInProgress = False

    def _recordOpStart(self, key: str) -> None:
        """Record the start wall-clock time for the given operation key."""
        try:
            self._opTimestamps[key][0] = time.time()
            self._cycleInProgress = True
        except Exception as e:
            logBoth('logWarning', IOServer.logSource, f"_recordOpStart({key}) error: {e}", Logger.ISSUE)

    def _recordOpEnd(self, key: str) -> None:
        """Record the end wall-clock time for the given operation key."""
        try:
            self._opTimestamps[key][1] = time.time()
        except Exception as e:
            logBoth('logWarning', IOServer.logSource, f"_recordOpEnd({key}) error: {e}", Logger.ISSUE)

    def _computeAndLogCycleTimes(self) -> None:
        """
        Compute delta times for all 9 operations, sum them, add 8 sec fixed
        overhead, then log the result compulsorily at ERROR/PROBLEM level so
        it always appears in both console and file logs.
        """
        ts = self._opTimestamps

        def getDelta(key: str) -> float:
            """Return end-start for key, or 0.0 if either timestamp is missing."""
            pair = ts.get(key, [None, None])
            if pair[0] is not None and pair[1] is not None:
                delta = pair[1] - pair[0]
                return max(delta, 0.0)   # guard against clock skew
            return 0.0

        T1 = getDelta(IOServer.OP_KNUCKLE)
        T2 = getDelta(IOServer.OP_HUB_BEARING)
        T3 = getDelta(IOServer.OP_TOP_BEARING)
        T4 = getDelta(IOServer.OP_NUT_WASHER)
        T5 = getDelta(IOServer.OP_NOCAP_BUNK)
        T6 = getDelta(IOServer.OP_TORQUE2)
        T7 = getDelta(IOServer.OP_SPLITPIN)
        T8 = getDelta(IOServer.OP_CAP)
        T9 = getDelta(IOServer.OP_BUNK_CAP_PRESS)

        sumOfDeltas   = T1 + T2 + T3 + T4 + T5 + T6 + T7 + T8 + T9
        fixedOverhead = 8   # seconds — fixed machine overhead per cycle
        totalMachineTime = sumOfDeltas + fixedOverhead

        cycleTimeMsg = (
            f"\n{'=' * 70}\n"
            f"MACHINE CYCLE TIME BREAKDOWN (pure machine/camera time only)\n"
            f"{'=' * 70}\n"
            f"T1  (Knuckle check           : PLC trigger → KnuckleCheckDone)          : {T1:.3f} sec\n"
            f"T2  (Hub & bottom bearing    : PLC trigger → HubCheckDone)               : {T2:.3f} sec\n"
            f"T3  (Top bearing             : PLC trigger → HubAndSecondBearingDone)    : {T3:.3f} sec\n"
            f"T4  (Nut & plate washer      : PLC trigger → Station3RotationDone)       : {T4:.3f} sec\n"
            f"T5  (No-cap bunk             : PLC trigger → NoCapBunkCheckDone)         : {T5:.3f} sec\n"
            f"T6  (No-cap bunk → Torque2   : PLC trigger → Station2TorqueValueSet)     : {T6:.3f} sec\n"
            f"T7  (Split pin & washer      : PLC trigger → SplitPinAndWasherDone)      : {T7:.3f} sec\n"
            f"T8  (Cap                     : PLC trigger → CapCheckDone)               : {T8:.3f} sec\n"
            f"T9  (Bunk for cap press      : PLC trigger → Station3TorqueValueSet ready): {T9:.3f} sec\n"
            f"{'-' * 70}\n"
            f"Sum of T1 – T9                                                           : {sumOfDeltas:.3f} sec\n"
            f"Fixed overhead                                                           : +{fixedOverhead} sec\n"
            f"{'=' * 70}\n"
            f"TOTAL MACHINE TIME                                                       : {totalMachineTime:.3f} sec\n"
            f"{'=' * 70}\n"
        )

        # Always print to terminal
        printBoldYellow(cycleTimeMsg)

        # Log at PROBLEM level → guaranteed to appear in both console and file logs
        logBoth('logCritical', IOServer.logSource, cycleTimeMsg, Logger.PROBLEM)

    def getCurrentTagsToBeRead(self) -> Tuple[list[str] | None, list[Type[bool | float] | None] | None]:
        """
        Get the PLC tags to be read based on current machine state.

        State to Excel Step Mapping:
        - States 1-2: QR Code (Step 0)
        - States 3-4: Knuckle (Step 1)
        - States 5-6: Hub (Step 2) - uses PLC_PC_CheckHub
        - States 7-8: Hub and Second Bearing (Step 3) - uses PLC_PC_CheckHubAndSecondBearing
        - States 9-10: Nut and Plate Washer (Step 4)
        - States 11-12: Tightening Torque 1 (Step 5) - uses PLC_PC_Station2TorqueValueSet
        - State 13: Free Rotations Done (Step 6)
        - States 14-15: Bunk for Component Press (Step 7) - uses PLC_PC_CheckBunk
        - State 16: Component Press Done (Step 8)
        - States 17-18: No Bunk (Step 9)
        - States 19-20: Tightening Torque 2 (Step 10) - uses PLC_PC_Station2TorqueValueSet (reused)
        - States 21-22: Split Pin and Washer (Step 11)
        - States 23-24: Cap (Step 12)
        - States 25-26: Bunk for Cap Press (Step 13) - uses PLC_PC_CheckBunk (reused)
        - State 27: Cap Press Done (Step 14)
        - States 28-29: Free Rotation Torque (Step 15)
        """
        currentState = self.machineState.getCurrentState()

        # Step 0: QR Code
        if currentState == MachineState.READ_QR_CODE:
            return [IOServer.PLC_PC_CheckQRCode], [bool]

        # Step 1: Knuckle
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE:
            return [IOServer.PLC_PC_CheckKnuckle], [bool]

        # Step 2: Hub (maps to HUB_AND_BOTTOM_BEARING state)
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING:
            return [IOServer.PLC_PC_CheckHub], [bool]

        # Step 3: Hub and Second Bearing (maps to TOP_BEARING state)
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING:
            return [IOServer.PLC_PC_CheckHubAndSecondBearing], [bool]

        # Step 4: Nut and Plate Washer
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER:
            return [IOServer.PLC_PC_CheckNutAndPlateWasher], [bool]

        # Step 5: Tightening Torque 1 (Station 2)
        if currentState == MachineState.READ_TIGHTENING_TORQUE_1_DONE:
            return [IOServer.PLC_PC_Station2TorqueValueSet], [bool]
        if currentState == MachineState.READ_TIGHTENING_TORQUE_1:
            return [IOServer.PLC_PC_Station2TorqueValue], [float]

        # Step 6: Free Rotations Done (Station 3)
        if currentState == MachineState.READ_FREE_ROTATIONS_DONE:
            return [IOServer.PLC_PC_Station3RotationDone], [bool]

        # Step 7: No Cap Bunk for Component Press
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS:
            return [IOServer.PLC_PC_CheckNoCapBunk], [bool]

        # Step 8: Component Press Done
        if currentState == MachineState.READ_COMPONENT_PRESS_DONE:
            return [IOServer.PLC_PC_ComponentPressDone], [bool]

        # Step 9: No Bunk
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK:
            return [IOServer.PLC_PC_CheckNoBunk], [bool]

        # Step 10: Tightening Torque 2 (Station 2 - second round, reuses same tags)
        if currentState == MachineState.READ_TIGHTENING_TORQUE_2_DONE:
            return [IOServer.PLC_PC_Station2TorqueValueSet], [bool]
        if currentState == MachineState.READ_TIGHTENING_TORQUE_2:
            return [IOServer.PLC_PC_Station2TorqueValue], [float]

        # Step 11: Split Pin and Washer
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER:
            return [IOServer.PLC_PC_CheckSplitPinAndWasher], [bool]

        # Step 12: Cap
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP:
            return [IOServer.PLC_PC_CheckCap], [bool]

        # Step 13: Bunk for Cap Press - reuses CheckBunk
        if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS:
            return [IOServer.PLC_PC_CheckBunk], [bool]

        # Step 14: Cap Press Done
        if currentState == MachineState.READ_CAP_PRESS_DONE:
            return [IOServer.PLC_PC_CapPressDone], [bool]

        # Step 15: Free Rotation Torque (Station 3 - final reading)
        if currentState == MachineState.READ_FREE_ROTATION_TORQUE_1_DONE:
            return [IOServer.PLC_PC_Station3TorqueValueSet], [bool]
        if currentState == MachineState.READ_FREE_ROTATION_TORQUE_1:
            return [IOServer.PLC_PC_Station3TorqueValue], [float]

        return None, None

    def getCurrentTagsToBeWritten(self) -> list[str] | None:
        """
        Get the PLC tags to be written based on current machine state.
        NOTE the order of the tags: The OK tag is populated first, and then the Done tag is populated.
        This order ensures that when the PLC reads the Done tag, it ALWAYS has the CORRECT RESULT of ImageProcessing.
        NOTE: The 3rd tag is the trigger tag eg CheckKnuckle, CheckHub which is to be reset to False
        in the same operation, after the first 2 are populated.
        """
        currentState = self.machineState.getCurrentState()

        # Step 0: QR Code
        if currentState == MachineState.WRITE_QR_CODE:
            return [IOServer.PC_PLC_QRCodeCheckOK, IOServer.PC_PLC_QRCodeCheckDone, IOServer.PLC_PC_CheckQRCode]

        # Step 1: Knuckle
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_KNUCKLE:
            return [IOServer.PC_PLC_KnuckleCheckOK, IOServer.PC_PLC_KnuckleCheckDone, IOServer.PLC_PC_CheckKnuckle]

        # Step 2: Hub (maps to HUB_AND_BOTTOM_BEARING state)
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING:
            return [IOServer.PC_PLC_HubCheckOK, IOServer.PC_PLC_HubCheckDone, IOServer.PLC_PC_CheckHub]

        # Step 3: Hub and Second Bearing (maps to TOP_BEARING state)
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_TOP_BEARING:
            return [IOServer.PC_PLC_HubAndSecondBearingCheckOK, IOServer.PC_PLC_HubAndSecondBearingCheckDone,
                    IOServer.PLC_PC_CheckHubAndSecondBearing]

        # Step 4: Nut and Plate Washer
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_NUT_AND_PLATEWASHER:
            return [IOServer.PC_PLC_NutAndPlateWasherCheckOK, IOServer.PC_PLC_NutAndPlateWasherCheckDone,
                    IOServer.PLC_PC_CheckNutAndPlateWasher]

        # Step 7: No Cap Bunk for Component Press
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS:
            return [IOServer.PC_PLC_NoCapBunkCheckOK, IOServer.PC_PLC_NoCapBunkCheckDone,
                    IOServer.PLC_PC_CheckNoCapBunk]

        # Step 9: No Bunk
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_NO_BUNK:
            return [IOServer.PC_PLC_NoBunkCheckOK, IOServer.PC_PLC_NoBunkCheckDone, IOServer.PLC_PC_CheckNoBunk]

        # Step 11: Split Pin and Washer
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER:
            return [IOServer.PC_PLC_SplitPinAndWasherCheckOK, IOServer.PC_PLC_SplitPinAndWasherCheckDone,
                    IOServer.PLC_PC_CheckSplitPinAndWasher]

        # Step 12: Cap
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_CAP:
            return [IOServer.PC_PLP_CapCheckOK, IOServer.PC_PLC_CapCheckDone, IOServer.PLC_PC_CheckCap]

        # Step 13: Bunk for Cap Press - reuses CheckBunk
        if currentState == MachineState.WRITE_RESULT_OF_CHECKING_BUNK_FOR_CAP_PRESS:
            return [IOServer.PC_PLC_BunkCheckOK, IOServer.PC_PLC_BunkCheckDone, IOServer.PLC_PC_CheckBunk]

        return None

    def connectPLC(self, forceRenew=False) -> bool | None:
        """Connect to the PLC using pycomm3 or MockPLC."""
        if self.connectionInProgress:
            return None
        self.connectionInProgress = True
        self.connectionAttempts += 1

        try:
            if forceRenew:
                if self.clientForReads is not None:
                    try:
                        self.clientForReads.close()
                    except:
                        pass
                if self.clientForWrites is not None:
                    try:
                        self.clientForWrites.close()
                    except:
                        pass
                self.clientForReads = None
                self.clientForWrites = None

            # Use MockPLC if mockInstance is True
            if self.mockInstance:
                from MockPLC import MockPLC
                self.clientForReads = MockPLC()
                self.clientForReads.open()
                logBoth('logInfo', IOServer.logSource, f"Connected to MockPLC for Reads", Logger.SUCCESS)
                self.clientForWrites = self.clientForReads  # Share same instance
                logBoth('logInfo', IOServer.logSource, f"Connected to MockPLC for Writes (shared instance)", Logger.SUCCESS)
            else:
                self.clientForReads = LogixDriver(f"{self.plc_ip}")
                self.clientForReads.open()
                logBoth('logInfo', IOServer.logSource, f"Connected to PLC for Reads at {self.plc_ip}", Logger.SUCCESS)
                self.clientForWrites = LogixDriver(f"{self.plc_ip}")
                self.clientForWrites.open()
                logBoth('logInfo', IOServer.logSource, f"Connected to PLC for Writes at {self.plc_ip}", Logger.SUCCESS)

            self.connectionInProgress = False
            self.connectionAttempts = 0
            return True
        except Exception as e:
            if (self.connectionAttempts == 1) or (
                    (self.connectionAttempts % IOServer.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) % 5) == 0:
                logBoth('logCritical', IOServer.logSource, f"PLC connection error: {e}", Logger.PROBLEM)
            try:
                self.clientForReads.close()
            except:
                pass
            try:
                self.clientForWrites.close()
            except:
                pass
            self.clientForReads = None
            self.clientForWrites = None
            self.connectionInProgress = False
            return False

    def launchConnectionMonitoringThread(self):
        objRef = self

        def connectionCheckingLoop():
            """Loop to check PLC connection status."""
            while not objRef.shutdown:
                time.sleep(objRef.CONNECTION_CHECK_INTERVAL)

                tryToConnect: bool = False
                if ((not objRef.clientForReads) or (not objRef.clientForReads.connected) or
                        (not objRef.clientForWrites) or (not objRef.clientForWrites.connected)):
                    tryToConnect = True
                else:
                    try:
                        readValue: int = 0
                        readValue = self.read_int(IOServer.PLC_PC_WatchTag)
                        if readValue != IOServer.WATCH_TAG_VALUE:
                            raise Exception(f"Could not read tag {IOServer.PLC_PC_WatchTag} from PLC")
                    except Exception:
                        if (objRef.connectionAttempts == 1) or (
                                (objRef.connectionAttempts % IOServer.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) % 5) == 0:
                            objRef.logger.fatal(f"PLC connection test failed")
                            logBoth('logCritical', IOServer.logSource, f"PLC connection test failed. Reconnecting...", Logger.PROBLEM)
                        tryToConnect = True

                if tryToConnect:
                    objRef.connectPLC(forceRenew=True)

        self.connectionCheckThread = threading.Thread(name=f'IOServer Connection Keep Alive Thread',
                                                      target=connectionCheckingLoop,
                                                      args=(), daemon=True)
        self.connectionCheckThread.start()

    def launchHeartbeatThread(self):
        objRef = self

        def reportHeartbeat():
            ioHeartbeatGap = CosThetaConfigurator.getInstance().getIOConnectionStatusSleepInterval()
            while not objRef.shutdown:
                try:
                    if objRef.clientForReads is None or objRef.clientForWrites is None:
                        sendHeartbeatFromIOServerToHeartbeatServer(redisConnection=objRef.heartbeatRedisConnection,
                                                                   status=DEAD)
                    elif not objRef.clientForReads.connected or not objRef.clientForWrites.connected:
                        sendHeartbeatFromIOServerToHeartbeatServer(redisConnection=objRef.heartbeatRedisConnection,
                                                                   status=DEAD)
                    else:
                        sendHeartbeatFromIOServerToHeartbeatServer(redisConnection=objRef.heartbeatRedisConnection,
                                                                   status=ALIVE)
                except Exception as e:
                    logBoth('logCritical', IOServer.logSource, f"Exception {e} encountered in IO heartbeat", Logger.PROBLEM)
                    objRef.connectToRedisForHeartbeatAndEmergencyMonitoring(forceRenew=True)
                try:
                    time.sleep(ioHeartbeatGap)
                except:
                    pass

        self.heartbeatThread = threading.Thread(name=f"IO Heartbeat Thread", target=reportHeartbeat, args=(),
                                                daemon=True)
        self.heartbeatThread.start()

    def launchThreadForUpdatingCombinedHeartbeat(self):
        objRef = self

        def updateHeartbeat():
            heartbeatGap = CosThetaConfigurator.getInstance().getCombinedConnectionStatusUpdateInterval()
            while not objRef.shutdown:
                try:

                    # WHILE TESTING PLC AND PC COMMUNICATION, currentStatus is set to True.
                    # IN PRODUCTION, set this back to readCombinedHeartbeatInIOServerFromHeartbeatServer(objRef.combinedHeartbeatRedisConnection)

                    # currentStatus = readCombinedHeartbeatInIOServerFromHeartbeatServer(
                    #     objRef.combinedHeartbeatRedisConnection)
                    currentStatus = True
                    if currentStatus:
                        IOServer.CONSECUTIVE_CONNECTION_DOWN_COUNT = 0
                        statusToBeSent = not IOServer.LAST_CONNECTION_STATUS_UPDATED
                        objRef.write_bool(IOServer.PC_PLC_ConnectionStatusTag, statusToBeSent, debug=False)
                        IOServer.LAST_CONNECTION_STATUS_UPDATED = statusToBeSent
                    else:
                        IOServer.CONSECUTIVE_CONNECTION_DOWN_COUNT += 1
                        if (IOServer.CONSECUTIVE_CONNECTION_DOWN_COUNT == 2):
                            logBoth('logCritical', IOServer.logSource, f"Combined Heartbeat - connection problem somewhere : sendEmergencyAbortFromIOServerToFEServer", Logger.PROBLEM)
                            sendEmergencyAbortFromIOServerToFEServer(objRef.emergencyRedisConnection)
                            objRef.resetAll()
                            objRef._resetOpTimestamps()  # Clear cycle timing on abort
                            objRef.machineState.setCurrentState(MachineState.READ_QR_CODE)
                            objRef.write_bool(IOServer.PLC_PC_CheckQRCode, True)
                except Exception as e:
                    logBoth('logCritical', IOServer.logSource, f"Exception {e} encountered in combined heartbeat", Logger.PROBLEM)
                    objRef.connectToRedisForHeartbeatAndEmergencyMonitoring(forceRenew=True)
                try:
                    time.sleep(heartbeatGap)
                except:
                    pass

        combinedHeartbeatThread = threading.Thread(name=f"Combined Heartbeat Update Thread", target=updateHeartbeat,
                                                   args=(), daemon=True)
        combinedHeartbeatThread.start()

    def launchEmergencyMonitoringThread(self):
        objRef = self

        def monitorEmergency():
            while not objRef.shutdown:
                emergencyActivated: bool = False
                if (objRef.clientForReads is not None):
                    if objRef.clientForReads.connected:
                        try:
                            emergencyActivated = objRef.read_bool(IOServer.PLC_PC_EmergencyAbort)
                        except Exception as e:
                            logBoth('logCritical', IOServer.logSource, f"Exception {e} encountered in emergency monitoring", Logger.PROBLEM)
                            objRef.connectToRedisForHeartbeatAndEmergencyMonitoring(forceRenew=True)
                if emergencyActivated:
                    logBoth('logCritical', IOServer.logSource, f"Combined Heartbeat - Emergency Button pressed in Machine : sendEmergencyAbortFromIOServerToFEServer", Logger.PROBLEM)
                    sendAbortFromIOServerToQRCodeServer(objRef.emergencyRedisConnection)
                    time.sleep(0.5)
                    clearKeyCommunicationQueuesOnAbort()
                    time.sleep(0.2)
                    sendEmergencyAbortFromIOServerToFEServer(objRef.emergencyRedisConnection)
                    objRef.resetTagToFalse(IOServer.PLC_PC_EmergencyAbort)
                    objRef.resetAll()
                    objRef._resetOpTimestamps()  # Clear cycle timing on abort
                    objRef.machineState.setCurrentState(MachineState.READ_QR_CODE)
                    objRef.write_bool(IOServer.PLC_PC_CheckQRCode, True)
                try:
                    time.sleep(1.0)
                except:
                    pass

        emergencyMonitoringThread = threading.Thread(name=f"Emergency Monitoring Thread", target=monitorEmergency,
                                                     args=(), daemon=True)
        emergencyMonitoringThread.start()

    def launchMonitorStopCommandThread(self):
        objRef = self

        def lookForStop():
            while not objRef.shutdown:
                try:
                    if objRef.heartbeatRedisConnected:
                        _, stopNow = getStopCommandFromQueue(objRef.heartbeatRedisConnection)
                        if stopNow:
                            objRef.shutdown = True
                            sendStoppedResponse(objRef.heartbeatRedisConnection, aProducer=IOServer.logSource)
                    else:
                        objRef.connectToRedisForHeartbeatAndEmergencyMonitoring(False)
                except:
                    pass
                if not objRef.shutdown:
                    time.sleep(2)

        self.monitorStopThread = threading.Thread(name=f'Monitor Stop Thread in IOServer - IOserver',
                                                  target=lookForStop,
                                                  args=(), daemon=True)
        self.monitorStopThread.start()

    def launchReadLoopThread(self):
        objRef = self

        def readLoop():
            """Read loop to read the input for current machine states"""
            written_TagsToBeRead: int = 0
            writeCounter = 0
            while not objRef.shutdown:
                try:
                    writeCounter += 1
                    valueRead: bool = False
                    goAheadToProcessing: bool = False
                    allok: bool = True
                    typeOfValues: str = "nothing"
                    finalValue: float = IOServer.FALSE_FLOAT_VALUE

                    if ((objRef.clientForReads is not None) and objRef.clientForReads.connected
                            and not objRef.connectionInProgress):
                        tagsToBeRead, valueTypes = objRef.getCurrentTagsToBeRead()
                        if tagsToBeRead is not None:
                            # if (writeCounter % 3) == 0:
                            #     printBoldBlue(f"Tags to be read are {tagsToBeRead} whose respective valueTypes are {valueTypes}")
                            if written_TagsToBeRead == 0:
                                written_TagsToBeRead += 1
                            if len(tagsToBeRead) == 1:
                                goAheadToProcessing = True
                                if valueTypes[0] == bool:
                                    typeOfValues = "bool"
                                    valueRead = objRef.read_bool(tagsToBeRead[0])
                                    allok = allok and valueRead
                                elif valueTypes[0] == float:
                                    typeOfValues = "float"
                                    finalValue = objRef.read_float(tagsToBeRead[0])
                            else:
                                typeOfValues = "bool"
                                valueRead = objRef.read_bool(tagsToBeRead[0])
                                allok = allok and valueRead
                                if allok:
                                    goAheadToProcessing = True
                                    valueRead = objRef.read_bool(tagsToBeRead[1])
                                    allok = allok and valueRead

                    if goAheadToProcessing:
                        if typeOfValues == "bool":
                            returnValue = objRef.process_current_read_state(allok)
                            if returnValue:
                                written_TagsToBeRead = 0
                        elif typeOfValues == "float":
                            returnValue = objRef.process_current_read_state(finalValue)
                            if returnValue:
                                written_TagsToBeRead = 0

                except Exception as e:
                    logBoth('logCritical', IOServer.logSource, f"Encountered exception {e}", Logger.PROBLEM)

                time.sleep(objRef.read_interval)

        self.continuousReadLoop = threading.Thread(name=f'Continuous Read Loop in IOServer',
                                                   target=readLoop,
                                                   args=(), daemon=True)
        self.continuousReadLoop.start()

    def launchWriteTagsLoopThread(self):
        objRef = self

        def writeTagsLoop():
            """Main do loop to take action wherever something required."""
            written_TagsToBeWritten: int = 0
            while not objRef.shutdown:
                tagsToBeWritten = objRef.getCurrentTagsToBeWritten()
                if (
                        objRef.clientForWrites is not None) and objRef.clientForWrites.connected and not objRef.connectionInProgress:
                    if tagsToBeWritten is not None and len(tagsToBeWritten) > 0:
                        if written_TagsToBeWritten == 0:
                            written_TagsToBeWritten += 1
                        if self.machineState.getCurrentState() == MachineState.WRITE_QR_CODE:
                            success, qrCode = readDataInIOServerFromQRCodeServer(self.redisConnectionForWrites)
                            if success:
                                objRef.currentQRCode = qrCode  # Store the QR code for this cycle
                                logBoth('logInfo', IOServer.logSource, f"Received QR Code: {qrCode}", Logger.SUCCESS)
                                objRef.perform_write_state_action(tags=tagsToBeWritten, result=True)
                                # Write rotation settings to PLC based on LHS/RHS
                                objRef.writeRotationSettingsToPLC(qrCode)
                                logBoth('logDebug', IOServer.logSource, f"Transition from state {objRef.machineState.getCurrentState().name}", Logger.GENERAL)
                                objRef.machineState.incrementState()
                                logBoth('logDebug', IOServer.logSource, f"        ...to state {objRef.machineState.getCurrentState().name}", Logger.GENERAL)
                        else:
                            # Capture the WRITE state we are about to act on, BEFORE incrementing
                            stateBeforeWrite = objRef.machineState.getCurrentState()
                            previousMachineState, evaluation = readDataInIOServerFromCameraServer(
                                self.redisConnectionForWrites)
                            if evaluation:
                                objRef.perform_write_state_action(tags=tagsToBeWritten, result=True)
                                # ── Record op-END timestamps for Done-tag-based operations ──
                                if stateBeforeWrite == MachineState.WRITE_RESULT_OF_CHECKING_KNUCKLE:
                                    objRef._recordOpEnd(IOServer.OP_KNUCKLE)
                                elif stateBeforeWrite == MachineState.WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING:
                                    objRef._recordOpEnd(IOServer.OP_HUB_BEARING)
                                elif stateBeforeWrite == MachineState.WRITE_RESULT_OF_CHECKING_TOP_BEARING:
                                    objRef._recordOpEnd(IOServer.OP_TOP_BEARING)
                                elif stateBeforeWrite == MachineState.WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS:
                                    objRef._recordOpEnd(IOServer.OP_NOCAP_BUNK)
                                elif stateBeforeWrite == MachineState.WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER:
                                    objRef._recordOpEnd(IOServer.OP_SPLITPIN)
                                elif stateBeforeWrite == MachineState.WRITE_RESULT_OF_CHECKING_CAP:
                                    objRef._recordOpEnd(IOServer.OP_CAP)
                                logBoth('logDebug', IOServer.logSource, f"Transition from state {objRef.machineState.getCurrentState().name}", Logger.GENERAL)
                                objRef.machineState.incrementState()
                                logBoth('logDebug', IOServer.logSource, f"        ...to state {objRef.machineState.getCurrentState().name}", Logger.GENERAL)
                            else:
                                if previousMachineState != MachineState.INVALID_STATE:
                                    objRef.perform_write_state_action(tags=tagsToBeWritten, result=False)
                                    logBoth('logWarning', IOServer.logSource, f"Did not move ahead from state {objRef.machineState.getCurrentState().name}", Logger.ISSUE)
                                    logBoth('logDebug', IOServer.logSource, f"Transition from state {objRef.machineState.getCurrentState().name}", Logger.GENERAL)
                                    objRef.machineState.decrementState()
                                    logBoth('logDebug', IOServer.logSource, f"        ...to state {objRef.machineState.getCurrentState().name}", Logger.GENERAL)
                time.sleep(objRef.write_loop_interval)

        self.continuousDoLoop = threading.Thread(name=f'Continuous Do Loop in IOServer',
                                                 target=writeTagsLoop,
                                                 args=(), daemon=True)
        self.continuousDoLoop.start()

    def process_current_read_state(self, valueRead: bool | float | None):
        """Process the value read from PLC based on current machine state."""
        if valueRead is None:
            return False

        # printBoldGreen(f"Read value {valueRead}")
        returnValue: bool = False
        currentState = self.machineState.getCurrentState()

        if type(valueRead) == bool:
            if valueRead:
                successfullySent: bool = False
                try:
                    # Step 0: QR Code
                    if currentState == MachineState.READ_QR_CODE:
                        successfullySent = sendDataFromIOServerToQRCodeServer(self.redisConnectionForReads)

                    # Step 1: Knuckle — START of T1
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_KNUCKLE)

                    # Step 2: Hub (HUB_AND_BOTTOM_BEARING state) — START of T2
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_HUB_BEARING)

                    # Step 3: Hub and Second Bearing (TOP_BEARING state) — START of T3
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_TOP_BEARING)

                    # Step 4: Nut and Plate Washer — START of T4
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_NUT_WASHER)

                    # Step 5: Tightening Torque 1 Done
                    elif currentState == MachineState.READ_TIGHTENING_TORQUE_1_DONE:
                        successfullySent = True

                    # Step 6: Free Rotations Done — END of T4
                    elif currentState == MachineState.READ_FREE_ROTATIONS_DONE:
                        successfullySent = sendDataFromIOServerToFEServer(self.redisConnectionForReads,
                                                                          currentMachineState=MachineState.READ_FREE_ROTATIONS_DONE)
                        if successfullySent:
                            self._recordOpEnd(IOServer.OP_NUT_WASHER)
                        # Reset Station 3 tags - prepare for eventual use in State 29
                        updateRequest: dict = {
                            "sleepTimeForDelay": TIME_WAIT_BEFORE_RESETTING_TORQUE3_VALUES_AFTER_READING_THEM,
                            "tag1": {"tag": IOServer.PLC_PC_Station3TorqueValueSet, "type": "bool", "value": False},
                            "tag2": {"tag": IOServer.PLC_PC_Station3TorqueValue, "type": "float", "value": 0.0},
                        }
                        logBoth('logDebug', IOServer.logSource, f"Sending request to UpdateTagsProcessor: Station 3 reset after free rotations", Logger.GENERAL)
                        addTagUpdateRequest(updateRequest)
                        # Step 7: Bunk for Component Press — START of T5 and T6
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_NOCAP_BUNK)
                            self._recordOpStart(IOServer.OP_TORQUE2)

                    # Step 8: Component Press Done
                    elif currentState == MachineState.READ_COMPONENT_PRESS_DONE:
                        successfullySent = sendDataFromIOServerToFEServer(self.redisConnectionForReads,
                                                                          currentMachineState=MachineState.READ_COMPONENT_PRESS_DONE)

                    # Step 9: No Bunk
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK)

                    # Step 10: Tightening Torque 2 Done — END of T6
                    elif currentState == MachineState.READ_TIGHTENING_TORQUE_2_DONE:
                        successfullySent = True
                        self._recordOpEnd(IOServer.OP_TORQUE2)

                    # Step 11: Split Pin and Washer — START of T7
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_SPLITPIN)

                    # Step 12: Cap — START of T8
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_CAP)

                    # Step 13: Bunk for Cap Press — START of T9
                    elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS:
                        successfullySent = sendDataFromIOServerToCameraServer(self.redisConnectionForReads,
                                                                              currentMachineState=MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS)
                        if successfullySent:
                            self._recordOpStart(IOServer.OP_BUNK_CAP_PRESS)

                    # Step 14: Cap Press Done
                    elif currentState == MachineState.READ_CAP_PRESS_DONE:
                        successfullySent = sendDataFromIOServerToFEServer(self.redisConnectionForReads,
                                                                          currentMachineState=MachineState.READ_CAP_PRESS_DONE)

                    # Step 15: Free Rotation Torque 1 Done — END of T9
                    elif currentState == MachineState.READ_FREE_ROTATION_TORQUE_1_DONE:
                        successfullySent = True
                        self._recordOpEnd(IOServer.OP_BUNK_CAP_PRESS)

                    if successfullySent:
                        logBoth('logDebug', IOServer.logSource, f"Transition from state {self.machineState.getCurrentState().name}", Logger.GENERAL)
                        self.machineState.incrementState()
                        logBoth('logDebug', IOServer.logSource, f"        ...to state {self.machineState.getCurrentState().name}", Logger.GENERAL)

                except Exception as e:
                    logBoth('logCritical', IOServer.logSource, f"Exception {e} encountered in current_read_state - 1", Logger.PROBLEM)

                returnValue = valueRead
            else:
                returnValue = valueRead

        elif type(valueRead) == float:
            if valueRead == IOServer.FALSE_FLOAT_VALUE:
                logBoth('logDebug', IOServer.logSource, f"Failed to read proper value of float in state {self.machineState.getCurrentState().name}", Logger.GENERAL)
                returnValue = False
            else:
                successfullySent: bool = False
                try:
                    # Step 5B: Tightening Torque 1 Value
                    if currentState == MachineState.READ_TIGHTENING_TORQUE_1:
                        logBoth('logInfo', IOServer.logSource, f"Read Station 2 Torque Value (1st time): {valueRead}", Logger.SUCCESS)
                        successfullySent = sendDataFromIOServerToFEServer(self.redisConnectionForReads,
                                                                          currentMachineState=MachineState.READ_TIGHTENING_TORQUE_1,
                                                                          value=valueRead)
                        # Reset Station 2 torque tags after reading (so Step 10 doesn't auto-trigger)
                        if successfullySent:
                            updateRequest : dict = {
                                "sleepTimeForDelay": TIME_WAIT_BEFORE_RESETTING_TORQUE2_VALUES_AFTER_READING_THEM,  # Seconds to wait before writing tags
                                "tag1": {"tag": IOServer.PLC_PC_Station2TorqueValueSet, "type": "bool", "value": False},
                                "tag2": {"tag": IOServer.PLC_PC_Station2TorqueValue, "type": "float", "value": 0.0},
                            }
                            logBoth('logDebug', IOServer.logSource, f"Sending request to UpdateTagsProcessor: Station 2 reset after torque 1", Logger.GENERAL)
                            addTagUpdateRequest(updateRequest)
                            # Transition to next state after successfully reading torque
                            logBoth('logDebug', IOServer.logSource, f"Transition from state {self.machineState.getCurrentState().name}", Logger.GENERAL)
                            self.machineState.incrementState()
                            logBoth('logDebug', IOServer.logSource, f"        ...to state {self.machineState.getCurrentState().name}", Logger.GENERAL)
                    # Step 10B: Tightening Torque 2 Value
                    elif currentState == MachineState.READ_TIGHTENING_TORQUE_2:
                        logBoth('logInfo', IOServer.logSource, f"Read Station 2 Torque Value (2nd time): {valueRead}", Logger.SUCCESS)
                        successfullySent = sendDataFromIOServerToFEServer(self.redisConnectionForReads,
                                                                          currentMachineState=MachineState.READ_TIGHTENING_TORQUE_2,
                                                                          value=valueRead)
                        if successfullySent:
                            updateRequest : dict = {
                                "sleepTimeForDelay": TIME_WAIT_BEFORE_RESETTING_TORQUE2_VALUES_AFTER_READING_THEM,  # Seconds to wait before writing tags
                                "tag1": {"tag": IOServer.PLC_PC_Station2TorqueValueSet, "type": "bool", "value": False},
                                "tag2": {"tag": IOServer.PLC_PC_Station2TorqueValue, "type": "float", "value": 0.0},
                            }
                            logBoth('logDebug', IOServer.logSource, f"Sending request to UpdateTagsProcessor: Station 2 reset after torque 2", Logger.GENERAL)
                            addTagUpdateRequest(updateRequest)
                            # Transition to next state after successfully reading torque
                            logBoth('logDebug', IOServer.logSource, f"Transition from state {self.machineState.getCurrentState().name}", Logger.GENERAL)
                            self.machineState.incrementState()
                            logBoth('logDebug', IOServer.logSource, f"        ...to state {self.machineState.getCurrentState().name}", Logger.GENERAL)

                    # Step 15B: Free Rotation Torque 1 Value - FINAL STATE — END of T9
                    elif currentState == MachineState.READ_FREE_ROTATION_TORQUE_1:
                        logBoth('logInfo', IOServer.logSource, f"Read Station 3 Torque Value: {valueRead}", Logger.SUCCESS)
                        successfullySent = sendDataFromIOServerToFEServer(self.redisConnectionForReads,
                                                                          currentMachineState=MachineState.READ_FREE_ROTATION_TORQUE_1,
                                                                          value=valueRead,
                                                                          moveToState=MachineState.READ_QR_CODE,
                                                                          action=moveAheadToNextComponent)
                        if successfullySent:
                            updateRequest: dict = {
                                "sleepTimeForDelay": TIME_WAIT_BEFORE_RESETTING_TORQUE3_VALUES_AFTER_READING_THEM,
                                # Seconds to wait before writing tags
                                "tag1": {"tag": IOServer.PLC_PC_Station3TorqueValueSet, "type": "bool", "value": False},
                                "tag2": {"tag": IOServer.PLC_PC_Station3TorqueValue, "type": "float", "value": 0.0},
                            }
                            logBoth('logDebug', IOServer.logSource, f"Sending request to UpdateTagsProcessor: Station 3 reset after free rotation torque", Logger.GENERAL)
                            addTagUpdateRequest(updateRequest)
                            logBoth('logDebug', IOServer.logSource, f"Transition from state {self.machineState.getCurrentState().name}", Logger.GENERAL)
                            self.machineState.incrementState()
                            logBoth('logDebug', IOServer.logSource, f"        ...to state {self.machineState.getCurrentState().name}", Logger.GENERAL)

                except Exception as e:
                    logBoth('logCritical', IOServer.logSource, f"Exception {e} encountered in current_read_state - 3", Logger.PROBLEM)

                returnValue = successfullySent

        if self.machineState.getCurrentState() == MachineState.READ_QR_CODE:
            # Cycle just completed: compute and log machine times, then reset for next cycle
            if self._cycleInProgress:
                self._computeAndLogCycleTimes()
                self._resetOpTimestamps()
            self.resetAll()
            self.write_bool(IOServer.PLC_PC_CheckQRCode, True)

        return returnValue

    def perform_write_state_action(self, tags: list[str], result: bool = True) -> bool:
        """Perform the write action to PLC tags."""
        logBoth('logDebug', IOServer.logSource, "Entered perform_write_state_action()", Logger.GENERAL)
        success1 = self.write_bool(tags[0], result)
        logBoth('logDebug', IOServer.logSource, f"Wrote {result} to {tags[0]}", Logger.GENERAL)
        time.sleep(IOServer.PLC_SLEEPTIME_BETWEEN_OK_AND_DONE)
        success2 = self.write_bool(tags[1], True)
        logBoth('logDebug', IOServer.logSource, f"Wrote True to {tags[1]}", Logger.GENERAL)

        if success1 and success2:
            self.logger.info(f"Performed action for, and wrote to tags {tags}")
        else:
            self.logger.info(f"Could not write to tags {tags}")
            logBoth('logWarning', IOServer.logSource, f"Could not write to tags {tags}", Logger.ISSUE)

        return result

    def startThreads(self):
        """Start the read and connection check threads."""
        global _updateTagsProcessor

        logBoth('logInfo', IOServer.logSource, "Starting read, connection, and do threads in IO Server", Logger.GENERAL)

        self.launchConnectionMonitoringThread()
        logBoth('logInfo', IOServer.logSource, "Started connection monitoring thread in IOServer", Logger.SUCCESS)

        self.launchReadLoopThread()
        logBoth('logInfo', IOServer.logSource, "Started read loop thread in IOServer", Logger.SUCCESS)

        self.launchWriteTagsLoopThread()
        logBoth('logInfo', IOServer.logSource, "Started do loop thread in IOServer", Logger.SUCCESS)

        self.launchHeartbeatThread()
        logBoth('logInfo', IOServer.logSource, "Started heartbeat thread in IOServer", Logger.SUCCESS)

        self.launchEmergencyMonitoringThread()
        logBoth('logInfo', IOServer.logSource, "Started emergency monitoring thread in IOServer", Logger.SUCCESS)

        self.launchMonitorStopCommandThread()
        logBoth('logInfo', IOServer.logSource, "Started monitorStop thread in IOServer", Logger.SUCCESS)

        self.launchThreadForUpdatingCombinedHeartbeat()
        logBoth('logInfo', IOServer.logSource, "Started combinedHeartbeat update thread in IOServer", Logger.SUCCESS)

        self.launchTagRequestListenerThread()
        logBoth('logInfo', IOServer.logSource, "Started tag request listener thread in IOServer", Logger.SUCCESS)

        # Start UpdateTagsToDefaultProcessor
        self.updateTagsProcessor = UpdateTagsToDefaultProcessor(ioServerInstance=self)
        self.updateTagsProcessor.start()
        _updateTagsProcessor = self.updateTagsProcessor  # Set global reference
        logBoth('logInfo', IOServer.logSource, "Started UpdateTagsToDefaultProcessor thread in IOServer", Logger.SUCCESS)

        logBoth('logInfo', IOServer.logSource, "Started read tag, connection monitoring, write tag and update tag threads", Logger.SUCCESS)

    # ==================== Read functions ====================

    def read_bool(self, tag: str, expected_value: bool = True, debug: bool = False) -> Optional[bool]:
        """Read a boolean tag from the PLC."""
        if tag is None or tag == "":
            return False
        if (self.clientForReads is None) or (not self.clientForReads.connected):
            return False
        try:
            value: bool = False
            with self.readingLock:
                value = self.clientForReads.read(tag).value
            if value is None:
                self.logger.error("Error reading bool tag %s", tag)
                logBoth('logWarning', IOServer.logSource, f"Error reading bool tag {tag}", Logger.ISSUE)
                return not expected_value
            if debug and value == expected_value:
                self.logger.info("Read bool tag %s: %s", tag, value)
            return value
        except Exception as e:
            self.logger.error("Error reading bool tag %s: %s", tag, e)
            logBoth('logWarning', IOServer.logSource, f"Error reading bool tag {tag}: {e}", Logger.ISSUE)
            return not expected_value

    def read_float(self, tag: str, debug: bool = False) -> Optional[float]:
        """Read a float tag from the PLC."""
        if tag is None or tag == "":
            return IOServer.FALSE_FLOAT_VALUE
        if (self.clientForReads is None) or (not self.clientForReads.connected):
            return IOServer.FALSE_FLOAT_VALUE
        try:
            value: float = IOServer.FALSE_FLOAT_VALUE
            with self.readingLock:
                value = self.clientForReads.read(tag).value
            if value is None:
                logBoth('logWarning', IOServer.logSource, f"Error reading float tag {tag}", Logger.ISSUE)
                return IOServer.FALSE_FLOAT_VALUE
            return value
        except Exception as e:
            logBoth('logWarning', IOServer.logSource, f"Error reading float tag {tag}: {e}", Logger.ISSUE)
            return IOServer.FALSE_FLOAT_VALUE

    def read_int(self, tag: str, debug: bool = False) -> Optional[int]:
        """Read an integer tag from the PLC."""
        if tag is None or tag == "":
            return IOServer.FALSE_INT_VALUE
        if (self.clientForReads is None) or (not self.clientForReads.connected):
            return IOServer.FALSE_INT_VALUE
        try:
            value: int = IOServer.FALSE_INT_VALUE
            with self.readingLock:
                value = self.clientForReads.read(tag).value
            if value is None:
                self.logger.error("Error reading integer tag %s: value is None", tag)
                logBoth('logWarning', IOServer.logSource, f"Error reading integer tag {tag}: value is None", Logger.ISSUE)
                return IOServer.FALSE_INT_VALUE
            if debug:
                self.logger.info("Read integer tag %s: %d", tag, value)
                logBoth('logInfo', IOServer.logSource, f"Read integer tag {tag}: {value}", Logger.GENERAL)
                return int(value)
        except Exception as e:
            self.logger.error("Error reading integer tag %s: %s", tag, e)
            logBoth('logWarning', IOServer.logSource, f"Error reading integer tag {tag}: {e}", Logger.ISSUE)
            return IOServer.FALSE_INT_VALUE

    def read_single(self, aTag: str) -> Any:
        if aTag is None or aTag == "":
            return IOServer.FALSE_FLOAT_VALUE
        if (self.clientForReads is None) or (not self.clientForReads.connected):
            return IOServer.FALSE_FLOAT_VALUE
        value = ""
        try:
            with self.readingLock:
                value = self.clientForReads.read(aTag).value
        except:
            pass
        return value

    def read_multiple(self, listOfTags: list) -> Any:
        if listOfTags is None or len(listOfTags) == 0:
            return None
        if (self.clientForReads is None) or (not self.clientForReads.connected):
            return None
        value = []
        try:
            with self.readingLock:
                value = self.clientForReads.read(*listOfTags)
        except:
            pass
        return value

    def read_array(self, arrayName: str, numberOfElements: int) -> Any:
        if numberOfElements == 0:
            return None
        if (self.clientForReads is None) or (not self.clientForReads.connected):
            return None
        value = []
        try:
            with self.readingLock:
                value = self.clientForReads.read(f"{arrayName}" + "{" + f"{numberOfElements}" + "}")
        except:
            pass
        return value

    def read_array_slice(self, arrayName: str, index: int, numberOfElements: int) -> Any:
        value = []
        try:
            with self.readingLock:
                value = self.clientForReads.read(f"{arrayName}[{index}]" + "{" + f"{numberOfElements}" + "}")
        except:
            pass
        return value

    # ==================== Write functions ====================

    def write_bool(self, tag: str, value: bool, debug: bool = True) -> bool:
        """Write a boolean to a tag to the PLC."""
        if tag is None:
            return False
        if (self.clientForWrites is None) or (not self.clientForWrites.connected):
            return False
        try:
            with self.writingLock:
                self.clientForWrites.write(tag, value)
            if debug:
                logBoth('logDebug', IOServer.logSource, f"Wrote to bool tag {tag}: {value} in write_bool()", Logger.GENERAL)
            return True
        except Exception as e:
            logBoth('logWarning', IOServer.logSource, f"Error writing bool tag {tag}: {e}", Logger.ISSUE)
            return False

    def write_float(self, tag: str, value: float, debug: bool = True) -> bool:
        """Write a float to a tag to the PLC."""
        if tag is None:
            return False
        if (self.clientForWrites is None) or (not self.clientForWrites.connected):
            return False
        try:
            with self.writingLock:
                self.clientForWrites.write(tag, value)
            if debug:
                self.logger.info(f"Wrote float tag {tag}: {value}")
                logBoth('logDebug', IOServer.logSource, f"Wrote to float tag {tag}: {value} in write_float()", Logger.GENERAL)
            return True
        except Exception as e:
            self.logger.error(f"Error writing float tag {tag}: {e}")
            logBoth('logWarning', IOServer.logSource, f"Error writing float tag {tag}: {e}", Logger.ISSUE)
            return False

    def write_int(self, tag: str, value: int, debug: bool = False) -> bool:
        """Write an integer to a tag to the PLC."""
        if tag is None or not isinstance(value, int):
            if debug:
                self.logger.error(f"Invalid input for tag {tag}: value {value} must be an integer")
                logBoth('logWarning', IOServer.logSource, f"Invalid input for tag {tag}: value {value} must be an integer", Logger.ISSUE)
            return False
        if (self.clientForWrites is None) or (not self.clientForWrites.connected):
            return False
        try:
            with self.writingLock:
                self.clientForWrites.write(tag, value)
            if debug:
                self.logger.info(f"Wrote integer tag {tag}: {value}")
                logBoth('logDebug', IOServer.logSource, f"Wrote integer tag {tag}: {value}", Logger.GENERAL)
            return True
        except Exception as e:
            self.logger.error(f"Error writing integer tag {tag}: {e}")
            logBoth('logWarning', IOServer.logSource, f"Error writing integer tag {tag}: {e}", Logger.ISSUE)
            return False

    def resetTagToFalse(self, tag: str, debug: bool = False) -> bool:
        """Reset a tag to False."""
        return self.write_bool(tag=tag, value=False, debug=debug)

    def resetTagToZero(self, tag: str, debug: bool = False) -> bool:
        """Reset a tag to 0.0."""
        return self.write_float(tag=tag, value=0.0, debug=debug)

    def resetAll(self, debug: bool = False) -> bool:
        """Reset all tags to False if bool, or to 0.0 if float."""

        # Reset current QR Code
        self.currentQRCode = ""

        # Step 0: QR Code
        self.resetTagToFalse(IOServer.PLC_PC_CheckQRCode)
        self.resetTagToFalse(IOServer.PC_PLC_QRCodeCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_QRCodeCheckDone)

        # Step 1: Knuckle
        self.resetTagToFalse(IOServer.PLC_PC_CheckKnuckle)
        self.resetTagToFalse(IOServer.PC_PLC_KnuckleCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_KnuckleCheckDone)

        # Step 2: Hub
        self.resetTagToFalse(IOServer.PLC_PC_CheckHub)
        self.resetTagToFalse(IOServer.PC_PLC_HubCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_HubCheckDone)

        # Step 3: Hub and Second Bearing
        self.resetTagToFalse(IOServer.PLC_PC_CheckHubAndSecondBearing)
        self.resetTagToFalse(IOServer.PC_PLC_HubAndSecondBearingCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_HubAndSecondBearingCheckDone)

        # Step 4: Nut and Plate Washer
        self.resetTagToFalse(IOServer.PLC_PC_CheckNutAndPlateWasher)
        self.resetTagToFalse(IOServer.PC_PLC_NutAndPlateWasherCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_NutAndPlateWasherCheckDone)

        # Step 5 & 10: Station 2 Torque
        self.resetTagToFalse(IOServer.PLC_PC_Station2TorqueValueSet)
        self.resetTagToZero(IOServer.PLC_PC_Station2TorqueValue)

        # Step 6: Station 3 Rotation Done
        self.resetTagToFalse(IOServer.PLC_PC_Station3RotationDone)

        # Step 7: No Cap Bunk
        self.resetTagToFalse(IOServer.PLC_PC_CheckNoCapBunk)
        self.resetTagToFalse(IOServer.PC_PLC_NoCapBunkCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_NoCapBunkCheckDone)

        # Step 8: Component Press Done
        self.resetTagToFalse(IOServer.PLC_PC_ComponentPressDone)

        # Step 9: No Bunk
        self.resetTagToFalse(IOServer.PLC_PC_CheckNoBunk)
        self.resetTagToFalse(IOServer.PC_PLC_NoBunkCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_NoBunkCheckDone)

        # Step 11: Split Pin and Washer
        self.resetTagToFalse(IOServer.PLC_PC_CheckSplitPinAndWasher)
        self.resetTagToFalse(IOServer.PC_PLC_SplitPinAndWasherCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_SplitPinAndWasherCheckDone)

        # Step 12: Cap
        self.resetTagToFalse(IOServer.PLC_PC_CheckCap)
        self.resetTagToFalse(IOServer.PC_PLP_CapCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_CapCheckDone)

        # Step 13: Bunk (used for both bunk checks)
        self.resetTagToFalse(IOServer.PLC_PC_CheckBunk)
        self.resetTagToFalse(IOServer.PC_PLC_BunkCheckOK)
        self.resetTagToFalse(IOServer.PC_PLC_BunkCheckDone)

        # Step 14: Cap Press Done
        self.resetTagToFalse(IOServer.PLC_PC_CapPressDone)

        # Step 15: Station 3 Torque
        self.resetTagToFalse(IOServer.PLC_PC_Station3TorqueValueSet)
        self.resetTagToZero(IOServer.PLC_PC_Station3TorqueValue)

        # Emergency Abort
        self.resetTagToFalse(IOServer.PLC_PC_EmergencyAbort)

    def getCurrentQRCode(self) -> str:
        """Get the current QR code for this cycle."""
        return self.currentQRCode

    def get_tag_address(self, tag: str) -> int:
        """Placeholder for mapping tags to addresses (not needed for pycomm3)."""
        return 0

    def find_pids(self):
        pid_tags = [
            tag
            for tag, _def in self.clientForReads.tags.items()
            if _def['data_type_name'] == 'PID'
        ]
        return pid_tags

    def find_attributes(self):
        for typ in self.clientForReads.data_types:
            with self.readingLock:
                logBoth('logDebug', IOServer.logSource, f'{typ} attributes: {self.clientForReads.data_types[typ]["attributes"]}', Logger.GENERAL)

    def getAllTagValues(self) -> dict:
        """Read all PLC tags and return as a dictionary."""
        if self.clientForReads is None or not self.clientForReads.connected:
            return {}

        tag_values = {}

        # Step 0: QR Code
        tag_values[IOServer.PLC_PC_CheckQRCode] = self.read_bool(IOServer.PLC_PC_CheckQRCode, debug=False)
        tag_values[IOServer.PC_PLC_QRCodeCheckOK] = self.read_bool(IOServer.PC_PLC_QRCodeCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_QRCodeCheckDone] = self.read_bool(IOServer.PC_PLC_QRCodeCheckDone, debug=False)

        # Step 1: Knuckle
        tag_values[IOServer.PLC_PC_CheckKnuckle] = self.read_bool(IOServer.PLC_PC_CheckKnuckle, debug=False)
        tag_values[IOServer.PC_PLC_KnuckleCheckOK] = self.read_bool(IOServer.PC_PLC_KnuckleCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_KnuckleCheckDone] = self.read_bool(IOServer.PC_PLC_KnuckleCheckDone, debug=False)

        # Step 2: Hub
        tag_values[IOServer.PLC_PC_CheckHub] = self.read_bool(IOServer.PLC_PC_CheckHub, debug=False)
        tag_values[IOServer.PC_PLC_HubCheckOK] = self.read_bool(IOServer.PC_PLC_HubCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_HubCheckDone] = self.read_bool(IOServer.PC_PLC_HubCheckDone, debug=False)

        # Step 3: Hub and Second Bearing
        tag_values[IOServer.PLC_PC_CheckHubAndSecondBearing] = self.read_bool(IOServer.PLC_PC_CheckHubAndSecondBearing,
                                                                              debug=False)
        tag_values[IOServer.PC_PLC_HubAndSecondBearingCheckOK] = self.read_bool(
            IOServer.PC_PLC_HubAndSecondBearingCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_HubAndSecondBearingCheckDone] = self.read_bool(
            IOServer.PC_PLC_HubAndSecondBearingCheckDone, debug=False)

        # Step 4: Nut and Plate Washer
        tag_values[IOServer.PLC_PC_CheckNutAndPlateWasher] = self.read_bool(IOServer.PLC_PC_CheckNutAndPlateWasher,
                                                                            debug=False)
        tag_values[IOServer.PC_PLC_NutAndPlateWasherCheckOK] = self.read_bool(IOServer.PC_PLC_NutAndPlateWasherCheckOK,
                                                                              debug=False)
        tag_values[IOServer.PC_PLC_NutAndPlateWasherCheckDone] = self.read_bool(
            IOServer.PC_PLC_NutAndPlateWasherCheckDone, debug=False)

        # Step 5 & 10: Station 2 Torque
        tag_values[IOServer.PLC_PC_Station2TorqueValueSet] = self.read_bool(IOServer.PLC_PC_Station2TorqueValueSet,
                                                                            debug=False)
        tag_values[IOServer.PLC_PC_Station2TorqueValue] = self.read_float(IOServer.PLC_PC_Station2TorqueValue,
                                                                          debug=False)

        # Step 6: Station 3 Rotation Done
        tag_values[IOServer.PLC_PC_Station3RotationDone] = self.read_bool(IOServer.PLC_PC_Station3RotationDone,
                                                                          debug=False)

        # Step 7: No Cap Bunk
        tag_values[IOServer.PLC_PC_CheckNoCapBunk] = self.read_bool(IOServer.PLC_PC_CheckNoCapBunk, debug=False)
        tag_values[IOServer.PC_PLC_NoCapBunkCheckOK] = self.read_bool(IOServer.PC_PLC_NoCapBunkCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_NoCapBunkCheckDone] = self.read_bool(IOServer.PC_PLC_NoCapBunkCheckDone, debug=False)

        # Step 8: Component Press Done
        tag_values[IOServer.PLC_PC_ComponentPressDone] = self.read_bool(IOServer.PLC_PC_ComponentPressDone, debug=False)

        # Step 9: No Bunk
        tag_values[IOServer.PLC_PC_CheckNoBunk] = self.read_bool(IOServer.PLC_PC_CheckNoBunk, debug=False)
        tag_values[IOServer.PC_PLC_NoBunkCheckOK] = self.read_bool(IOServer.PC_PLC_NoBunkCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_NoBunkCheckDone] = self.read_bool(IOServer.PC_PLC_NoBunkCheckDone, debug=False)

        # Step 11: Split Pin and Washer
        tag_values[IOServer.PLC_PC_CheckSplitPinAndWasher] = self.read_bool(IOServer.PLC_PC_CheckSplitPinAndWasher,
                                                                            debug=False)
        tag_values[IOServer.PC_PLC_SplitPinAndWasherCheckOK] = self.read_bool(IOServer.PC_PLC_SplitPinAndWasherCheckOK,
                                                                              debug=False)
        tag_values[IOServer.PC_PLC_SplitPinAndWasherCheckDone] = self.read_bool(
            IOServer.PC_PLC_SplitPinAndWasherCheckDone, debug=False)

        # Step 12: Cap
        tag_values[IOServer.PLC_PC_CheckCap] = self.read_bool(IOServer.PLC_PC_CheckCap, debug=False)
        tag_values[IOServer.PC_PLP_CapCheckOK] = self.read_bool(IOServer.PC_PLP_CapCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_CapCheckDone] = self.read_bool(IOServer.PC_PLC_CapCheckDone, debug=False)

        # Step 13: Bunk
        tag_values[IOServer.PLC_PC_CheckBunk] = self.read_bool(IOServer.PLC_PC_CheckBunk, debug=False)
        tag_values[IOServer.PC_PLC_BunkCheckOK] = self.read_bool(IOServer.PC_PLC_BunkCheckOK, debug=False)
        tag_values[IOServer.PC_PLC_BunkCheckDone] = self.read_bool(IOServer.PC_PLC_BunkCheckDone, debug=False)

        # Step 14: Cap Press Done
        tag_values[IOServer.PLC_PC_CapPressDone] = self.read_bool(IOServer.PLC_PC_CapPressDone, debug=False)

        # Step 15: Station 3 Torque
        tag_values[IOServer.PLC_PC_Station3TorqueValueSet] = self.read_bool(IOServer.PLC_PC_Station3TorqueValueSet,
                                                                            debug=False)
        tag_values[IOServer.PLC_PC_Station3TorqueValue] = self.read_float(IOServer.PLC_PC_Station3TorqueValue,
                                                                          debug=False)

        # System tags
        tag_values[IOServer.PLC_PC_EmergencyAbort] = self.read_bool(IOServer.PLC_PC_EmergencyAbort, debug=False)
        tag_values[IOServer.PLC_PC_WatchTag] = self.read_int(IOServer.PLC_PC_WatchTag, debug=False)

        # Add current machine state
        tag_values["_currentMachineState"] = str(self.machineState.getCurrentState())

        return tag_values

    def launchTagRequestListenerThread(self):
        """Launch thread that listens for tag publish requests on Redis queue."""
        import json
        objRef = self

        PUBLISH_TAGS_QUEUE = "publishTags"
        RECEIVE_TAGS_QUEUE = "receiveTags"

        def listenForTagRequests():
            while not objRef.shutdown:
                try:
                    # Check for request in publishTags queue (blocking with 1 sec timeout)
                    result = objRef.redisConnectionForReads.blpop(PUBLISH_TAGS_QUEUE, timeout=1)

                    if result:
                        # Got a request - clear any remaining messages in the queue
                        while objRef.redisConnectionForReads.lpop(PUBLISH_TAGS_QUEUE):
                            pass

                        # Fetch all tag values
                        tag_values = objRef.getAllTagValues()

                        # Put response in receiveTags queue
                        objRef.redisConnectionForReads.rpush(RECEIVE_TAGS_QUEUE, json.dumps(tag_values))

                except Exception as e:
                    pass  # Silently ignore errors to not disrupt main operation

        self.tagRequestThread = threading.Thread(name='Tag Request Listener Thread',
                                                 target=listenForTagRequests,
                                                 args=(), daemon=True)
        self.tagRequestThread.start()

    def __del__(self):
        """Cleanup on object destruction."""
        self.shutdown = True
        # Stop the UpdateTagsToDefaultProcessor
        if hasattr(self, 'updateTagsProcessor') and self.updateTagsProcessor is not None:
            try:
                self.updateTagsProcessor.stop()
            except:
                pass
        if self.clientForReads and self.clientForReads.connected:
            try:
                self.clientForReads.close()
            except:
                pass
            try:
                self.clientForWrites.close()
            except:
                pass
        logBoth('logInfo', IOServer.logSource, f"IOServer shutdown", Logger.CRITICAL)


# *********************************************************************

def startIOServer(mode : str = "TEST"):
    io = IOServer(mode = mode)
    logBoth('logCritical', IOServer.logSource, "*****************", Logger.SUCCESS)
    logBoth('logCritical', IOServer.logSource, "Started IO Server", Logger.SUCCESS)
    logBoth('logCritical', IOServer.logSource, "*****************", Logger.SUCCESS)
    io.heartbeatThread.join()
    io.monitorStopThread.join()
    sys.exit(0)


# *********************************************************************

# if __name__ == "__main__":
#     startIOServer()