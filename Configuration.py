# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

import pathlib
import platform
import threading
from pyjavaproperties import Properties
import BaseUtils
from BaseUtils import *
from utils.CosThetaColors import *
from collections.abc import MutableMapping
import numpy as np
import json
from typing import Optional, Any, List, Tuple
import time as _time

# ***********************************

configFilePath = str(BaseUtils.get_project_root()) + '/ApplicationConfiguration.properties'

# ***********************************

class CosThetaConfigurator():
    """
    Singleton configuration manager for CosTheta applications.

    This class handles loading and accessing configuration properties from
    ApplicationConfiguration.properties file. It provides platform detection,
    configuration validation, and type-safe access to all configuration values.

    Usage:
        config = CosThetaConfigurator.getInstance()
        value = config.getSomeProperty()
    """

    _RELOAD_CHECK_INTERVAL_SECS: float = 5.0
    _lastReloadCheckTime: float = 0.0

    # ***********************************

    __singleton_lock = threading.Lock()
    __singleton_instance: Optional['CosThetaConfigurator'] = None

    isWindowsOS: bool = True
    isUnixOS: bool = False
    isMacOS: bool = False
    osPopulated: bool = False

    # Configuration state
    _configs = Properties()
    _loaded: bool = False
    _reloaded: bool = True
    _lastTimeLoaded: Optional[float] = None
    integrityIsOk: Optional[bool] = None

    # =============================================================================
    # SINGLETON AND INITIALIZATION METHODS
    # =============================================================================

    @classmethod
    def __init__(cls):
        """Initialize the singleton instance."""
        print(CosThetaColors.CGREEN, end="")
        print(CosThetaColors.CBOLD, end="")
        print(CosThetaColors.CEND)
        CosThetaConfigurator.populatePlatform()
        CosThetaConfigurator._loadConfig()
        if CosThetaConfigurator.__singleton_instance is not None:
            raise Exception(
                f"{getFullyQualifiedName(__file__, cls)} is a singleton class! "
                f"It should be accessed via {getFullyQualifiedName(__file__, cls)}.getInstance()")

    @staticmethod
    def getInstance() -> 'CosThetaConfigurator':
        """
        Get the singleton instance of CosThetaConfigurator.

        Returns:
            CosThetaConfigurator: The singleton instance
        """
        if not CosThetaConfigurator.__singleton_instance:
            with CosThetaConfigurator.__singleton_lock:
                if not CosThetaConfigurator.__singleton_instance:
                    CosThetaConfigurator.__singleton_instance = CosThetaConfigurator()
                    CosThetaConfigurator.__singleton_instance.checkIntegrity()
        return CosThetaConfigurator.__singleton_instance

    # =============================================================================
    # PLATFORM DETECTION METHODS
    # =============================================================================

    @classmethod
    def populatePlatform(cls) -> None:
        """Detect and cache the current operating system platform."""
        if not CosThetaConfigurator.osPopulated:
            currentPlatform = platform.system().lower()

            if currentPlatform and (('windows' in currentPlatform) or ('nt' in currentPlatform)):
                CosThetaConfigurator.isWindowsOS = True
                CosThetaConfigurator.isUnixOS = False
                CosThetaConfigurator.isMacOS = False
            elif currentPlatform and 'darwin' in currentPlatform:
                CosThetaConfigurator.isWindowsOS = False
                CosThetaConfigurator.isUnixOS = False
                CosThetaConfigurator.isMacOS = True
            elif currentPlatform:
                CosThetaConfigurator.isWindowsOS = False
                CosThetaConfigurator.isUnixOS = True
                CosThetaConfigurator.isMacOS = False

            CosThetaConfigurator.osPopulated = True

    @classmethod
    def isWindows(cls) -> bool:
        """Check if running on Windows OS."""
        CosThetaConfigurator.populatePlatform()
        return CosThetaConfigurator.isWindowsOS

    @classmethod
    def isUnix(cls) -> bool:
        """Check if running on Unix/Linux OS."""
        CosThetaConfigurator.populatePlatform()
        return CosThetaConfigurator.isUnixOS

    @classmethod
    def isLinux(cls) -> bool:
        """Check if running on Linux OS (alias for isUnix)."""
        CosThetaConfigurator.populatePlatform()
        return CosThetaConfigurator.isUnixOS

    @classmethod
    def isMac(cls) -> bool:
        """Check if running on macOS."""
        CosThetaConfigurator.populatePlatform()
        return CosThetaConfigurator.isMacOS

    # =============================================================================
    # CONFIGURATION LOADING METHODS
    # =============================================================================

    @classmethod
    def _loadConfig(cls) -> None:
        """Load or reload the configuration file if needed."""
        if not CosThetaConfigurator._loaded:
            try:
                with open(configFilePath, 'r') as config_file:
                    CosThetaConfigurator._configs.load(config_file)
                    CosThetaConfigurator._loaded = True
                    CosThetaConfigurator._lastTimeLoaded = pathlib.Path(configFilePath).stat().st_mtime
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
            CosThetaConfigurator._reloaded = False
        else:
            now = _time.monotonic()
            if (now - CosThetaConfigurator._lastReloadCheckTime) < cls._RELOAD_CHECK_INTERVAL_SECS:
                CosThetaConfigurator._reloaded = False
                return  # skip the stat entirely
            try:
                lastUpdatedTime = pathlib.Path(configFilePath).stat().st_mtime
                if lastUpdatedTime > CosThetaConfigurator._lastTimeLoaded:
                    with open(configFilePath, 'r') as config_file:
                        CosThetaConfigurator._configs.load(config_file)
                    CosThetaConfigurator._lastTimeLoaded = lastUpdatedTime
                    CosThetaConfigurator._reloaded = True
                else:
                    CosThetaConfigurator._reloaded = False
            except Exception as e:
                CosThetaConfigurator._reloaded = False

    @classmethod
    def _getReloaded(cls) -> bool:
        """Check if configuration was recently reloaded."""
        return CosThetaConfigurator._reloaded

    @classmethod
    def _getLoaded(cls) -> bool:
        """Check if configuration has been loaded."""
        return CosThetaConfigurator._loaded

    @classmethod
    def getLastTimeLoaded(cls) -> Optional[float]:
        """Get the timestamp when configuration was last loaded."""
        return CosThetaConfigurator._lastTimeLoaded

    @classmethod
    def _getConfig(cls) -> Tuple[bool, bool, Properties]:
        """
        Get configuration state and properties object.

        Returns:
            Tuple of (loaded, reloaded, configs)
        """
        CosThetaConfigurator._loadConfig()
        return CosThetaConfigurator._loaded, CosThetaConfigurator._reloaded, CosThetaConfigurator._configs

    # =============================================================================
    # CONFIGURATION INTEGRITY CHECK
    # =============================================================================

    @classmethod
    def checkIntegrity(cls) -> Optional[bool]:
        """
        Verify configuration integrity and compatibility.
        Exits program if production mode has incompatible logging settings.

        Returns:
            bool: True if configuration is valid
        """
        print(CosThetaColors.CBOLD, end="")
        print(CosThetaColors.CEND)

        if (CosThetaConfigurator.integrityIsOk is None) or (not CosThetaConfigurator.integrityIsOk):
            appMode = CosThetaConfigurator.getApplicationMode()
            fileLoggingLevel = CosThetaConfigurator.getFileLoggingLevel()
            consoleLoggingLevel = CosThetaConfigurator.getConsoleLoggingLevel()

            prodMode = "PRODUCTION" in appMode
            allowedLoggingModeInProd = (
                    (("CONSIDER_ACTION" in fileLoggingLevel) or ("TAKE_ACTION" in fileLoggingLevel)) and
                    (("CONSIDER_ACTION" in consoleLoggingLevel) or ("TAKE_ACTION" in consoleLoggingLevel))
            )

            if not prodMode or (prodMode and allowedLoggingModeInProd):
                CosThetaConfigurator.integrityIsOk = True
            else:
                print(CosThetaColors.CRED, end="")
                print(CosThetaColors.CBOLD, end="")
                print(f"Application mode is {appMode}, file logging level is {fileLoggingLevel}, "
                      f"console logging level is {consoleLoggingLevel}")
                print(f"This is an incompatible combination.", end="")
                print(CosThetaColors.CEND, end="")
                CosThetaConfigurator.integrityIsOk = False
                print(CosThetaColors.CRED, end="")
                print(CosThetaColors.CBOLD, end="")
                print("Hence, closing down the program.", end="")
                print(CosThetaColors.CEND)
                sys.exit(0)

        return CosThetaConfigurator.integrityIsOk

    # =============================================================================
    # HELPER METHODS FOR TYPE-SAFE VALUE RETRIEVAL
    # =============================================================================

    @classmethod
    def getValue(cls, key: str, default: str = '') -> Any:
        """
        Get a configuration value by key with optional default.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        key = str(key)
        l, r, c = CosThetaConfigurator._getConfig()
        try:
            value = c[key]
        except Exception:
            value = None

        if value is None:
            return default
        return value

    @classmethod
    def _getBool(cls, key: str, default: bool) -> bool:
        """
        Helper method to get boolean configuration values.

        Args:
            key: Configuration key
            default: Default boolean value

        Returns:
            bool: Configuration value as boolean
        """
        try:
            val = str(cls.getValue(key, default=str(default)))
            return val.lower() == "true"
        except Exception:
            return default

    @classmethod
    def _getInt(cls, key: str, default: int) -> int:
        """
        Helper method to get integer configuration values.

        Args:
            key: Configuration key
            default: Default integer value

        Returns:
            int: Configuration value as integer
        """
        try:
            return int(cls.getValue(key, default=str(default)))
        except Exception:
            return default

    @classmethod
    def _getFloat(cls, key: str, default: float) -> float:
        """
        Helper method to get float configuration values.

        Args:
            key: Configuration key
            default: Default float value

        Returns:
            float: Configuration value as float
        """
        try:
            return float(cls.getValue(key, default=str(default)))
        except Exception:
            return default

    @classmethod
    def _getString(cls, key: str, default: str) -> str:
        """
        Helper method to get string configuration values.

        Args:
            key: Configuration key
            default: Default string value

        Returns:
            str: Configuration value as string
        """
        return str(cls.getValue(key, default=default))

    @classmethod
    def getKeys(cls, matchingString: str) -> List[str]:
        """
        Get all configuration keys that contain the matching string.

        Args:
            matchingString: String to search for in keys

        Returns:
            List of matching keys
        """
        matchingString = str(matchingString).lower()
        l, r, c = CosThetaConfigurator._getConfig()
        keys = c.keys()
        matchingKeys = [key for key in keys if matchingString in key.lower()]
        return matchingKeys

    # =============================================================================
    # CONFIGURATION KEY DEFINITIONS AND GETTERS
    # =============================================================================
    # All configuration keys are defined as class constants followed by their
    # getter methods. This provides type-safe access and clear documentation.
    # =============================================================================

    # ===== REPORT MONITOR =====
    REPORT_MONITOR_FOUND_KEY = 'report.monitor.found'

    @classmethod
    def getReportMonitorFound(cls) -> bool:
        return cls._getBool(cls.REPORT_MONITOR_FOUND_KEY, False)

    # ===== CAMERA PARAMETERS =====
    CAMERA_ID_KEY = 'camera.id'
    CAMERA_IP_KEY = 'camera.ip'
    CAMERA_PORT_KEY = 'camera.port'
    CAMERA_UID_KEY = 'camera.uid'
    CAMERA_PWD_KEY = 'camera.pwd'
    SAVE_ALL_PICTURES_BECAUSE_ITS_IN_TRIAL_MODE = "save.all.pictures.because.its.in.trial.mode"
    PICTURE_SAVING_DIR_FOR_MODE_TRIAL_KEY = "picture.saving.dir.for.mode.trial"
    MAX_ALLOWED_NONE_FRAME_COUNTS_IN_CAMERA_KEY = "max.allowed.none.frame.counts.in.camera"

    @classmethod
    def getCameraId(cls) -> str:
        return cls._getString(cls.CAMERA_ID_KEY, "Camera_1")

    @classmethod
    def getCameraIP(cls) -> str:
        return cls._getString(cls.CAMERA_IP_KEY, "192.168.1.64")

    @classmethod
    def getCameraPort(cls) -> int:
        return cls._getInt(cls.CAMERA_PORT_KEY, 80)

    @classmethod
    def getCameraUid(cls) -> str:
        return cls._getString(cls.CAMERA_UID_KEY, "admin")

    @classmethod
    def getCameraPwd(cls) -> str:
        return cls._getString(cls.CAMERA_PWD_KEY, "abcd1234")

    @classmethod
    def getMainPictureSavingDirForModeTrial(cls) -> str:
        return cls._getString(cls.PICTURE_SAVING_DIR_FOR_MODE_TRIAL_KEY, "C:/Temp/TrialImages/")

    @classmethod
    def getMaxAllowedNoneFrameCountsInCamera(cls) -> int:
        return cls._getInt(cls.MAX_ALLOWED_NONE_FRAME_COUNTS_IN_CAMERA_KEY, 10)

    @classmethod
    def getSaveAllPicturesBecauseItsInTrialMode(cls) -> bool:
        return cls._getBool(cls.SAVE_ALL_PICTURES_BECAUSE_ITS_IN_TRIAL_MODE, False)

    # ***********************************

    # Picture Reduction parameters
    PICTURE_RECORDING_FPS_KEY = "picture.recording.fps"

    @classmethod
    def getPictureRecordingFPS(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.PICTURE_RECORDING_FPS_KEY, default="16"))
        except Exception as e:
            return 16

    # ***********************************

    # Application parameters
    APPLICATION_NAME_KEY = 'application.name'
    APPLICATION_MODE_KEY = 'application.mode'
    WINDOW_TITLE_KEY = 'window.title'

    @classmethod
    def getApplicationName(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.APPLICATION_NAME_KEY, default='application')

    @classmethod
    def getApplicationMode(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.APPLICATION_MODE_KEY, default='TEST')

    @classmethod
    def getWindowTitle(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.WINDOW_TITLE_KEY, default='Default Window Title')

    # ***********************************

    # File logutils parameters
    FILE_LOGGINGLEVEL_KEY = 'file.loggingLevel'
    LOGGING_DIRECTORY_KEY = 'logging.directory'
    FILELOGGING_FORMAT_KEY = 'filelogging.format'
    FILELOGGING_DATEFORMAT_KEY = 'filelogging.date.format'
    LOGGINGFILE_SUFFIX_KEY = 'loggingfile.suffix'
    BACKUPLOGS_COUNT_KEY = 'backuplogs.count'

    @classmethod
    def getLoggingDirectory(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.LOGGING_DIRECTORY_KEY, default='logs')

    @classmethod
    def getFileLoggingLevel(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.FILE_LOGGINGLEVEL_KEY, default='WARNING')

    @classmethod
    def getFileLoggingFormat(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.FILELOGGING_FORMAT_KEY,
                                             default='%(name)-35s > [%(levelname)s] [%(asctime)s] : %(message)s')

    @classmethod
    def getFileLoggingDateFormat(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.FILELOGGING_DATEFORMAT_KEY,
                                             default='%Y-%m-%d %H:%M:%S')

    @classmethod
    def getFileLoggingSuffix(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.LOGGINGFILE_SUFFIX_KEY, default='_log')

    @classmethod
    def getBackupLogsCount(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.BACKUPLOGS_COUNT_KEY, default="10"))
        except Exception as e:
            return 10

    # ***********************************

    # Console logutils parameters
    CONSOLE_LOGGINGLEVEL_KEY = 'console.logginglevel'
    CONSOLELOGGING_FORMAT_KEY = 'consolelogging.format'
    CONSOLELOGGING_DATEFORMAT_KEY = 'consolelogging.date.format'
    FRONTEND_LOGGING_LEVEL_KEY = 'frontend.logging.level'

    @classmethod
    def getFrontendLoggingLevel(cls) -> str:
        return cls.getValue(key=cls.FRONTEND_LOGGING_LEVEL_KEY, default='INFO')

    @classmethod
    def getConsoleLoggingLevel(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.CONSOLE_LOGGINGLEVEL_KEY, default='WARNING')

    @classmethod
    def getConsoleLoggingFormat(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.CONSOLELOGGING_FORMAT_KEY,
                                             default='%(name)-12s: %(levelname)-8s %(message)s')

    @classmethod
    def getConsoleLoggingDateFormat(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.CONSOLELOGGING_DATEFORMAT_KEY,
                                             default='%d-%m %H:%M:%S.%f')

    # ***********************************

    # Front end parameters
    LABEL_FONTFACE_KEY = 'label.fontface'
    INITIAL_FONTSIZE_KEY = 'initial.fontsize'
    LABEL_INITIAL_HEIGHT_KEY = 'label.initialheight'

    @classmethod
    def getFontFace(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.LABEL_FONTFACE_KEY, default='Courier')

    @classmethod
    def getInitialFontsize(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.INITIAL_FONTSIZE_KEY, default="10"))
        except Exception as e:
            return 10

    @classmethod
    def getLabelInitialHeight(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.LABEL_INITIAL_HEIGHT_KEY, default="50"))
        except Exception as e:
            return 50

    # ***********************************

    # Saving images and videos
    BASE_FOLDER_FOR_IMAGES_KEY = 'basefolder.for.images'
    IMAGES_KNUCKLE_FOLDER_KEY = 'images.knuckle.folder'
    FOLDER_FOR_HUB_AND_BOTTOM_BEARING_KEY = 'images.hub.and.bottom.bearing.folder'
    FOLDER_FOR_TOP_BEARING_KEY = 'images.top.bearing.folder'
    IMAGES_NUT_AND_PLATEWASHER_FOLDER_KEY = 'images.nut.and.platewasher.folder'
    IMAGES_SPLITPIN_AND_WASHER_FOLDER_KEY = 'images.splitpin.and.washer.folder'
    IMAGES_CAP_FOLDER_KEY = 'images.cap.folder'
    FOLDER_FOR_BUNK_AND_NO_BUNK_KEY = 'images.bunk.and.no.bunk.folder'
    IMAGES_OK_FOLDER_KEY = 'images.ok.folder'
    IMAGES_NOTOK_FOLDER_KEY = 'images.notok.folder'

    @classmethod
    def getBaseFolderForImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.BASE_FOLDER_FOR_IMAGES_KEY, default="")

    @classmethod
    def getFolderForKnuckleImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IMAGES_KNUCKLE_FOLDER_KEY, default="1-Knuckle/")

    @classmethod
    def getFolderForHubAndBottomBearingImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FOLDER_FOR_HUB_AND_BOTTOM_BEARING_KEY,
                                             default="2-HubAndBottomBearing/")

    @classmethod
    def getFolderForTopBearingImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FOLDER_FOR_TOP_BEARING_KEY,
                                             default="3-TopBearing/")

    @classmethod
    def getFolderForNutAndPlateWasherImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IMAGES_NUT_AND_PLATEWASHER_FOLDER_KEY,
                                             default="4-NutAndPlateWasher/")

    @classmethod
    def getFolderForSplitPinAndWasherImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IMAGES_SPLITPIN_AND_WASHER_FOLDER_KEY,
                                             default="5-SplitPinAndWasher/")

    @classmethod
    def getFolderForCapImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IMAGES_CAP_FOLDER_KEY, default="6-Cap/")

    @classmethod
    def getFolderForBunkAndNoBunkImages(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FOLDER_FOR_BUNK_AND_NO_BUNK_KEY, default="7-BunkAndNoBunk/")

    @classmethod
    def getImagesOKFolder(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IMAGES_OK_FOLDER_KEY, default=f"ok/")

    @classmethod
    def getImagesNotOKFolder(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IMAGES_NOTOK_FOLDER_KEY, default=f"notok/")

    # ***********************************

    # Camera status update parameters
    TIME_DURATION_SLEEP_INTERVAL_KEY = 'timeduration.sleepinterval.sec'
    FRONTEND_ALL_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = 'frontend.all.connectionstatus.sleepinterval.sec'
    COMBINED_HEARTBEAT_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = "combinedheartbeat.connectionstatus.sleepinterval.sec"
    FRONTEND_EMERGENCY_STATUS_SLEEP_INTERVAL_KEY = 'frontend.emergency.status.sleepinterval.sec'
    FRONTEND_STATUS_SLEEP_INTERVAL_KEY = 'frontend.status.sleepinterval.sec'
    CAMERA_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = 'camera.connectionstatus.sleepinterval.sec'
    IO_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = 'costhetaio.connectionstatus.sleepinterval.sec'
    DATABASE_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = "db.connectionstatus.update.sleepinterval.sec"
    CAMERA_TIME_TO_RESPOND_AFTER_POWER_IS_RESTORED_KEY = 'time.takenbycamera.to.respond.after.power.is.restored'
    QRCODE_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = 'qrcode.connectionstatus.update.sleepinterval.sec'
    GET_QRCODE_REQUEST_SLEEP_INTERVAL_KEY = 'qrcode.request.sleepinterval.sec'
    COMBINED_CONNECTION_STATUS_SLEEP_INTERVAL_KEY = 'combined.connection.status.sleepinterval.sec'
    MIN_CONTINUOUS_DISCONNECTIONS_TO_SEND_ALARM_KEY = "min.continuous.disconnections.to.send.alarm"
    LOG_DISCONNECTION_EVERY_N_SECS_KEY = "log.disconnection.every.n.secs"

    @classmethod
    def getTimeDurationSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.TIME_DURATION_SLEEP_INTERVAL_KEY,
                                              default="1.0"))
        except Exception as e:
            return 1.0

    @classmethod
    def getGeneralConnectionStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.FRONTEND_ALL_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                                              default="5.0"))
        except Exception as e:
            return 5.0

    @classmethod
    def getCombinedHeartbeatConnectionStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.COMBINED_HEARTBEAT_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                    default="2.0"))
        except Exception as e:
            return 2.0

    @classmethod
    def getFrontEndEmergencyStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.FRONTEND_EMERGENCY_STATUS_SLEEP_INTERVAL_KEY,
                    default="5.0"))
        except Exception as e:
            return 5.0

    @classmethod
    def getCameraConnectionStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.CAMERA_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                                              default="0.25"))
        except Exception as e:
            return 0.25

    @classmethod
    def getIOConnectionStatusSleepInterval(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.IO_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                                                       default="0.25"))
        except Exception as e:
            return 0.25

    @classmethod
    def getDatabaseConnectionStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.DATABASE_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                                              default="0.25"))
        except Exception as e:
            return 0.25

    @classmethod
    def getQRCodeConnectionStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.QRCODE_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                                              default="0.25"))
        except Exception as e:
            return 0.25

    @classmethod
    def getFrontendStatusSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.FRONTEND_STATUS_SLEEP_INTERVAL_KEY,
                                              default="0.25"))
        except Exception as e:
            return 0.25

    @classmethod
    def getTimeTakenByCameraToRespondAfterPowerIsRestored(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.CAMERA_TIME_TO_RESPOND_AFTER_POWER_IS_RESTORED_KEY, default="30.0"))
        except Exception as e:
            return 30.0

    @classmethod
    def getQRCodeRequestSleepInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.GET_QRCODE_REQUEST_SLEEP_INTERVAL_KEY,
                                              default="0.1"))
        except Exception as e:
            return 0.1

    @classmethod
    def getCombinedConnectionStatusUpdateInterval(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.COMBINED_CONNECTION_STATUS_SLEEP_INTERVAL_KEY,
                                              default="2.0"))
        except Exception as e:
            return 2.0

    @classmethod
    def getMinimumContinuousDisconnectionsNeededToSendAlarm(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.MIN_CONTINUOUS_DISCONNECTIONS_TO_SEND_ALARM_KEY,
                                              default="5"))
        except Exception as e:
            return 5

    @classmethod
    def getLogDisconnectionsAfterNSecs(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.LOG_DISCONNECTION_EVERY_N_SECS_KEY,
                                              default="10"))
        except Exception as e:
            return 1

    # ***********************************

    # Splash screen parameters
    SPLASHSCREEN_TIME_KEY = 'splashscreen.time.sec'
    ENDSCREEN_TIME_KEY = 'endscreen.time.sec'

    @classmethod
    def getSplashScreenTime(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.SPLASHSCREEN_TIME_KEY, default="20"))
        except Exception as e:
            return 20

    @classmethod
    def getEndScreenTime(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.ENDSCREEN_TIME_KEY, default="15"))
        except Exception as e:
            return 15

    # ***********************************

    # Connection retry parameters
    SHOW_RECONNECT_DIALOG_KEY = 'show.reconnect.dialog'
    WAITTIME_AFTER_RECONNECT_KEY = 'waittime.after.reconnect'
    CONSECUTIVE_CONNECTION_RETRIES_KEY = 'consecutive.connect.retries'
    INTERVAL_BETWEEN_CONNECTION_RETRIES_KEY = 'interval.between.connection.retries.ms'

    @classmethod
    def getShowReconnectDialog(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.SHOW_RECONNECT_DIALOG_KEY, default='false')
        except Exception as e:
            value = 'false'
        if value.lower() == 'true':
            return True
        return False

    @classmethod
    def getWaittimeAfterReconnect(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.WAITTIME_AFTER_RECONNECT_KEY, default="5"))
        except Exception as e:
            return 5

    @classmethod
    def getConsecutiveConnectionRetries(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.CONSECUTIVE_CONNECTION_RETRIES_KEY, default="3"))
        except Exception as e:
            return 3

    @classmethod
    def getMSIntervalBetweenConnectionRetries(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.INTERVAL_BETWEEN_CONNECTION_RETRIES_KEY,
                                                     default="20"))
        except Exception as e:
            return 20

    # ***********************************

    # Google Drive connections
    UPLOAD_TO_GOOGLE_DRIVE_KEY = 'upload.to.googledrive'
    GOOGLEDRIVE_UPLOAD_INTERVAL_KEY = 'googledrive.upload.interval.min'

    @classmethod
    def getUploadToGoogleDrive(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.UPLOAD_TO_GOOGLE_DRIVE_KEY, default='false')
        except Exception as e:
            value = 'false'
        if value.lower() == 'true':
            return True
        return False

    # Delay between pictures and frames of videos
    @classmethod
    def getGoogleDriveUploadInterval(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.GOOGLEDRIVE_UPLOAD_INTERVAL_KEY, default="10"))
        except Exception as e:
            return 10

    # ***********************************

    MINIMUM_DELAY_BETWEEN_PICTURES_KEY = 'minimum.delay.between.pictures.ms'
    MINIMUM_DELAY_BETWEEN_VIDEO_FRAMES_KEY = 'minimum.delay.between.videoframes.ms'
    CALCULATE_DELAY_BETWEEN_PICTURES_KEY = 'calculate.delay.when.using.pictures'
    SLEEP_TIME_FOR_MONITORING_TAKEPICQ_KEY = 'sleeptime.monitor.takepic'
    MAX_ALLOWED_MULTIPLE_FOR_PIC_DELAY_KEY = 'max.allowed.multiple.for.pic.delay'
    MAX_ALLOWED_TIME_TAKING_PICTURE_KEY = 'max.allowed.time.for.taking.picture'
    CUTOFF_TIME_THAT_TRIGGERS_CAMERA_CONNECTION_RENEWAL = 'cutoff.time.that.triggers.camera.connection.renewal'

    @classmethod
    def getMinimumDelayBetweenPicturesInMS(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MINIMUM_DELAY_BETWEEN_PICTURES_KEY,
                                                     default="175"))
        except Exception as e:
            return 175

    @classmethod
    def getMinimumDelayBetweenVideoframesInMS(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MINIMUM_DELAY_BETWEEN_VIDEO_FRAMES_KEY,
                                                     default="80"))
        except Exception as e:
            return 80

    @classmethod
    def getCalculateDelayWhenUsingPictures(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.CALCULATE_DELAY_BETWEEN_PICTURES_KEY,
                                                  default="False")
            if value == "True":
                return True
            else:
                return False
        except Exception as e:
            return False

    @classmethod
    def getSleepTimeForMonitoringTakePicQ(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.SLEEP_TIME_FOR_MONITORING_TAKEPICQ_KEY,
                                                       default="0.02"))
        except Exception as e:
            return 0.02

    @classmethod
    def getMaxAllowedMultipleForPicDelay(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MAX_ALLOWED_MULTIPLE_FOR_PIC_DELAY_KEY,
                                                       default="0.7"))
        except Exception as e:
            return 0.7

    @classmethod
    def getMaxAllowedTimeForTakingPicture(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MAX_ALLOWED_TIME_TAKING_PICTURE_KEY,
                                                       default="0.15"))
        except Exception as e:
            return 0.15

    @classmethod
    def getCutoffTimeThatTriggersCameraConnectionRenewal(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.CUTOFF_TIME_THAT_TRIGGERS_CAMERA_CONNECTION_RENEWAL,
                default="0.2"))
        except Exception as e:
            return 0.2

    # ***********************************

    # ADAM_IP and IO CONNECTION RETRY GAP
    ADAM_IP_KEY = 'adam.ip'
    GAP_BETWEEN_CONNECTION_RETRIES = 'gap.between.ioconnection.retries.sec'

    @classmethod
    def getAdamIP(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.ADAM_IP_KEY, default='192.168.1.50')

    @classmethod
    def getGapBetweenConnectionRetriesinIO(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.GAP_BETWEEN_CONNECTION_RETRIES, default="5"))
        except Exception as e:
            return 5

    # ***********************************

    # Light control parameters and addresses
    CONTROL_LIGHTS_KEY = 'control.lights'
    LIGHTS_ON_POSITION_TIME_KEY = 'lights.on.position.time.sec'
    LIGHT1_ADDRESS_KEY = 'light1.address'
    LIGHT2_ADDRESS_KEY = 'light2.address'
    LIGHT1_ACTIVATED_STATE_KEY = 'light1.activated.state'
    LIGHT2_ACTIVATED_STATE_KEY = 'light2.activated.state'

    @classmethod
    def getControlLights(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.CONTROL_LIGHTS_KEY, default='false')
        except Exception as e:
            value = 'false'
        if value.lower() == 'true':
            return True
        return False

    @classmethod
    def getLightsOnTime(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.LIGHTS_ON_POSITION_TIME_KEY, default="0.1"))
        except Exception as e:
            return 0.1

    @classmethod
    def getLightAddress(cls, lightId: int = 1) -> int:
        attr_name = f"LIGHT{lightId}_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{lightId + 1}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getLightActivatedState(cls, lightId: int = 1) -> int:
        attr_name = f"LIGHT{lightId}_ACTIVATED_STATE_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default="1"))
        except Exception as e:
            value = 1
        return value

    # ***********************************

    # Tower Lamp control parameters and addresses
    CONTROL_TOWER_LAMPS = 'control.towerlamps'
    TOWERLAMP1_GREEN_ADDRESS_KEY = 'towerlamp1.green.address'
    TOWERLAMP1_RED_ADDRESS_KEY = 'towerlamp1.red.address'
    TOWERLAMP2_GREEN_ADDRESS_KEY = 'towerlamp2.green.address'
    TOWERLAMP2_RED_ADDRESS_KEY = 'towerlamp2.red.address'
    TOWERLAMP1_ACTIVATED_STATE_KEY = 'towerlamp1.activated.state'
    TOWERLAMP2_ACTIVATED_STATE_KEY = 'towerlamp2.activated.state'
    GREENLIGHT_DURATION_KEY = 'greenlight.duration.ms'
    REDLIGHT_DURATION_KEY = 'redlight.duration.ms'

    @classmethod
    def getControlTowerlamps(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.CONTROL_TOWER_LAMPS, default='false')
        except Exception as e:
            value = 'false'
        if value.lower() == 'true':
            return True
        return False

    @classmethod
    def getTowerlampGreenAddress(cls, towerlampId: int = 1) -> int:
        attr_name = f"TOWERLAMP{towerlampId}_GREEN_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{4 + towerlampId}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getTowerlampRedAddress(cls, towerlampId: int = 1) -> int:
        attr_name = f"TOWERLAMP{towerlampId}_RED_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{6 + towerlampId}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getTowerlampActivatedState(cls, towerlampId: int = 1) -> int:
        attr_name = f"TOWERLAMP{towerlampId}_ACTIVATED_STATE_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default="1"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getGreenLightDuration(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.GREENLIGHT_DURATION_KEY, default="800"))
        except Exception as e:
            return 800

    @classmethod
    def getRedLightDuration(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.REDLIGHT_DURATION_KEY, default="200"))
        except Exception as e:
            return 200

    # ***********************************

    # Actuator addresses
    ACTUATOR1_OUTPUT_ADDRESS_KEY = 'actuator1.output.address'
    ACTUATOR2_OUTPUT_ADDRESS_KEY = 'actuator2.output.address'
    ACTUATOR1_OUTPUT_ACCEPT_BOTTLES_STATE_KEY = 'actuator1.acceptbottles.state'
    ACTUATOR2_OUTPUT_ACCEPT_BOTTLES_STATE_KEY = 'actuator2.acceptbottles.state'

    ACTUATOR1_INPUT_ADDRESS_KEY = 'actuator_working1.input.address'
    ACTUATOR2_INPUT_ADDRESS_KEY = 'actuator_working2.input.address'
    ACTUATOR1_INPUT_ACCEPT_BOTTLES_STATE_KEY = 'actuator_working1.acceptbottles.state'
    ACTUATOR2_INPUT_ACCEPT_BOTTLES_STATE_KEY = 'actuator_working2.acceptbottles.state'

    @classmethod
    def getActuatorOutputAddress(cls, actuatorId: int = 1) -> int:
        attr_name = f"ACTUATOR{actuatorId}_OUTPUT_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{actuatorId}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getActuatorWorkingInputAddress(cls, actuatorId: int = 1) -> int:
        attr_name = f"ACTUATOR{actuatorId}_INPUT_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{4 + actuatorId}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getActuatorOutputAcceptBottlesState(cls, actuatorId: int = 1) -> int:
        attr_name = f"ACTUATOR{actuatorId}_OUTPUT_ACCEPT_BOTTLES_STATE_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default="1"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getActuatorWorkingInputAcceptBottlesState(cls, actuatorId: int = 1) -> int:
        attr_name = f"ACTUATOR{actuatorId}_INPUT_ACCEPT_BOTTLES_STATE_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default="1"))
        except Exception as e:
            value = 1
        return value

    # ***********************************

    # Disc addresses
    DISC1_INPUT_ADDRESS_KEY = 'disc1.input.address'
    DISC2_INPUT_ADDRESS_KEY = 'disc2.input.address'
    DISC1_ACTIVATED_STATE_KEY = 'disc1.activated.state'
    DISC2_ACTIVATED_STATE_KEY = 'disc2.activated.state'

    @classmethod
    def getDiscInputAddress(cls, discId: int = 1) -> int:
        attr_name = f"DISC{discId}_INPUT_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{discId}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getDiscActivatedState(cls, discId: int = 1) -> int:
        attr_name = f"DISC{discId}_ACTIVATED_STATE_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default="1"))
        except Exception as e:
            value = 1
        return value

    # ***********************************

    # Bottle-release input addresses
    BOTTLE_RELEASE1_INPUT_ADDRESS_KEY = 'bottle_release1.input.address'
    BOTTLE_RELEASE2_INPUT_ADDRESS_KEY = 'bottle_release2.input.address'
    BOTTLE_RELEASE1_ACTIVATED_STATE_KEY = 'bottle_release1.activated.state'
    BOTTLE_RELEASE2_ACTIVATED_STATE_KEY = 'bottle_release2.activated.state'

    @classmethod
    def getBottleReleaseInputAddress(cls, bottleReleaseId: int = 1) -> int:
        attr_name = f"BOTTLE_RELEASE{bottleReleaseId}_INPUT_ADDRESS_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"{2 + bottleReleaseId}"))
        except Exception as e:
            value = 1
        return value

    @classmethod
    def getBottleReleaseActivatedState(cls, bottleReleaseId: int = 1) -> int:
        attr_name = f"BOTTLE_RELEASE{bottleReleaseId}_ACTIVATED_STATE_KEY"
        try:
            value = int(CosThetaConfigurator.getValue(getattr(cls, attr_name), default="1"))
        except Exception as e:
            value = 1
        return value

    # ***********************************

    ALL_CONNECTIONS_OUTPUT_ADDRESS_KEY = "allconnections.output.address"
    FALSE_COUNTER_ACTIVATION_LIMIT_KEY = "false.counter.activation.limit"

    @classmethod
    def getAllConnectionsOutputAddress(cls) -> int:
        try:
            value = int(CosThetaConfigurator.getValue(f"ALL_CONNECTIONS_OUTPUT_ADDRESS_KEY", default="7"))
        except Exception as e:
            value = 7
        return value

    @classmethod
    def getFalseCounterActivationLimit(cls) -> int:
        try:
            value = int(CosThetaConfigurator.getValue(f"FALSE_COUNTER_ACTIVATION_LIMIT_KEY", default="2"))
        except Exception as e:
            value = 2
        return value

    # ***********************************

    # Redis parameters
    REDIS_HOST_KEY = "redisserver.host"
    REDIS_PORT_KEY = "redisserver.port"

    @classmethod
    def getRedisHost(cls) -> str:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.REDIS_HOST_KEY, default='localhost')
        except Exception as e:
            value = 'localhost'
        return value

    @classmethod
    def getRedisPort(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.REDIS_PORT_KEY, default="6379"))
        except Exception as e:
            return 6379

    # ***********************************

    RECORDING1_QUEUE_KEY = "recording1.queue"
    RECORDING2_QUEUE_KEY = "recording2.queue"

    @classmethod
    def getRecordingQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"RECORDING{cameraId}_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"recording{cameraId}.queue")

    # ***********************************

    CAMERA1_TAKE_PIC_QUEUE_KEY = "camera1.takepic.queue"
    CAMERA2_TAKE_PIC_QUEUE_KEY = "camera2.takepic.queue"
    CAMERA1_REQUEST_RESULT_QUEUE_KEY = "camera1.requestresult.queue"
    CAMERA2_REQUEST_RESULT_QUEUE_KEY = "camera2.requestresult.queue"
    CAMERA1_HEARTBEAT_QUEUE_KEY = "camera1.heartbeat.queue"
    CAMERA2_HEARTBEAT_QUEUE_KEY = "camera2.heartbeat.queue"
    CAMERA1_RESULT_QUEUE_KEY = "camera1.result.queue"
    CAMERA2_RESULT_QUEUE_KEY = "camera2.result.queue"

    @classmethod
    def getCameraTakePicQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"CAMERA{cameraId}_TAKE_PIC_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"cam{cameraId}.discinput")

    @classmethod
    def getCameraHeartbeatQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"CAMERA{cameraId}_HEARTBEAT_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"cam{cameraId}.hb")

    @classmethod
    def getCameraRequestResultQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"CAMERA{cameraId}_REQUEST_RESULT_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"cam{cameraId}.request.result")

    @classmethod
    def getCameraResultQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"CAMERA{cameraId}_RESULT_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"cam{cameraId}.result")

    # ***********************************

    ACTUATOR1_HEARTBEAT_QUEUE_KEY = "actuator1.heartbeat.queue"
    ACTUATOR2_HEARTBEAT_QUEUE_KEY = "actuator2.heartbeat.queue"
    ACTUATOR1_ACTION_QUEUE_KEY = "actuator1.action.queue"
    ACTUATOR2_ACTION_QUEUE_KEY = "actuator2.action.queue"
    TOWERLAMP1_ACTION_QUEUE_KEY = "towerlamp1.action.queue"
    TOWERLAMP2_ACTION_QUEUE_KEY = "towerlamp2.action.queue"

    @classmethod
    def getActuatorHeartbeatQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"ACTUATOR{cameraId}_HEARTBEAT_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"act{cameraId}.hb")

    @classmethod
    def getActuatorActionQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"ACTUATOR{cameraId}_ACTION_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"act{cameraId}.action")

    @classmethod
    def getTowerLampActionQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"TOWERLAMP{cameraId}_ACTION_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"tl{cameraId}.action")

    # ***********************************

    BOTTLE_RELEASE1_HEARTBEAT_QUEUE_KEY = "bottle_release1.heartbeat.queue"
    BOTTLE_RELEASE2_HEARTBEAT_QUEUE_KEY = "bottle_release2.heartbeat.queue"

    @classmethod
    def getBottleReleaseHeartbeatQueue(cls, bottleId: int = 1) -> str:
        attr_name = f"BOTTLE_RELEASE{bottleId}_HEARTBEAT_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"bottle{bottleId}.hb")

    # ***********************************

    DATABASE_HEARTBEAT_QUEUE_KEY = "db.heartbeat.queue"
    IO_HEARTBEAT_QUEUE_KEY = "io.heartbeat.queue"
    QRCODE_HEARTBEAT_QUEUE_KEY = "qrcode.heartbeat.queue"

    @classmethod
    def getDatabaseHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.DATABASE_HEARTBEAT_QUEUE_KEY, default=f"db.hb")

    @classmethod
    def getIOHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IO_HEARTBEAT_QUEUE_KEY, default=f"io.hb")

    @classmethod
    def getQRCodeHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.QRCODE_HEARTBEAT_QUEUE_KEY, default=f"qrcode.hb")

    # ***********************************

    SAVEPICTURE1_QUEUE_KEY = "savepicture1.queue"
    SAVEPICTURE2_QUEUE_KEY = "savepicture2.queue"

    @classmethod
    def getSavePictureQueue(cls, cameraId: int = 1) -> str:
        attr_name = f"SAVEPICTURE{cameraId}_QUEUE_KEY"
        return CosThetaConfigurator.getValue(getattr(cls, attr_name), default=f"save{cameraId}.q")

    # ***********************************

    DATABASE_QUEUE_KEY = "db.queue"

    @classmethod
    def getDatabaseQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.DATABASE_QUEUE_KEY, default="db")

    # ***********************************

    SOUND_QUEUE_KEY = "alarm.queue"
    MONITOR_ALL_CONNECTIONS_QUEUE_KEY = "monitorAllConnections.queue"
    GAP_BETWEEN_CONNECTION_ALARMS_KEY = "gap.between.connection.alarms"

    @classmethod
    def getMonitorAllConnectionsQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.MONITOR_ALL_CONNECTIONS_QUEUE_KEY,
                                             default="monitorAllConnectionsQ")

    @classmethod
    def getConnectionAlarmQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.SOUND_QUEUE_KEY, default="alarmQ")

    @classmethod
    def getGapBetweenConnectionAlarms(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(CosThetaConfigurator.GAP_BETWEEN_CONNECTION_ALARMS_KEY, default="60.0"))
        except Exception as e:
            return 60.0

    # ***********************************

    FILE_LOGGING_QUEUE_KEY = "file.logging.queue"

    @classmethod
    def getFileLoggingQueue(cls):
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FILE_LOGGING_QUEUE_KEY, default="filelogging")

    # ***********************************

    CONSOLE_LOGGING_QUEUE_KEY = "console.logging.queue"

    @classmethod
    def getConsoleLoggingQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.CONSOLE_LOGGING_QUEUE_KEY, default="consolelogging")

    # ***********************************

    ALL_CONNECTIONS_QUEUE_KEY = "allconnections.queue"

    @classmethod
    def getAllConnectionsQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.ALL_CONNECTIONS_QUEUE_KEY, default="allQ")

    # ***********************************

    OK_COMMAND_KEY = "ok.command"
    NOT_OK_COMMAND_KEY = "notok.command"
    REQUEST_COMMAND_KEY = "request.command"

    # ***********************************

    @classmethod
    def getOkCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.OK_COMMAND_KEY, default="OK")

    @classmethod
    def getNotOKCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.NOT_OK_COMMAND_KEY, default="NotOK")

    @classmethod
    def getRequestCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.REQUEST_COMMAND_KEY, default="request")

    # STOP COMMUNICATION QUEUES
    STOP_COMMAND_QUEUE_KEY = "stopcommand.queue"
    STOPPED_RESPONSE_QUEUE_KEY = "stoppedresponse.queue"
    START_COMMAND_KEY = "start.command"
    STOP_COMMAND_KEY = "stop.command"
    EXIT_COMMAND_KEY = "exit.command"
    STOPPED_RESPONSE_KEY = "stopped.response"
    REJECT_RESPONSE_KEY = "reject.response"
    UPDATE_VALUE_KEY = "updatevalue.command"
    TAKE_PICTURE_KEY = "takepicture.command"
    READ_QRCODE_KEY = "readqrcode.command"
    NO_ACTION_KEY = "noaction.command"
    MOVE_AHEAD_TO_NEXT_COMMAND_KEY = "move.ahead.to.next.component.command"

    @classmethod
    def getStopCommandQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.STOP_COMMAND_QUEUE_KEY, default="stopcommandQ")

    @classmethod
    def getStoppedResponseQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.STOPPED_RESPONSE_QUEUE_KEY,
                                             default="stoppedresponseQ")

    @classmethod
    def getStartCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.START_COMMAND_KEY, default="start")

    @classmethod
    def getStopCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.STOP_COMMAND_KEY, default="stop")

    @classmethod
    def getExitCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.EXIT_COMMAND_KEY, default="exit")

    @classmethod
    def getStoppedResponse(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.STOPPED_RESPONSE_KEY, default="stopped")

    @classmethod
    def getRejectResponse(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.REJECT_RESPONSE_KEY, default="reject")

    @classmethod
    def getInvalidResult(cls) -> str:
        return "INVALID RESULT"

    @classmethod
    def getInvalidState(cls) -> str:
        return "INVALID STATE"

    @classmethod
    def getUpdateValueCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.UPDATE_VALUE_KEY, default="updatevalue")

    @classmethod
    def getTakePictureCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.TAKE_PICTURE_KEY, default="takepicture")

    @classmethod
    def getReadQRCodeCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.READ_QRCODE_KEY, default="readqrcode")

    @classmethod
    def getNoActionCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.NO_ACTION_KEY, default="noaction")

    @classmethod
    def getMoveAheadToNextComponentCommand(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.MOVE_AHEAD_TO_NEXT_COMMAND_KEY,
                                             default="moveaheadtonextcomponent")

    # ***********************************

    TERMINAL_DEBUG_KEY = "terminal.debug"

    @classmethod
    def getTerminalDebug(cls) -> bool:
        value = CosThetaConfigurator.getValue(CosThetaConfigurator.TERMINAL_DEBUG_KEY, default="False")
        if value.lower() == 'true':
            return True
        return False

    # ***********************************

    POLLING_TIME_FOR_DISC_SIGNAL_KEY = "polling.time.for.disc.signal"
    POLLING_TIME_FOR_BOTTLE_RELEASE_KEY = "polling.time.for.bottle.release"
    POLLING_TIME_FOR_COUNTER_UPDATES_KEY = 'polling.time.for.counter.updates'
    POLLING_TIME_FOR_READING_THREADS_KEY = 'polling.time.for.reading.threads'

    POLLING_TIME_FOR_ACTUATOR_POSITION_KEY = "polling.time.for.actuator.position"
    HOLDING_TIME_FOR_GREEN_SIGNAL_KEY = "holding.time.for.towerlamp.green.signal"
    HOLDING_TIME_FOR_RED_SIGNAL_KEY = "holding.time.for.towerlamp.red.signal"
    HOLDING_TIME_FOR_HOOTER_KEY = "holding.time.for.hooter"
    ANTICIPATED_TIME_FOR_ACTUATOR_ACTIVATION_KEY = "anticipated.time.for.actuator.activation"
    ANTICIPATED_TIME_FOR_BOTTLE_TRAVEL_TO_ACTUATOR_KEY = "anticipated.time.for.bottle.travel.to.actuator"
    WAIT_TIME_BEFORE_ACTUATOR_ACTIVATION_KEY = "wait.time.before.actuator.activation"
    FASTEST_POSSIBLE_TIME_BETWEEN_TAKEPIC_REQUESTS_KEY = "fastest.possible.time.between.takepic.requests"
    FASTEST_POSSIBLE_TIME_BETWEEN_TAKEPIC_AND_BOTTLERELEASE_KEY = "fastest.possible.time.between.takepic.and.bottlerelease"
    TIME_TO_GET_A_PICTURE_KEY = "time.to.get.a.picture"
    MAX_DELAY_ALLOWED_BETWEEN_TAKEPIC_AND_BOTTLERELEASE_KEY = "max.delay.allowed.between.takepic.and.bottlerelease"
    LEFT_DISC_DELAY_TIME_BETWEEN_SIGNAL_AND_TAKE_PIC_KEY = "left.disc.delay.time.between.signal.and.sendtakepic"
    RIGHT_DISC_DELAY_TIME_BETWEEN_SIGNAL_AND_TAKE_PIC_KEY = "right.disc.delay.time.between.signal.and.sendtakepic"
    TIME_BETWEEN_PICTURES_MS_KEY = "time.between.pictures.ms"

    @classmethod
    def getTimeBetweenPicturesInMs(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.TIME_BETWEEN_PICTURES_MS_KEY,
                                                       default="100.0"))
        except Exception as e:
            return 100.0

    @classmethod
    def getPollingTimeForCounterUpdates(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.POLLING_TIME_FOR_COUNTER_UPDATES_KEY,
                                                       default="0.05"))
        except Exception as e:
            return 0.05

    @classmethod
    def getPollingTimeForReadingThreads(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.POLLING_TIME_FOR_READING_THREADS_KEY,
                                                       default="0.03"))
        except Exception as e:
            return 0.03

    @classmethod
    def getPollingTimeForDiscSignal(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.POLLING_TIME_FOR_DISC_SIGNAL_KEY,
                                                       default="0.03"))
        except Exception as e:
            return 0.03

    @classmethod
    def getPollingTimeForActuatorPosition(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.POLLING_TIME_FOR_ACTUATOR_POSITION_KEY,
                                                       default="0.025"))
        except Exception as e:
            return 0.025

    @classmethod
    def getPollingTimeForBottleRelease(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.POLLING_TIME_FOR_BOTTLE_RELEASE_KEY,
                                                       default="0.025"))
        except Exception as e:
            return 0.025

    @classmethod
    def getHoldingTimeForGreenSignal(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.HOLDING_TIME_FOR_GREEN_SIGNAL_KEY,
                                                       default="0.250"))
        except Exception as e:
            return 0.250

    @classmethod
    def getHoldingTimeForRedSignal(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(key=CosThetaConfigurator.HOLDING_TIME_FOR_GREEN_SIGNAL_KEY,
                                                       default="0.1"))
        except Exception as e:
            return 0.1

    @classmethod
    def getHoldingTimeForHooter(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.HOLDING_TIME_FOR_HOOTER_KEY, default="0.05"))
        except Exception as e:
            return 0.05

    @classmethod
    def getAnticipatedTimeForActuatorActivation(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.ANTICIPATED_TIME_FOR_ACTUATOR_ACTIVATION_KEY,
                                              default="0.25"))
        except Exception as e:
            return 0.25

    @classmethod
    def getAnticipatedTimeForBottleTravelToActuator(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.ANTICIPATED_TIME_FOR_BOTTLE_TRAVEL_TO_ACTUATOR_KEY, default="0.3"))
        except Exception as e:
            return 0.3

    @classmethod
    def getWaitTimeBeforeActuatorActivation(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.WAIT_TIME_BEFORE_ACTUATOR_ACTIVATION_KEY,
                                              default="0.05"))
        except Exception as e:
            return 0.05

    @classmethod
    def getFastestPossibleTimeBetweenTakePicRequests(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.FASTEST_POSSIBLE_TIME_BETWEEN_TAKEPIC_REQUESTS_KEY,
                    default="1.0"))
        except Exception as e:
            return 1.0

    @classmethod
    def getTimeToGetAPicture(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.TIME_TO_GET_A_PICTURE_KEY,
                                              default="0.06"))
        except Exception as e:
            return 0.06

    @classmethod
    def getMaximumAllowedDelayBetweenTakePicAndBottleRelease(cls) -> float:
        # if gap between these 2 signals is more than the max allowed, then bottles will be forcibly rejected
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.MAX_DELAY_ALLOWED_BETWEEN_TAKEPIC_AND_BOTTLERELEASE_KEY,
                    default="15.0"))
        except Exception as e:
            return 15.0

    @classmethod
    def getFastestPossibleTimeBetweenTakePicAndBottleRelease(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.FASTEST_POSSIBLE_TIME_BETWEEN_TAKEPIC_AND_BOTTLERELEASE_KEY,
                    default="1.3"))
        except Exception as e:
            return 1.3

    @classmethod
    def getLeftDiscDelayTimeBetweenSignalAndSendTakePic(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.LEFT_DISC_DELAY_TIME_BETWEEN_SIGNAL_AND_TAKE_PIC_KEY,
                    default="0.2"))
        except Exception as e:
            return 0.2

    @classmethod
    def getRightDiscDelayTimeBetweenSignalAndSendTakePic(cls) -> float:
        try:
            return float(
                CosThetaConfigurator.getValue(
                    key=CosThetaConfigurator.RIGHT_DISC_DELAY_TIME_BETWEEN_SIGNAL_AND_TAKE_PIC_KEY,
                    default="0.2"))
        except Exception as e:
            return 0.2

    # ***********************************

    VERIFY_INTEGRITY_KEY = "verify.integrity"

    @classmethod
    def getVerifyIntegrity(cls) -> bool:
        value = CosThetaConfigurator.getValue(CosThetaConfigurator.VERIFY_INTEGRITY_KEY, default="False")
        if value.lower() == 'true':
            return True
        return False

    # ***********************************

    BEEPER_MESSAGE_KEY = "beeper.message"
    BEEPER_REPEATS_KEY = "beeper.repeats"

    @classmethod
    def getHeartbeatBeepMessage(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.BEEPER_MESSAGE_KEY, default="beep")

    @classmethod
    def getBeeperRepeats(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=CosThetaConfigurator.BEEPER_REPEATS_KEY, default="1"))
        except Exception as e:
            return 1

    # ***********************************

    RECORDING_DURATION_SECS_KEY = "recording.duration.secs"
    RECORD_VIDEO_KEY = "record.video"
    RECORD_PICTURES_KEY = "record.pictures"

    @classmethod
    def getRecordingDuration(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.RECORDING_DURATION_SECS_KEY, default="10"))
        except Exception as e:
            return 10

    @classmethod
    def getRecordVideo(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.RECORD_VIDEO_KEY, default='false')
        except Exception as e:
            value = 'false'
        if value.lower() == 'true':
            return True
        return False

    @classmethod
    def getRecordPictures(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.RECORD_PICTURES_KEY, default='true')
        except Exception as e:
            value = 'true'
        if value.lower() == 'true':
            return True
        return False

    # ***********************************
    LEFT_DISC_EXCLUSION_ENTRY_SIDE_POLYGON_KEY = "left.disc.exclusion.polygon.entry.side"
    LEFT_DISC_EXCLUSION_EXIT_SIDE_POLYGON_KEY = "left.disc.exclusion.polygon.exit.side"
    LEFT_DISC_INNER_POLYGONPOINTS_KEY = "left.disc.inner.polygonpoints"
    LEFT_DISC_MIDDLE_POLYGONPOINTS_KEY = "left.disc.middle.polygonpoints"
    LEFT_DISC_OUTER_POLYGONPOINTS_KEY = "left.disc.outer.polygonpoints"

    RIGHT_DISC_EXCLUSION_ENTRY_SIDE_POLYGON_KEY = "right.disc.exclusion.polygon.entry.side"
    RIGHT_DISC_EXCLUSION_EXIT_SIDE_POLYGON_KEY = "right.disc.exclusion.polygon.exit.side"
    RIGHT_DISC_INNER_POLYGONPOINTS_KEY = "right.disc.inner.polygonpoints"
    RIGHT_DISC_MIDDLE_POLYGONPOINTS_KEY = "right.disc.middle.polygonpoints"
    RIGHT_DISC_OUTER_POLYGONPOINTS_KEY = "right.disc.outer.polygonpoints"

    @classmethod
    def getLeftDiscExclusionEntryPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_EXCLUSION_ENTRY_SIDE_POLYGON_KEY}",
                default="[[1235, 270], [1140, 215], [1170, 160], [965, 80], [965, 45], [800, 30], [800, 10], [1000, 10], [1275, 100]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[1235, 270], [1140, 215], [1170, 160], [965, 80], [965, 45], [800, 30], [800, 10], [1000, 10], [1275, 100]]"),
                dtype=np.int32)

    @classmethod
    def getLeftDiscExclusionExitPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_EXCLUSION_EXIT_SIDE_POLYGON_KEY}",
                default="[[465, 600], [500, 240], [560, 220], [620, 650]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads("[[465, 600], [500, 240], [560, 220], [620, 650]]"), dtype=np.int32)

    @classmethod
    def getLeftDiscInnerPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_INNER_POLYGONPOINTS_KEY}",
                default="[[990, 60], [875, 235], [740, 370], [590, 450], [540, 280],[720, 170], [765, 30]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(
                json.loads("[[990, 60], [875, 235], [740, 370], [590, 450], [540, 280],[720, 170], [765, 30]]"),
                dtype=np.int32)

    @classmethod
    def getLeftDiscMiddlePolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_MIDDLE_POLYGONPOINTS_KEY}",
                default="[[1150, 165], [1015, 90], [845, 335], [700, 430], [590, 445], [610, 615], [820, 535], [1040, 345]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[1150, 165], [1015, 90], [845, 335], [700, 430], [590, 445], [610, 615], [820, 535], [1040, 345]]"),
                dtype=np.int32)

    @classmethod
    def getLeftDiscOuterPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_OUTER_POLYGONPOINTS_KEY}",
                default="[[1200, 310], [1180, 395], [1090, 510], [1005, 570], [925, 620], [880, 640], [815, 675], [688, 700], [655, 610], [825, 540], [925, 480], [1035, 350], [1100, 250]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[1200, 310], [1180, 395], [1090, 510], [1005, 570], [925, 620], [880, 640], [815, 675], [688, 700], [655, 610], [825, 540], [925, 480], [1035, 350], [1100, 250]]"),
                dtype=np.int32)

    # ************

    @classmethod
    def getRightDiscExclusionEntryPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_EXCLUSION_ENTRY_SIDE_POLYGON_KEY}",
                default="[[20, 300], [70, 220], [60, 210], [235, 110], [220, 80], [390, 10], [230, 10], [7, 130]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(
                json.loads("[[20, 300], [70, 220], [60, 210], [235, 110], [220, 80], [390, 10], [230, 10], [7, 130]]"),
                dtype=np.int32)

    @classmethod
    def getRightDiscExclusionExitPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_EXCLUSION_EXIT_SIDE_POLYGON_KEY}",
                default="[[755, 570], [755, 500], [735, 505], [740, 400], [720, 395], [730, 260], [665, 275], [665, 400], [630, 410], [625, 550], [570, 550], [570, 645]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[755, 570], [755, 500], [735, 505], [740, 400], [720, 395], [730, 260], [665, 275], [665, 400], [630, 410], [625, 550], [570, 550], [570, 645]]"),
                dtype=np.int32)

    @classmethod
    def getRightDiscInnerPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_INNER_POLYGONPOINTS_KEY}",
                default="[[225, 80], [327, 235], [415, 320], [515, 378], [715, 395], [700, 280], [590, 230], [475, 135], [405, 25]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[225, 80], [327, 235], [415, 320], [515, 378], [715, 395], [700, 280], [590, 230], [475, 135], [405, 25]]"),
                dtype=np.int32)

    @classmethod
    def getRightDiscMiddlePolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_MIDDLE_POLYGONPOINTS_KEY}",
                default="[[70, 215], [180, 370], [315, 485], [410, 520], [485, 535], [705, 535], [705, 440], [485, 400], [310, 275], [210, 120]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[70, 215], [180, 370], [315, 485], [410, 520], [485, 535], [705, 535], [705, 440], [485, 400], [310, 275], [210, 120]]"),
                dtype=np.int32)

    @classmethod
    def getRightDiscOuterPolygonPoints(cls, cust_name: str, med_name: str) -> np.ndarray:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_OUTER_POLYGONPOINTS_KEY}",
                default="[[25, 365], [90, 255], [215, 385], [370, 495], [480, 540], [625, 550], [635, 630], [520, 640], [395, 625], [295, 590], [200,540], [100,450], [30,370]]")
            listOfPoints = json.loads(pointsAsString)
            return np.asarray(listOfPoints, dtype=np.int32)
        except Exception as e:
            return np.asarray(json.loads(
                "[[25, 365], [90, 255], [215, 385], [370, 495], [480, 540], [625, 550], [635, 630], [520, 640], [395, 625], [295, 590], [200,540], [100,450], [30,370]]"),
                dtype=np.int32)

    # ***********************************

    NO_OF_MEDICINES_KEY = "no.of.medicines"
    MEDICINE_NAME_KEY = "medicine.name.{}"

    @classmethod
    def getNumberOfMedicines(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.NO_OF_MEDICINES_KEY, default="1"))
        except Exception as e:
            return 1

    @classmethod
    def getNameOfMedicine(cls, medNo: int = 1) -> str:
        attr_name: str = CosThetaConfigurator.getValue(key=CosThetaConfigurator.MEDICINE_NAME_KEY,
                                                       default="medicine.name.{}")
        currentKey = attr_name.format(medNo)
        try:
            return CosThetaConfigurator.getValue(key=currentKey, default="Becadexamin")
        except Exception as e:
            return "Becadexamin"

    # ***********************************

    CONNECTION_STATUS_FONT_MULTIPLE_KEY = "connectionstatus.font.multiple"
    DATETIME_FONT_MULTIPLE_KEY = "datetime.font.multiple"
    COSTHETA_FONT_MULTIPLE_KEY = "costheta.font.multiple"

    @classmethod
    def getConnectionStatusFontMultiple(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.CONNECTION_STATUS_FONT_MULTIPLE_KEY, default="1.4"))
        except Exception as e:
            return 1.4

    @classmethod
    def getDatetimeFontMultiple(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.DATETIME_FONT_MULTIPLE_KEY, default="0.5"))
        except Exception as e:
            return 0.5

    @classmethod
    def getCosthetaFontMultiple(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.COSTHETA_FONT_MULTIPLE_KEY, default="1.0"))
        except Exception as e:
            return 1.0

    # NO OF BOTTLES PER IMAGE
    NO_OF_BOTTLES_PER_IMAGE_KEY = "no.of.bottles.per.image"

    @classmethod
    def getNoOfBottlesPerImage(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.NO_OF_BOTTLES_PER_IMAGE_KEY}",
                default="3"))
        except Exception as e:
            return 3

    # ***********************************Handling Buffering Delay*********************************

    RIGHT_DISC_FIRST_PICTURE_DELAY_KEY = "right.disc.firstpic.delay"
    LEFT_DISC_FIRST_PICTURE_DELAY_KEY = "left.disc.firstpic.delay"
    INTERIM_PICTURES_DELAY = "interim.pictures.delay"

    @classmethod
    def getRightDiscFirstPictureDelay(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.RIGHT_DISC_FIRST_PICTURE_DELAY_KEY, default="0.1"))
        except Exception as e:
            return 0.1

    @classmethod
    def getLeftDiscFirstPictureDelay(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.LEFT_DISC_FIRST_PICTURE_DELAY_KEY, default="1.2"))
        except Exception as e:
            return 1.2

    @classmethod
    def getInterimPicturesDelay(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.INTERIM_PICTURES_DELAY, default="0.1"))
        except Exception as e:
            return 0.1

    # ***********************************Handling Buffering Delay*********************************
    TIME_TO_DISPLAY_OK_IMAGES = "time.to.display.ok.images"
    TIME_TO_DISPLAY_NOT_OK_IMAGES = "time.to.display.not.ok.images"

    @classmethod
    def getTimeToDisplayOkImages(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.TIME_TO_DISPLAY_OK_IMAGES, default="1.0"))
        except Exception as e:
            return 1.0

    @classmethod
    def getTimeToDisplayNotOkImages(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=CosThetaConfigurator.TIME_TO_DISPLAY_NOT_OK_IMAGES, default="5.0"))
        except Exception as e:
            return 5.0

    # ***********************************Counting Aid Parameters*********************************

    NEIGHBOURING_DISTANCE_RIGHT_DISC_KEY = "neighbouring.distance.right.disc"
    NEIGHBOURING_DISTANCE_LEFT_DISC_KEY = "neighbouring.distance.left.disc"
    MIN_AREA_FRACTION_RIGHT_DISC_KEY = "min.area.fraction.right.disc"
    MIN_AREA_FRACTION_LEFT_DISC_KEY = "min.area.fraction.left.disc"
    BASE_MIN_AREA_KEY = "base.min.area.size"

    @classmethod
    def getNeighbouringDistanceForRightDisc(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.NEIGHBOURING_DISTANCE_RIGHT_DISC_KEY}",
                default="55.0"))
        except Exception as e:
            return 55.0

    @classmethod
    def getNeighbouringDistanceForLeftDisc(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.NEIGHBOURING_DISTANCE_LEFT_DISC_KEY}",
                default="55.0"))
        except Exception as e:
            return 55.0

    @classmethod
    def getMinAreaFractionForRightDisc(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.MIN_AREA_FRACTION_RIGHT_DISC_KEY}",
                default="0.4"))
        except Exception as e:
            return 0.4

    @classmethod
    def getMinAreaFractionForLeftDisc(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.MIN_AREA_FRACTION_LEFT_DISC_KEY}",
                default="0.33"))
        except Exception as e:
            return 0.33

    @classmethod
    def getBaseMinAreaSize(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.BASE_MIN_AREA_KEY}", default="30.0"))
        except Exception as e:
            return 30.0

    # ***********************************Desired Capsule Counts *********************************

    RIGHT_DISC_OUTER_COUNT_KEY = "right.disc.outer.count"
    RIGHT_DISC_MIDDLE_COUNT_KEY = "right.disc.middle.count"
    RIGHT_DISC_INNER_COUNT_KEY = "right.disc.inner.count"
    LEFT_DISC_OUTER_COUNT_KEY = "left.disc.outer.count"
    LEFT_DISC_MIDDLE_COUNT_KEY = "left.disc.middle.count"
    LEFT_DISC_INNER_COUNT_KEY = "left.disc.inner.count"

    @classmethod
    def getRightDiscDesiredOuterCount(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_OUTER_COUNT_KEY}",
                default="60"))
        except Exception as e:
            return 60

    @classmethod
    def getRightDiscDesiredMiddleCount(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_MIDDLE_COUNT_KEY}",
                default="60"))
        except Exception as e:
            return 60

    @classmethod
    def getRightDiscDesiredInnerCount(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_INNER_COUNT_KEY}",
                default="60"))
        except Exception as e:
            return 60

    @classmethod
    def getLeftDiscDesiredOuterCount(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_OUTER_COUNT_KEY}",
                default="60"))
        except Exception as e:
            return 60

    @classmethod
    def getLeftDiscDesiredMiddleCount(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_MIDDLE_COUNT_KEY}",
                default="60"))
        except Exception as e:
            return 60

    @classmethod
    def getLeftDiscDesiredInnerCount(cls, cust_name: str, med_name: str) -> int:
        try:
            return int(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_INNER_COUNT_KEY}",
                default="60"))
        except Exception as e:
            return 60

    # ***********************************Coordinates for Repporting Result*********************************

    RIGHT_DISC_INNER_COORDINATE_KEY = "right.disc.inner.coordinate"
    RIGHT_DISC_MIDDLE_COORDINATE_KEY = "right.disc.middle.coordinate"
    RIGHT_DISC_OUTER_COORDINATE_KEY = "right.disc.outer.coordinate"
    LEFT_DISC_INNER_COORDINATE_KEY = "left.disc.inner.coordinate"
    LEFT_DISC_MIDDLE_COORDINATE_KEY = "left.disc.middle.coordinate"
    LEFT_DISC_OUTER_COORDINATE_KEY = "left.disc.outer.coordinate"

    @classmethod
    def getRightDiscInnerCoordinates(cls, cust_name: str, med_name: str) -> tuple:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_INNER_COORDINATE_KEY}",
                default="[470,270]")
            listOfPoints = json.loads(pointsAsString)
            return tuple(listOfPoints)
        except Exception as e:
            return tuple(json.loads("[470,270]"))

    @classmethod
    def getRightDiscMiddleCoordinates(cls, cust_name: str, med_name: str) -> tuple:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_MIDDLE_COORDINATE_KEY}",
                default="[355,420]")
            listOfPoints = json.loads(pointsAsString)
            return tuple(listOfPoints)
        except Exception as e:
            return tuple(json.loads("[355,420]"))

    @classmethod
    def getRightDiscOuterCoordinates(cls, cust_name: str, med_name: str) -> tuple:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_OUTER_COORDINATE_KEY}",
                default="[320,565]")
            listOfPoints = json.loads(pointsAsString)
            return tuple(listOfPoints)
        except Exception as e:
            return tuple(json.loads("[320,565]"))

    @classmethod
    def getLeftDiscInnerCoordinates(cls, cust_name: str, med_name: str) -> tuple:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_INNER_COORDINATE_KEY}",
                default="[830,340]")
            listOfPoints = json.loads(pointsAsString)
            return tuple(listOfPoints)
        except Exception as e:
            return tuple(json.loads("[830,340]"))

    @classmethod
    def getLeftDiscMiddleCoordinates(cls, cust_name: str, med_name: str) -> tuple:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_MIDDLE_COORDINATE_KEY}",
                default="[1010,300]")
            listOfPoints = json.loads(pointsAsString)
            return tuple(listOfPoints)
        except Exception as e:
            return tuple(json.loads("[1010,300]"))

    @classmethod
    def getLeftDiscOuterCoordinates(cls, cust_name: str, med_name: str) -> tuple:
        try:
            pointsAsString = CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_OUTER_COORDINATE_KEY}",
                default="[1150,280]")
            listOfPoints = json.loads(pointsAsString)
            return tuple(listOfPoints)
        except Exception as e:
            return tuple(json.loads("[1150,280]"))

    # ***********************************Min and Max Areas for various parts of the disc*********************************

    RIGHT_DISC_OUTER_MINAREA_KEY = "right.disc.outer.minarea"
    RIGHT_DISC_OUTER_MAXAREA_KEY = "right.disc.outer.maxarea"
    RIGHT_DISC_MIDDLE_MINAREA_KEY = "right.disc.middle.minarea"
    RIGHT_DISC_MIDDLE_MAXAREA_KEY = "right.disc.middle.maxarea"
    RIGHT_DISC_INNER_MINAREA_KEY = "right.disc.inner.minarea"
    RIGHT_DISC_INNER_MAXAREA_KEY = "right.disc.inner.maxarea"

    LEFT_DISC_OUTER_MINAREA_KEY = "left.disc.outer.minarea"
    LEFT_DISC_OUTER_MAXAREA_KEY = "left.disc.outer.maxarea"
    LEFT_DISC_MIDDLE_MINAREA_KEY = "left.disc.middle.minarea"
    LEFT_DISC_MIDDLE_MAXAREA_KEY = "left.disc.middle.maxarea"
    LEFT_DISC_INNER_MINAREA_KEY = "left.disc.inner.minarea"
    LEFT_DISC_INNER_MAXAREA_KEY = "left.disc.inner.maxarea"

    @classmethod
    def getLeftDiscOuterMinArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_OUTER_MINAREA_KEY}",
                default="8.0"))
        except Exception as e:
            return 8.0

    @classmethod
    def getLeftDiscOuterMaxArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_OUTER_MAXAREA_KEY}",
                default="295.0"))
        except Exception as e:
            return 295.0

    @classmethod
    def getLeftDiscMiddleMinArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_MIDDLE_MINAREA_KEY}",
                default="40.0"))
        except Exception as e:
            return 40.0

    @classmethod
    def getLeftDiscMiddleMaxArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_MIDDLE_MAXAREA_KEY}",
                default="295.0"))
        except Exception as e:
            return 295.0

    @classmethod
    def getLeftDiscInnerMinArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_INNER_MINAREA_KEY}",
                default="72.5"))
        except Exception as e:
            return 72.5

    @classmethod
    def getLeftDiscInnerMaxArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.LEFT_DISC_INNER_MAXAREA_KEY}",
                default="295.0"))
        except Exception as e:
            return 295.0

    @classmethod
    def getRightDiscOuterMinArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_OUTER_MINAREA_KEY}",
                default="15.0"))
        except Exception as e:
            return 15.0

    @classmethod
    def getRightDiscOuterMaxArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_OUTER_MAXAREA_KEY}",
                default="287.5"))
        except Exception as e:
            return 287.5

    @classmethod
    def getRightDiscMiddleMinArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_MIDDLE_MINAREA_KEY}",
                default="15.0"))
        except Exception as e:
            return 15.0

    @classmethod
    def getRightDiscMiddleMaxArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_MIDDLE_MAXAREA_KEY}",
                default="293.0"))
        except Exception as e:
            return 293.0

    @classmethod
    def getRightDiscInnerMinArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_INNER_MINAREA_KEY}",
                default="72.5"))
        except Exception as e:
            return 72.5

    @classmethod
    def getRightDiscInnerMaxArea(cls, cust_name: str, med_name: str) -> float:
        try:
            return float(CosThetaConfigurator.getValue(
                key=f"{cust_name.lower()}.{med_name.lower()}.{CosThetaConfigurator.RIGHT_DISC_INNER_MAXAREA_KEY}",
                default="21.0"))
        except Exception as e:
            return 277.5

    # ***********************************Classification for Invalid Result : To ensure picture does not reflected as Not OK*********************************

    MINIMUM_OUTER_COUNT_KEY = "minimum.outer.count"
    MINIMUM_MIDDLE_COUNT_KEY = "minimum.middle.count"
    MINIMUM_INNER_COUNT_KEY = "minimum.inner.count"

    @classmethod
    def getMinimumOuterCount(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MINIMUM_OUTER_COUNT_KEY, default="0"))
        except Exception as e:
            return 0

    @classmethod
    def getMinimumMiddleCount(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MINIMUM_MIDDLE_COUNT_KEY, default="0"))
        except Exception as e:
            return 0

    @classmethod
    def getMinimumInnerCount(cls) -> int:
        try:
            return int(CosThetaConfigurator.getValue(key=CosThetaConfigurator.MINIMUM_INNER_COUNT_KEY, default="0"))
        except Exception as e:
            return 0

    # ***********************************Classification for Reporting and Database Backups *********************************

    REPORT_INVALID_RESULTS_KEY = "report.include.invalidresults"
    AUDIT_REPORT_BASE_DIR_KEY = "audit.report.basedir"
    REPORT_BASE_DIR_KEY = "report.basedir"
    DATABASE_BACKUP_DIR_KEY = "db.backup.dir"

    @classmethod
    def getReportInvalidResults(cls) -> bool:
        try:
            value = CosThetaConfigurator.getValue(key=CosThetaConfigurator.REPORT_INVALID_RESULTS_KEY, default='false')
        except Exception as e:
            value = 'false'
        if value.lower() == 'true':
            return True
        return False

    @classmethod
    def getBaseDirForReports(cls) -> str:
        return CosThetaConfigurator.getValue(
            key=f"{CosThetaConfigurator.REPORT_BASE_DIR_KEY}",
            default='C:/Temp/Reports/')

    @classmethod
    def getBaseDirForAuditReports(cls) -> str:
        return CosThetaConfigurator.getValue(key=f"{CosThetaConfigurator.AUDIT_REPORT_BASE_DIR_KEY}",
                                             default='C:/Temp/Reports/')

    @classmethod
    def getDatabaseBackupDirectory(cls) -> str:
        return CosThetaConfigurator.getValue(key=CosThetaConfigurator.DATABASE_BACKUP_DIR_KEY,
                                             default='C:/DatabaseBackup/')

    # ***********************************QR Code COM Port *********************************

    QRCODE_PORT_KEY = "qrcode.port"
    QRCODE_BAUD_RATE_KEY = "qrcode.baudrate"
    QRCODE_REGEX_PATTERN_KEY = "qrcode.regex.pattern"
    QRCODE_EXTRACT_DATA_KEY = "qrcode.extractdata"
    QRCODE_NUMBER_OF_CHARACTERS_TO_CHECK_KEY = "qrcode.number.of.characters.to.check"
    QRCODE_PART_MAPPING_PATTERN_KEY = "qrcode.partmapping"

    @classmethod
    def getQRCodePort(cls) -> str:
        return CosThetaConfigurator.getValue(key=f"{CosThetaConfigurator.QRCODE_PORT_KEY}", default='COM1')

    @classmethod
    def getQRCodeBaudRate(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=f"{CosThetaConfigurator.QRCODE_BAUD_RATE_KEY}", default='19200'))
        except Exception as e:
            return 38400

    @classmethod
    def getQRCodeRegexPatterns(cls) -> list[str]:
        patterns = []
        for i in range(1, 10):
            try:
                aPattern: str = CosThetaConfigurator.getValue(
                    key=f"{CosThetaConfigurator.QRCODE_REGEX_PATTERN_KEY}.{i}", default='')
                if (aPattern is not None) and (aPattern != ''):
                    patterns.append(aPattern.strip())
            except Exception as e:
                pass
        return patterns

    @classmethod
    def getQRCodeExtractionPatterns(cls) -> list:
        extractionPatterns = []
        for i in range(1, 10):
            try:
                aPattern: str = CosThetaConfigurator.getValue(key=f"{CosThetaConfigurator.QRCODE_EXTRACT_DATA_KEY}.{i}",
                                                              default='')
                # print(f"Got extraction pattern {aPattern}")
                if (aPattern is not None) and (aPattern != ''):
                    index_list = [int(item.strip()) for item in aPattern.strip().split(",")]
                    extractionPatterns.append(index_list)
            except Exception as e:
                pass
        # print(f"{extractionPatterns = }")
        return extractionPatterns

    @classmethod
    def getNumberOfCharactersToCheckInQRCode(cls) -> int:
        try:
            return int(
                CosThetaConfigurator.getValue(key=f"{CosThetaConfigurator.QRCODE_NUMBER_OF_CHARACTERS_TO_CHECK_KEY}",
                                              default='54'))
        except Exception as e:
            return 54

    @classmethod
    def getQRCodePartMappingPatterns(cls) -> dict[str, str]:
        partMappings = {}
        for i in range(1, 50):
            try:
                aMapping: str = CosThetaConfigurator.getValue(
                    key=f"{CosThetaConfigurator.QRCODE_PART_MAPPING_PATTERN_KEY}.{i}", default='')
                if (aMapping is not None) and (aMapping != ''):
                    dollarSignSeparatedValues = aMapping.strip().split("$")
                    if len(dollarSignSeparatedValues) == 3:
                        modelAndSideValue = dollarSignSeparatedValues[1]
                        aPattern = modelAndSideValue.strip().split(".")
                        if (len(aPattern) == 3):
                            aKey = f"{dollarSignSeparatedValues[0]}${aPattern[0]}"
                            aValue = f"{aPattern[1]} - {aPattern[2]} - {dollarSignSeparatedValues[2].strip()}"
                            partMappings[aKey] = aValue
            except Exception as e:
                pass
        return partMappings

    # ***********************************QR Code COM Port *********************************

    READ_QR_CODE_QUEUE_KEY = "read.qrcodeQ"
    SEND_QR_CODE_QUEUE_TO_IO_KEY = "send.qrcodeQ.ioserver"
    SEND_QR_CODE_QUEUE_TO_FE_KEY = "send.qrcodeQ.frontendserver"

    @classmethod
    def getReadQRCodeQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.READ_QR_CODE_QUEUE_KEY, default="readQRCodeq")

    @classmethod
    def getSendQRCodeQueueToIO(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.SEND_QR_CODE_QUEUE_TO_IO_KEY,
                                             default="sendQRCodeq.io")

    @classmethod
    def getSendQRCodeQueueToFrontEnd(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.SEND_QR_CODE_QUEUE_TO_FE_KEY,
                                             default="sendQRCodeq.fe")

    # *********************************** Queue Names *********************************

    IO_2_FRONTEND_QUEUE_KEY = "io.2.frontend.queue"
    IO_2_CAMERA_QUEUE_KEY = "io.2.camera.queue"
    IO_2_QRCODE_QUEUE_KEY = "io.2.qrcode.queue"
    IO_2_QRCODE_ABORT_QUEUE_KEY = "io.2.qrcode.abort.queue"
    IO_2_HEARTBEAT_QUEUE_KEY = "io.2.heartbeat.queue"

    QRCODE_2_IO_QUEUE_KEY = "qrcode.2.io.queue"
    QRCODE_2_FRONTEND_QUEUE_KEY = "qrcode.2.frontend.queue"
    QRCODE_2_HEARTBEAT_QUEUE_KEY = "qrcode.2.heartbeat.queue"
    QRCODE_2_CAMERA_QUEUE_KEY = "qrcode.2.camera.queue"

    FRONTEND_2_IO_QUEUE_KEY = "frontend.2.io.queue"
    FRONTEND_2_DATABASE_QUEUE_KEY = "frontend.2.database.queue"
    FRONTEND_2_HEARTBEAT_QUEUE_KEY = "frontend.2.heartbeat.queue"

    CAMERA_2_IO_QUEUE_KEY = "camera.2.io.queue"
    CAMERA_2_FRONTEND_QUEUE_KEY = "camera.2.frontend.queue"
    CAMERA_2_HEARTBEAT_QUEUE_KEY = "camera.2.heartbeat.queue"

    DATABASE_2_HEARTBEAT_QUEUE_KEY = "database.2.heartbeat.queue"

    HEARTBEAT_2_FRONTEND_QUEUE_KEY = "heartbeat.2.frontend.queue"
    HEARTBEAT_2_IO_QUEUE_KEY = "heartbeat.2.io.queue"

    ALARM_QUEUE_KEY = "alarm.queue"
    EMERGENCY_QUEUE_KEY = "emergency.queue"

    @classmethod
    def getIOToFrontEndQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IO_2_FRONTEND_QUEUE_KEY, default="io2frontend.q")

    @classmethod
    def getIOToCameraQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IO_2_CAMERA_QUEUE_KEY, default="io2camera.q")

    @classmethod
    def getIOToQRCodeQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IO_2_QRCODE_QUEUE_KEY, default="io2qrcode.q")

    @classmethod
    def getIOToQRCodeAbortQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IO_2_QRCODE_ABORT_QUEUE_KEY,
                                             default="io2qrcodeabort.q")

    @classmethod
    def getIOToHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.IO_2_HEARTBEAT_QUEUE_KEY, default="io2hb.q")

    @classmethod
    def getQRCodeToIOQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.QRCODE_2_IO_QUEUE_KEY, default="qrcode2io.q")

    @classmethod
    def getQRCodeToFrontendQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.QRCODE_2_FRONTEND_QUEUE_KEY, default="qrcode2fe.q")

    @classmethod
    def getQRCodeToHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.QRCODE_2_HEARTBEAT_QUEUE_KEY, default="qrcode2hb.q")

    @classmethod
    def getFrontendToIOQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FRONTEND_2_IO_QUEUE_KEY, default="fe2io.q")

    @classmethod
    def getFrontendToDatabaseQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FRONTEND_2_DATABASE_QUEUE_KEY, default="fe2db.q")

    @classmethod
    def getQRCodeToCameraQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.QRCODE_2_CAMERA_QUEUE_KEY, default="qrcode2camera.q")

    @classmethod
    def getFrontendToHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.FRONTEND_2_HEARTBEAT_QUEUE_KEY, default="fe2hb.q")

    @classmethod
    def getCameraToIOQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.CAMERA_2_IO_QUEUE_KEY, default="camera2io.q")

    @classmethod
    def getCameraToFrontendQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.CAMERA_2_FRONTEND_QUEUE_KEY, default="camera2fe.q")

    @classmethod
    def getCameraToHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.CAMERA_2_HEARTBEAT_QUEUE_KEY, default="camera2hb.q")

    @classmethod
    def getDatabaseToHeartbeatQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.DATABASE_2_HEARTBEAT_QUEUE_KEY, default="db2hb.q")

    @classmethod
    def getHeartbeatToFrontendQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.HEARTBEAT_2_FRONTEND_QUEUE_KEY, default="hb2fe.q")

    @classmethod
    def getHeartbeatToIOQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.HEARTBEAT_2_IO_QUEUE_KEY, default="hb2io.q")

    @classmethod
    def getAlarmQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.ALARM_QUEUE_KEY, default="alarm.q")

    @classmethod
    def getEmergencyQueue(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.EMERGENCY_QUEUE_KEY, default="emergency.q")

    # *********************************** PLC-PC Communication Tag names *********************************

    # ==================== QR Code (Step 0) ====================

    PLC_PC_CHECK_QRCODE_KEY = "plc.pc.check.qrcode.tagname"
    PC_PLC_QRCODE_OK_TAGNAME_KEY = "pc.plc.qrcode.ok.tagname"
    PC_PLC_QRCODE_DONE_TAGNAME_KEY = "pc.plc.qrcode.done.tagname"

    # ==================== Check Knuckle (Step 1) ====================
    PLC_PC_CHECK_KNUCKLE_KEY = "plc.pc.check.knuckle.tagname"
    PC_PLC_KNUCKLE_CHECK_OK_TAGNAME_KEY = "pc.plc.knuckle.check.ok.tagname"
    PC_PLC_KNUCKLE_CHECK_DONE_TAGNAME_KEY = "pc.plc.knuckle.check.done.tagname"

    # ==================== Hub Tags (Step 2) ====================
    PLC_PC_CHECK_HUB_KEY = "plc.pc.check.hub.tagname"
    PC_PLC_HUB_CHECK_OK_KEY = "pc.plc.hub.check.ok.tagname"
    PC_PLC_HUB_CHECK_DONE_KEY = "pc.plc.hub.check.done.tagname"

    # ==================== Hub and Second Bearing Tags (Step 3) ====================
    PLC_PC_CHECK_HUB_AND_SECOND_BEARING_KEY = "plc.pc.check.hub.and.second.bearing.tagname"
    PC_PLC_HUB_AND_SECOND_BEARING_CHECK_OK_KEY = "pc.plc.hub.and.second.bearing.check.ok.tagname"
    PC_PLC_HUB_AND_SECOND_BEARING_CHECK_DONE_KEY = "pc.plc.hub.and.second.bearing.check.done.tagname"

    # ==================== Nut and Plate Washer Tags (Step 4) ====================
    PLC_PC_CHECK_NUT_AND_PLATE_WASHER_KEY = "plc.pc.check.nut.and.plate.washer.tagname"
    PC_PLC_NUT_AND_PLATE_WASHER_CHECK_OK_KEY = "pc.plc.nut.and.plate.washer.check.ok.tagname"
    PC_PLC_NUT_AND_PLATE_WASHER_CHECK_DONE_KEY = "pc.plc.nut.and.plate.washer.check.done.tagname"

    # ==================== Station 2 Torque Value Set Tag (Step 5 and 10) ====================
    PLC_PC_STATION2_TORQUE_VALUE_SET_KEY = "plc.pc.station2.torque.value.set.tagname"
    PLC_PC_STATION2_TORQUE_VALUE_KEY = "plc.pc.station2.torque.value.tagname"

    # ==================== Station 3 Free Rotation Done Tag (Step 6) ====================
    PLC_PC_STATION3_ROTATION_DONE_KEY = "plc.pc.station3.rotation.done.tagname"

    # ==================== No Cap Bunk Tags (Step 7) ====================
    PLC_PC_CHECK_NO_CAP_BUNK_KEY = "plc.pc.check.no.cap.bunk.tagname"
    PC_PLC_NO_CAP_BUNK_CHECK_OK_KEY = "pc.plc.no.cap.bunk.check.ok.tagname"
    PC_PLC_NO_CAP_BUNK_CHECK_DONE_KEY = "pc.plc.no.cap.bunk.check.done.tagname"

    # ==================== Component Press Done Tag (Step 8) ====================
    PLC_PC_COMPONENT_PRESS_DONE_KEY = "plc.pc.component.press.done.tagname"

    # ==================== No Bunk Tags (Step 9) ====================
    PLC_PC_CHECK_NO_BUNK_KEY = "plc.pc.check.no.bunk.tagname"
    PC_PLC_NO_BUNK_CHECK_OK_KEY = "pc.plc.no.bunk.check.ok.tagname"
    PC_PLC_NO_BUNK_CHECK_DONE_KEY = "pc.plc.no.bunk.check.done.tagname"

    # ==================== Split Pin and Washer Tags (Step 11) ====================
    PLC_PC_CHECK_SPLIT_PIN_AND_WASHER_KEY = "plc.pc.check.split.pin.and.washer.tagname"
    PC_PLC_SPLIT_PIN_AND_WASHER_CHECK_OK_KEY = "pc.plc.split.pin.and.washer.check.ok.tagname"
    PC_PLC_SPLIT_PIN_AND_WASHER_CHECK_DONE_KEY = "pc.plc.split.pin.and.washer.check.done.tagname"

    # ==================== Check Cap (Step 12) ====================
    PLC_PC_CHECK_CAP_KEY = "plc.pc.check.cap.tagname"
    PC_PLC_CAP_CHECK_OK_KEY = "pc.plc.cap.check.ok.tagname"
    PC_PLC_CAP_CHECK_DONE_KEY = "pc.plc.cap.check.done.tagname"

    # ==================== Check Cap (Step 13) ====================
    PLC_PC_CHECK_BUNK_KEY = "plc.pc.check.bunk.tagname"
    PC_PLC_BUNK_CHECK_OK_KEY = "pc.plc.bunk.check.ok.tagname"
    PC_PLC_BUNK_CHECK_DONE_KEY = "pc.plc.bunk.check.done.tagname"

    # ==================== Station 3 Torque Value Set Tag (Step 14) ====================
    PLC_PC_CAP_PRESS_DONE_KEY = "plc.pc.cap.press.done.tagname"

    # ==================== Station 3 Torque Value Set Tag (Step 15) ====================
    PLC_PC_STATION3_TORQUE_VALUE_SET_KEY = "plc.pc.station3.torque.value.set.tagname"
    PLC_PC_STATION3_TORQUE_VALUE_KEY = "plc.pc.station3.torque.value.tagname"

    PLC_PC_EMERGENCY_ABORT_KEY = "plc.pc.emergency.abort.tagname"
    PLC_PC_WATCH_TAG_KEY = "plc.pc.watchtag.tagname"
    PC_PLC_CONNECTION_STATUS_KEY = "pc.plc.connection.status.tagname"

    # Rotation Settings Tags (PC writes to PLC)
    PC_PLC_NO_OF_ROTATION1_CCW_KEY = "pc.plc.no.of.rotation1.ccw.tagname"
    PC_PLC_NO_OF_ROTATION1_CW_KEY = "pc.plc.no.of.rotation1.cw.tagname"
    PC_PLC_NO_OF_ROTATION2_CCW_KEY = "pc.plc.no.of.rotation2.ccw.tagname"
    PC_PLC_NO_OF_ROTATION2_CW_KEY = "pc.plc.no.of.rotation2.cw.tagname"
    PC_PLC_LH_RH_SELECTION_KEY = "pc.plc.lh.rh.selection.tagname"
    PC_PLC_ROTATION_UNIT_RPM_KEY = "pc.plc.rotation.unit.rpm.tagname"

    PLC_READ_INTERVAL_KEY = "plc.read.interval"
    PLC_WRITE_INTERVAL_KEY = "plc.write.interval"
    PLC_CONNECTION_CHECK_INTERVAL_KEY = "plc.connection.check.interval"

    PLC_IP_KEY = "plc.ip"
    PLC_DEBUG_KEY = "plc.debug"
    PLC_SLEEPTIME_BETWEEN_OK_AND_DONE_KEY = "plc.sleeptime.between.ok.and.done"

    # ==================== Check QR Methods (Step 1) ====================
    @classmethod
    def getPlcPcCheckQRCodeTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_QRCODE_KEY, default="PLC_PC_CheckQRCode")

    @classmethod
    def getPcPlcQRCodeOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_QRCODE_OK_TAGNAME_KEY,
                                             default="PC_PLC_QRCodeCheckOK")

    @classmethod
    def getPcPlcQRCodeDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_QRCODE_DONE_TAGNAME_KEY,
                                             default="PC_PLC_QRCodeCheckDone")

    # ==================== Check Knuckle Methods (Step 2) ====================

    @classmethod
    def getPlcPcCheckKnuckleTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_KNUCKLE_KEY,
                                             default="PLC_PC_CheckKnuckle")

    @classmethod
    def getPcPlcKnuckleCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_KNUCKLE_CHECK_OK_TAGNAME_KEY,
                                             default="PC_PLC_KnuckleCheckOK")

    @classmethod
    def getPcPlcKnuckleCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_KNUCKLE_CHECK_DONE_TAGNAME_KEY,
                                             default="PC_PLC_KnuckleCheckDone")

    # ==================== Hub Methods (Step 3) ====================
    @classmethod
    def getPlcPcCheckHubTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_HUB_KEY,
                                             default="PLC_PC_CheckHub")

    @classmethod
    def getPcPlcHubCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_HUB_CHECK_OK_KEY,
                                             default="PC_PLC_HubCheckOK")

    @classmethod
    def getPcPlcHubCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_HUB_CHECK_DONE_KEY,
                                             default="PC_PLC_HubCheckDone")

    # ==================== Hub and Second Bearing Methods (Step 3) ====================
    @classmethod
    def getPlcPcCheckHubAndSecondBearingTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_HUB_AND_SECOND_BEARING_KEY,
                                             default="PLC_PC_CheckHubAndSecondBearing")

    @classmethod
    def getPcPlcHubAndSecondBearingCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_HUB_AND_SECOND_BEARING_CHECK_OK_KEY,
                                             default="PC_PLC_HubAndSecondBearingCheckOK")

    @classmethod
    def getPcPlcHubAndSecondBearingCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_HUB_AND_SECOND_BEARING_CHECK_DONE_KEY,
                                             default="PC_PLC_HubAndSecondBearingCheckDone")

    # ==================== Nut and Plate Washer Methods (Step 4) ====================

    @classmethod
    def getPlcPcCheckNutAndPlateWasherTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_NUT_AND_PLATE_WASHER_KEY,
                                             default="PLC_PC_CheckNutAndPlateWasher")

    @classmethod
    def getPcPlcNutAndPlateWasherOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NUT_AND_PLATE_WASHER_CHECK_OK_KEY,
                                             default="PC_PLC_NutAndPlateWasherCheckOK")

    @classmethod
    def getPcPlcNutAndPlateWasherDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NUT_AND_PLATE_WASHER_CHECK_DONE_KEY,
                                             default="PC_PLC_NutAndPlateWasherCheckDone")

    # ==================== Station 2 Torque Value Set Method (Step 5 and 10) ====================
    @classmethod
    def getPlcPcStation2TorqueValueSetTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_STATION2_TORQUE_VALUE_SET_KEY,
                                             default="PLC_PC_Station2TorqueValueSet")

    @classmethod
    def getPlcPcStation2TorqueValueTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_STATION2_TORQUE_VALUE_KEY,
                                             default="PLC_PC_Station2TorqueValue")

    # ==================== Station 3 Rotation Done Method (Step 6) ====================
    @classmethod
    def getPlcPcStation3RotationDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_STATION3_ROTATION_DONE_KEY,
                                             default="PLC_PC_Station3RotationDone")

    # ==================== No Cap Bunk Methods (Step 7) ====================
    @classmethod
    def getPlcPcCheckNoCapBunkTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_NO_CAP_BUNK_KEY,
                                             default="PLC_PC_CheckNoCapBunk")

    @classmethod
    def getPcPlcNoCapBunkCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_CAP_BUNK_CHECK_OK_KEY,
                                             default="PC_PLC_NoCapBunkCheckOK")

    @classmethod
    def getPcPlcNoCapBunkCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_CAP_BUNK_CHECK_DONE_KEY,
                                             default="PC_PLC_NoCapBunkCheckDone")

    # ==================== Component Press Done Method (Step 8) ====================
    @classmethod
    def getPlcPcComponentPressDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_COMPONENT_PRESS_DONE_KEY,
                                             default="PLC_PC_ComponentPressDone")

    # ==================== No Bunk Methods (Step 9) ====================
    @classmethod
    def getPlcPcCheckNoBunkTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_NO_BUNK_KEY,
                                             default="PLC_PC_CheckNoBunk")

    @classmethod
    def getPcPlcNoBunkCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_BUNK_CHECK_OK_KEY,
                                             default="PC_PLC_NoBunkCheckOK")

    @classmethod
    def getPcPlcNoBunkCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_BUNK_CHECK_DONE_KEY,
                                             default="PC_PLC_NoBunkCheckDone")

    # ==================== Split Pin and Washer Methods (Step 11) ====================
    @classmethod
    def getPlcPcCheckSplitPinAndWasherTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_SPLIT_PIN_AND_WASHER_KEY,
                                             default="PLC_PC_CheckSplitPinAndWasher")

    @classmethod
    def getPcPlcSplitPinAndWasherCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_SPLIT_PIN_AND_WASHER_CHECK_OK_KEY,
                                             default="PC_PLC_SplitPinAndWasherCheckOK")

    @classmethod
    def getPcPlcSplitPinAndWasherCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_SPLIT_PIN_AND_WASHER_CHECK_DONE_KEY,
                                             default="PC_PLC_SplitPinAndWasherCheckDone")

    # ==================== Cap Methods (Step 12) ====================
    @classmethod
    def getPlcPcCheckCapTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_CAP_KEY,
                                             default="PLC_PC_CheckCap")

    @classmethod
    def getPcPlcCapCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_CAP_CHECK_OK_KEY,
                                             default="PC_PLC_CapCheckOK")

    @classmethod
    def getPcPlcCapCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_CAP_CHECK_DONE_KEY,
                                             default="PC_PLC_CapCheckDone")

    # ==================== Bunk Methods (Step 13) ====================
    @classmethod
    def getPlcPcCheckBunkTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CHECK_BUNK_KEY,
                                             default="PLC_PC_CheckBunk")

    @classmethod
    def getPcPlcBunkCheckOKTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_BUNK_CHECK_OK_KEY,
                                             default="PC_PLC_BunkCheckOK")

    @classmethod
    def getPcPlcBunkCheckDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_BUNK_CHECK_DONE_KEY,
                                             default="PC_PLC_BunkCheckDone")

    # ==================== Cap Press Done Method (Step 14) ====================
    @classmethod
    def getPlcPcCapPressDoneTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_CAP_PRESS_DONE_KEY,
                                             default="PLC_PC_CapPressDone")

    # ==================== Station 3 Torque Methods (Step 15) ====================
    @classmethod
    def getPlcPcStation3TorqueValueSetTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_STATION3_TORQUE_VALUE_SET_KEY,
                                             default="PLC_PC_Station3TorqueValueSet")

    @classmethod
    def getPlcPcStation3TorqueValueTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_STATION3_TORQUE_VALUE_KEY,
                                                 default="PLC_PC_Station3TorqueValue")

    # ================================================================================
    @classmethod
    def getPlcPcEmergencyAbortTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_EMERGENCY_ABORT_KEY,
                                             default="PLC_PC_EmergencyAbort")

    @classmethod
    def getPlcPcWatchTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_PC_WATCH_TAG_KEY,
                                             default="PLC_PC_WatchTag")

    @classmethod
    def getPcPlcConnectionStatusTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_CONNECTION_STATUS_KEY,
                                             default="PC_PLC_ConnectionStatus")

    @classmethod
    def getPlcIP(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_IP_KEY, default="192.168.1.100")

    @classmethod
    def getPlcDebug(cls) -> bool:
        try:
            val = str(CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_DEBUG_KEY, default="False"))
            return True if val.lower() == "true" else False
        except Exception as e:
            return False

    @classmethod
    def getPlcSleepTimeBetweenOKAndDone(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_SLEEPTIME_BETWEEN_OK_AND_DONE_KEY,
                                                       default="0.2"))
        except Exception as e:
            return 0.2

    @classmethod
    def getPlcReadInterval(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_READ_INTERVAL_KEY,
                                                       default="0.2"))
        except:
            return 0.2

    @classmethod
    def getPlcWriteInterval(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_WRITE_INTERVAL_KEY,
                                                       default="0.1"))
        except:
            return 0.1

    @classmethod
    def getPlcConnectionCheckInterval(cls) -> float:
        try:
            return float(CosThetaConfigurator.getValue(CosThetaConfigurator.PLC_CONNECTION_CHECK_INTERVAL_KEY,
                                                       default="1.0"))
        except:
            return 1.0

    # ==================== Rotation Settings Tag Getters ====================

    @classmethod
    def getPcPlcNoOfRotation1CCWTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_OF_ROTATION1_CCW_KEY,
                                             default="PC_PLC_NoOfRotation1CCW")

    @classmethod
    def getPcPlcNoOfRotation1CWTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_OF_ROTATION1_CW_KEY,
                                             default="PC_PLC_NoOfRotation1CW")

    @classmethod
    def getPcPlcNoOfRotation2CCWTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_OF_ROTATION2_CCW_KEY,
                                             default="PC_PLC_NoOfRotation2CCW")

    @classmethod
    def getPcPlcNoOfRotation2CWTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_NO_OF_ROTATION2_CW_KEY,
                                             default="PC_PLC_NoOfRotation2CW")

    @classmethod
    def getPcPlcLHRHSelectionTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_LH_RH_SELECTION_KEY,
                                             default="PC_PLC_LH_RH_Selection")

    @classmethod
    def getPcPlcRotationUnitRPMTagName(cls) -> str:
        return CosThetaConfigurator.getValue(CosThetaConfigurator.PC_PLC_ROTATION_UNIT_RPM_KEY,
                                             default="PC_PLC_RotationUnitRPM")

    # *********************************** Target width and height for Machine States *********************************

    MACHINE_STATE_3_TARGET_WIDTH_KEY: str = "machine.state.3.target.width"
    MACHINE_STATE_3_TARGET_HEIGHT_KEY: str = "machine.state.3.target.height"

    MACHINE_STATE_5_TARGET_WIDTH_KEY: str = "machine.state.5.target.width"
    MACHINE_STATE_5_TARGET_HEIGHT_KEY: str = "machine.state.5.target.height"

    MACHINE_STATE_7_TARGET_WIDTH_KEY: str = "machine.state.7.target.width"
    MACHINE_STATE_7_TARGET_HEIGHT_KEY: str = "machine.state.7.target.height"

    MACHINE_STATE_9_TARGET_WIDTH_KEY: str = "machine.state.9.target.width"
    MACHINE_STATE_9_TARGET_HEIGHT_KEY: str = "machine.state.9.target.height"

    MACHINE_STATE_14_TARGET_WIDTH_KEY: str = "machine.state.14.target.width"
    MACHINE_STATE_14_TARGET_HEIGHT_KEY: str = "machine.state.14.target.height"

    MACHINE_STATE_17_TARGET_WIDTH_KEY: str = "machine.state.17.target.width"
    MACHINE_STATE_17_TARGET_HEIGHT_KEY: str = "machine.state.17.target.height"

    MACHINE_STATE_21_TARGET_WIDTH_KEY: str = "machine.state.21.target.width"
    MACHINE_STATE_21_TARGET_HEIGHT_KEY: str = "machine.state.21.target.height"

    MACHINE_STATE_23_TARGET_WIDTH_KEY: str = "machine.state.23.target.width"
    MACHINE_STATE_23_TARGET_HEIGHT_KEY: str = "machine.state.23.target.height"

    MACHINE_STATE_25_TARGET_WIDTH_KEY: str = "machine.state.25.target.width"
    MACHINE_STATE_25_TARGET_HEIGHT_KEY: str = "machine.state.25.target.height"

    @classmethod
    def getTargetWidthAndHeight(cls, currentMachineState: int) -> Tuple[int, int]:
        attr_name_width = f"MACHINE_STATE_{currentMachineState}_TARGET_WIDTH_KEY"
        attr_name_height = f"MACHINE_STATE_{currentMachineState}_TARGET_HEIGHT_KEY"
        targetWidth: int = int(CosThetaConfigurator.getValue(getattr(cls, attr_name_width), default=f"1080"))
        targetHeight: int = int(CosThetaConfigurator.getValue(getattr(cls, attr_name_height), default=f"720"))
        return targetWidth, targetHeight

    # *********************************** max seconds to wait for camera feedback *********************************

    MAX_SECONDS_TO_WAIT_FOR_CAMERA_FEEDBACK_KEY: str = "max.seconds.to.wait.for.camera.feedback"

    @classmethod
    def getMaxSecondsToWaitForCameraFeedback(cls) -> float:
        return float(CosThetaConfigurator.getValue(CosThetaConfigurator.MAX_SECONDS_TO_WAIT_FOR_CAMERA_FEEDBACK_KEY,
                                                   default="5"))

    # *********************************** max seconds to wait for camera feedback *********************************

    @classmethod
    def getInstructionForState(cls, stateNumber: int) -> str:
        key = f"state.{stateNumber}.instruction"
        return CosThetaConfigurator.getValue(key, default="NO INSTRUCTION AVAILABLE")

    # *********************************** CAP CHECK PARAMETERS *********************************

    CAP_CHECK_CENTER_X_KEY: str = "cap.check.center.x"
    CAP_CHECK_CENTER_Y_KEY: str = "cap.check.center.y"
    CAP_CHECK_RADIUS_DOST_KEY: str = "cap.check.radius.dost"
    CAP_CHECK_RADIUS_DOSTPLUS_KEY: str = "cap.check.radius.dostplus"
    CAP_CHECK_DOST_DELTA_THRESHOLD_KEY: str = "cap.check.delta.threshold.dost"
    CAP_CHECK_DOST_RB_THRESHOLD_KEY: str = "cap.check.rb.threshold.dost"
    CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_KEY: str = "cap.check.delta.threshold.dostplus"
    CAP_CHECK_DOSTPLUS_RB_THRESHOLD_KEY: str = "cap.check.rb.threshold.dostplus"

    # Component-specific delta threshold keys for Step 1
    CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_HUB_KEY: str = "cap.check.delta.threshold.hub.dostplus"
    CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_TOP_KEY: str = "cap.check.delta.threshold.top.dostplus"
    CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_NUT_KEY: str = "cap.check.delta.threshold.nut.dostplus"
    CAP_CHECK_DOST_DELTA_THRESHOLD_HUB_KEY: str = "cap.check.delta.threshold.hub.dost"
    CAP_CHECK_DOST_DELTA_THRESHOLD_TOP_KEY: str = "cap.check.delta.threshold.top.dost"
    CAP_CHECK_DOST_DELTA_THRESHOLD_NUT_KEY: str = "cap.check.delta.threshold.nut.dost"

    @classmethod
    def getCapCheckCenterX(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_CENTER_X_KEY, default="635"))

    @classmethod
    def getCapCheckCenterY(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_CENTER_Y_KEY, default="360"))

    @classmethod
    def getCapCheckRadius(cls, componentType: str = "DOST") -> int:
        if componentType.upper() == "DOSTPLUS":
            return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_RADIUS_DOSTPLUS_KEY, default="70"))
        elif componentType.upper() == "DOST":
            return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_RADIUS_DOST_KEY, default="70"))
        return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_RADIUS_DOST_KEY, default="100"))

    @classmethod
    def getCapCheckDeltaThreshold(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_KEY, default="70"))
        elif componentType.upper() == "DOST":
            return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_KEY, default="70"))
        return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_KEY, default="30"))

    @classmethod
    def getCapCheckRBThreshold(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOSTPLUS_RB_THRESHOLD_KEY, default="15"))
        elif componentType.upper() == "DOST":
            return int(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_RB_THRESHOLD_KEY, default="-1"))
        return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_RB_THRESHOLD_KEY, default="-1"))

    @classmethod
    def getCapCheckDeltaThresholdHub(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_HUB_KEY, default="35"))
        elif componentType.upper() == "DOST":
            return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_HUB_KEY, default="30"))
        return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_HUB_KEY, default="30"))

    @classmethod
    def getCapCheckDeltaThresholdTop(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_TOP_KEY, default="50"))
        elif componentType.upper() == "DOST":
            return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_TOP_KEY, default="30"))
        return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_TOP_KEY, default="30"))

    @classmethod
    def getCapCheckDeltaThresholdNut(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOSTPLUS_DELTA_THRESHOLD_NUT_KEY, default="35"))
        elif componentType.upper() == "DOST":
            return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_NUT_KEY, default="30"))
        return float(CosThetaConfigurator.getValue(cls.CAP_CHECK_DOST_DELTA_THRESHOLD_NUT_KEY, default="30"))

    # *********************************** CAP CHECK PARAMETERS DONE *********************************

    # *********************************** BUNK CHECK PARAMETERS *********************************
    BUNK_CHECK_CENTER_X_KEY: str = "bunk.check.center.x"
    BUNK_CHECK_CENTER_Y_KEY: str = "bunk.check.center.y"
    BUNK_CHECK_RADIUS_DOST_KEY: str = "bunk.check.radius.dost"
    BUNK_CHECK_RADIUS_DOSTPLUS_KEY: str = "bunk.check.radius.dostplus"
    BUNK_CHECK_DOST_RB_DIFF_THRESHOLD_KEY: str = "bunk.check.rb.diff.threshold.dost"
    BUNK_CHECK_DOSTPLUS_RB_DIFF_THRESHOLD_KEY: str = "bunk.check.rb.diff.threshold.dostplus"

    @classmethod
    def getBunkCheckCenterX(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.BUNK_CHECK_CENTER_X_KEY, default="630"))

    @classmethod
    def getBunkCheckCenterY(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.BUNK_CHECK_CENTER_Y_KEY, default="320"))

    @classmethod
    def getBunkCheckRadius(cls, componentType: str = "DOST") -> int:
        if componentType.upper() == "DOSTPLUS":
            return int(CosThetaConfigurator.getValue(cls.BUNK_CHECK_RADIUS_DOSTPLUS_KEY, default="50"))
        elif componentType.upper() == "DOST":
            return int(CosThetaConfigurator.getValue(cls.BUNK_CHECK_RADIUS_DOST_KEY, default="70"))
        return int(CosThetaConfigurator.getValue(cls.BUNK_CHECK_RADIUS_DOST_KEY, default="70"))

    @classmethod
    def getBunkCheckRBDiffThreshold(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return float(CosThetaConfigurator.getValue(cls.BUNK_CHECK_DOSTPLUS_RB_DIFF_THRESHOLD_KEY, default="30"))
        elif componentType.upper() == "DOST":
            return float(CosThetaConfigurator.getValue(cls.BUNK_CHECK_DOST_RB_DIFF_THRESHOLD_KEY, default="30"))
        return float(CosThetaConfigurator.getValue(cls.BUNK_CHECK_DOST_RB_DIFF_THRESHOLD_KEY, default="30"))

    # *********************************** BUNK CHECK PARAMETERS DONE *********************************

    # *********************************** NUT AND PLATE WASHER CHECK PARAMETERS *********************************
    # Replace the old keys with these new ones:
    NUT_PLATE_WASHER_CHECK_CENTER_X_KEY: str = "nut.plate.washer.check.center.x"
    NUT_PLATE_WASHER_CHECK_CENTER_Y_KEY: str = "nut.plate.washer.check.center.y"
    NUT_PLATE_WASHER_CHECK_INNER_RADIUS_KEY: str = "nut.plate.washer.check.inner.radius"
    NUT_PLATE_WASHER_CHECK_MIDDLE_RADIUS_KEY: str = "nut.plate.washer.check.middle.radius"
    NUT_PLATE_WASHER_CHECK_OUTER_RADIUS_KEY: str = "nut.plate.washer.check.outer.radius"
    NUT_PLATE_WASHER_CHECK_NUT_THRESHOLD_KEY: str = "nut.plate.washer.check.nut.threshold"
    NUT_PLATE_WASHER_CHECK_WASHER_THRESHOLD_KEY: str = "nut.plate.washer.check.washer.threshold"

    @classmethod
    def getNutAndPlateWasherCheckCenterX(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_CENTER_X_KEY, default="634"))

    @classmethod
    def getNutAndPlateWasherCheckCenterY(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_CENTER_Y_KEY, default="349"))

    @classmethod
    def getNutAndPlateWasherCheckInnerRadius(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_INNER_RADIUS_KEY, default="26"))

    @classmethod
    def getNutAndPlateWasherCheckMiddleRadius(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_MIDDLE_RADIUS_KEY, default="34"))

    @classmethod
    def getNutAndPlateWasherCheckOuterRadius(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_OUTER_RADIUS_KEY, default="49"))

    @classmethod
    def getNutAndPlateWasherCheckNutThreshold(cls) -> float:
        return float(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_NUT_THRESHOLD_KEY, default="10.0"))

    @classmethod
    def getNutAndPlateWasherCheckWasherThreshold(cls) -> float:
        return float(CosThetaConfigurator.getValue(cls.NUT_PLATE_WASHER_CHECK_WASHER_THRESHOLD_KEY, default="8.0"))

# *********************************** NUT AND PLATE WASHER CHECK PARAMETERS DONE *********************************
# *********************************** NO CAP BUNK CHECK PARAMETERS *********************************
    NO_CAP_BUNK_CHECK_CENTER_X_KEY: str = "no.cap.bunk.check.center.x"
    NO_CAP_BUNK_CHECK_CENTER_Y_KEY: str = "no.cap.bunk.check.center.y"
    NO_CAP_BUNK_CHECK_INNER_RADIUS_OF_NUT_KEY: str = "no.cap.bunk.check.inner.radius.of.nut"
    NO_CAP_BUNK_CHECK_OUTER_RADIUS_OF_NUT_KEY: str = "no.cap.bunk.check.outer.radius.of.nut"
    NO_CAP_BUNK_CHECK_OUTER_RADIUS_OF_WASHER_KEY: str = "no.cap.bunk.check.outer.radius.of.washer"
    NO_CAP_BUNK_CHECK_THRESHOLD_DOST_KEY: str = "no.cap.bunk.check.threshold.dost"
    NO_CAP_BUNK_CHECK_THRESHOLD_DOSTPLUS_KEY: str = "no.cap.bunk.check.threshold.dostplus"

    @classmethod
    def getNoCapBunkCheckCenterX(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_CENTER_X_KEY, default="630"))

    @classmethod
    def getNoCapBunkCheckCenterY(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_CENTER_Y_KEY, default="350"))

    @classmethod
    def getNoCapBunkCheckInnerRadiusOfNut(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_INNER_RADIUS_OF_NUT_KEY, default="26"))

    @classmethod
    def getNoCapBunkCheckOuterRadiusOfNut(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_OUTER_RADIUS_OF_NUT_KEY, default="39"))

    @classmethod
    def getNoCapBunkCheckOuterRadiusOfWasher(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_OUTER_RADIUS_OF_WASHER_KEY, default="59"))

    @classmethod
    def getNoCapBunkCheckThreshold(cls, componentType: str = "DOST") -> float:
        if componentType.upper() == "DOSTPLUS":
            return float(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_THRESHOLD_DOSTPLUS_KEY, default="25"))
        elif componentType.upper() == "DOST":
            return float(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_THRESHOLD_DOST_KEY, default="25"))
        return float(CosThetaConfigurator.getValue(cls.NO_CAP_BUNK_CHECK_THRESHOLD_DOST_KEY, default="25"))

# *********************************** NO CAP BUNK CHECK PARAMETERS DONE *********************************
# *********************************** NO BUNK CHECK PARAMETERS *********************************
    NO_BUNK_CHECK_CENTER_X_KEY: str = "no.bunk.check.center.x"
    NO_BUNK_CHECK_CENTER_Y_KEY: str = "no.bunk.check.center.y"
    NO_BUNK_CHECK_INNER_RADIUS_KEY: str = "no.bunk.check.inner.radius"
    NO_BUNK_CHECK_MIDDLE_RADIUS_KEY: str = "no.bunk.check.middle.radius"
    NO_BUNK_CHECK_OUTER_RADIUS_KEY: str = "no.bunk.check.outer.radius"
    NO_BUNK_CHECK_NUT_THRESHOLD_KEY: str = "no.bunk.check.nut.threshold"
    NO_BUNK_CHECK_WASHER_THRESHOLD_KEY: str = "no.bunk.check.washer.threshold"

    @classmethod
    def getNoBunkCheckCenterX(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_CENTER_X_KEY, default="634"))

    @classmethod
    def getNoBunkCheckCenterY(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_CENTER_Y_KEY, default="349"))

    @classmethod
    def getNoBunkCheckInnerRadius(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_INNER_RADIUS_KEY, default="26"))

    @classmethod
    def getNoBunkCheckMiddleRadius(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_MIDDLE_RADIUS_KEY, default="34"))

    @classmethod
    def getNoBunkCheckOuterRadius(cls) -> int:
        return int(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_OUTER_RADIUS_KEY, default="49"))

    @classmethod
    def getNoBunkCheckNutThreshold(cls) -> float:
        return float(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_NUT_THRESHOLD_KEY, default="10.0"))

    @classmethod
    def getNoBunkCheckWasherThreshold(cls) -> float:
        return float(CosThetaConfigurator.getValue(cls.NO_BUNK_CHECK_WASHER_THRESHOLD_KEY, default="8.0"))
    # *********************************** NO BUNK CHECK PARAMETERS DONE *********************************

    # Washer presence detection control
    CHECK_WASHERS_PRESENCE_IN_NUT_AND_PLATE_WASHER_KEY = "check.washers.presence.in.nutandplatewasher"

    @classmethod
    def getCheckWashersPresenceInNutAndPlateWasher(cls) -> bool:
        """
        Get whether to perform washer presence detection in nut and plate washer check.

        If True: Perform full washer detection using color analysis
        If False: Return result based only on nut detection

        Returns:
            bool: True to check washer presence, False to skip washer check
        """
        return cls._getBool(cls.CHECK_WASHERS_PRESENCE_IN_NUT_AND_PLATE_WASHER_KEY, True)
