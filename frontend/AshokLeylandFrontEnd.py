from datetime import datetime
from typing import Union

import numpy as np
from numpy import ndarray

from logutils import LogLevel

'''
## The Safe Rules for Mixing Qt and Python Threads

If you must mix them, these rules prevent crashes:

**Never** touch a Qt widget or Qt object from a plain Python `Thread`. Qt objects have thread affinity — they belong to the thread that created them.

**Always** use `Qt.QueuedConnection` when connecting signals across thread boundaries. This ensures signal delivery is marshalled through Qt's event queue onto the correct thread.

**Use `QThread` for anything that needs to interact with Qt objects.** QThreads participate in Qt's event system. Plain Python threads do not.

**For non-Qt work** (like Redis I/O in `SlaveFileLogger`), Python threads are fine *as long as they never touch Qt objects at all*, not even through a shared reference.

**Use `QMetaObject.invokeMethod()`** if you need a Python thread to trigger something on the Qt main thread — this is the safe way to cross the thread-affinity boundary.

---

## In Summary
Plain Python Thread          QThread / Qt Main Thread
─────────────────────        ────────────────────────
Knows nothing about Qt  ←──→  Owns all Qt objects
Has no event loop            Has Qt event loop
GIL-protected bytecode       Qt C++ internals NOT GIL-protected
Safe for pure Python I/O     Required for any UI interaction

'''

# PySide6 imports - QtCore
from PySide6.QtCore import (
    Qt,
    QObject,
    QEvent,
    QTimer,
    QThread,
    Signal,
    Slot,
)

# PySide6 imports - QtWidgets
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QFrame,
    QSpacerItem,
    QSizePolicy, QMessageBox,
)

# PySide6 imports - QtGui
from PySide6.QtGui import (
    QColor,
    QPixmap,
    QImage,
    QFont,
    QFontMetrics, QAction, QKeyEvent,
)

from redis import Redis

from BaseUtils import getFullyQualifiedName
# From Configuration
from Configuration import (
    CosThetaConfigurator,
    get_project_root,
)

from frontend.CosThetaMonitorDimensions import (
    getAppInstance,
    populateMonitorDimensions
)

# From frontend widgets
from frontend.widgets.CosThetaSeparators import CosThetaQVLine
from frontend.CosThetaStylesheets import (
    modeLabelStylesheet,
    modeLabelStylesheet_with_no_qr_code,
    modeLabelStylesheet_with_qr_code,
    okLabelStylesheet,
    notokLabelStylesheet, outcomeLabelStylesheet, companyNameStylesheet,
)
from frontend.widgets.CosThetaInitialSplashScreen import CosThetaInitialSplashScreen
from frontend.widgets.CosThetaExitingSplashScreen import CosThetaExitingSplashScreen
from frontend.SimplePopups import (
    # NOTE: This import appears to be unused - verify and remove if not needed
    changePasswordForSelf, createAccount, changePassword, changeRole, activateUser, inactivateUser,
    createProductionReportByModelName, createProductionReportByModelNameAndDateLimits,
    createProductionReportOfTodayByModelName, createProductionReportByDateLimits, createProductionReportOfToday,
    getConfirmation, updateMachineSettingsDialog)
from frontend.frontendutils.FrontEndLogger import (
    # NOTE: This import appears to be unused - verify and remove if not needed
    sendStopToAll)
from frontend.newwidgets.CosThetaResultsContainer import CosThetaResultsContainer
from frontend.newwidgets.CosThetaSimpleMessageContainer import SimpleMessageContainer
from frontend.newwidgets.ToggleMessageContainer import ToggleMessageContainer

# From utils.RedisUtils
from utils.RedisUtils import (
    ok,
    notok,
    ALIVE,
    DEAD,
    sendHeartbeatFromFEServerToHeartbeatServer,
    sendDataFromFEServerToDatabaseServer,
    readDataInFEServerFromQRCodeServer,
    readDataInFEServerFromCameraServer,
    readDataInFEServerFromIOServer,
    readEmergencyAbortInFEServerFromIOServer,
    clearKeyCommunicationQueuesOnAbort,
    getPostgresDatetimeFromString, sendAbortFromIOServerToQRCodeServer, blankWhiteImage,
    readHeartbeatsInFEServerFromHeartbeatServer,
    logMessageToFile,
    logMessageToConsole,
    logMessageToConsoleAndFile,
)

# From persistence (setDatabaseName is defined here, not in RedisUtils)
from persistence.Persistence import (
    setDatabaseName,
    getComponentsProducedToday,
    getComponentsProducedThisWeek,
    getComponentsProducedThisMonth,
    getDatabaseName,
)

# From utils.CosThetaPrintUtils - retained only for any remaining internal use
from utils.CosThetaPrintUtils import getCurrentTime, printBoldBlue

from frontend.frontendutils.CosThetaImageUtils import (
    createImage,
    getPixmapImage,
    resize_pixmap
)

# From statemachine
from statemachine.StateMachine import (
    MachineState,
    MachineStateMachine,
)

app = getAppInstance()
populateMonitorDimensions()  # needs to be called to ensure that a QtGui context is there for some calls to work

class AutoCompanyFrontEnd(QMainWindow):

    shutdownThreads = False
    logSource : str = getFullyQualifiedName(__file__)
    windowTitle = CosThetaConfigurator.getInstance().getWindowTitle()

    processUpdationRedisConnection: Union[Redis, None] = None
    processUpdationRedisConnected: bool = False
    connectionsUpdationRedisConnection: Union[Redis, None] = None
    connectionsUpdationRedisConnected: bool = False
    emergencyUpdationRedisConnection: Union[Redis, None] = None
    emergencyUpdationRedisConnected: bool = False
    heartbeatRedisConnection: Union[Redis, None] = None
    heartbeatRedisConnected: bool = False
    databaseUpdationRedisConnection: Union[Redis, None] = None
    databaseUpdationRedisConnected: bool = False

    # connection status of the 4 connections
    qrCodeServerConnectionStatus : bool = False
    cameraServerConnectionStatus : bool = False
    ioServerConnectionStatus : bool = False
    dbServerConnectionStatus : bool = False

    # current state of the front-end
    machineState : MachineStateMachine = MachineStateMachine()

    # Variables for storing results
    defaultTime = "1970-01-01 00:00:00"

    currentQRCode: Union[str, None] = None
    currentQRCodeForDisplay: Union[str, None] = None
    currentComponentAssemblyStartDatetime: str = defaultTime

    originalKnuckleCheckImage: Union[np.ndarray, None] = None
    processedKnuckleCheckImage: Union[np.ndarray, None] = None
    currentKnuckleCheckResult: Union[str, None] = None
    currentKnuckleCheckDatetime: str = defaultTime

    originalHubAndBottomBearingCheckImage: Union[np.ndarray, None] = None
    processedHubAndBottomBearingCheckImage: Union[np.ndarray, None] = None
    currentHubAndBottomBearingCheckResult: Union[str, None] = None
    currentHubAndBottomBearingCheckDatetime: str = defaultTime

    originalTopBearingCheckImage: Union[np.ndarray, None] = None
    processedTopBearingCheckImage: Union[np.ndarray, None] = None
    currentTopBearingCheckResult: Union[str, None] = None
    currentTopBearingCheckDatetime: str = defaultTime

    originalNutAndPlateWasherCheckImage: Union[np.ndarray, None] = None
    processedNutAndPlateWasherCheckImage: Union[np.ndarray, None] = None
    currentNutAndPlateWasherCheckResult: Union[str, None] = None
    currentNutAndPlateWasherCheckDatetime: str = defaultTime

    currentTighteningTorque1: float = 0.0
    currentTighteningTorque1CheckResult: str = notok
    currentTighteningTorque1Datetime: str = defaultTime

    currentFreeRotationsDone: str = notok
    currentFreeRotationsDatetime: str = defaultTime

    originalBunkForComponentPressCheckImage: Union[np.ndarray, None] = None
    processedBunkForComponentPressCheckImage: Union[np.ndarray, None] = None
    currentBunkForComponentPressCheckResult: Union[str, None] = None
    currentBunkForComponentPressCheckDatetime: str = defaultTime

    currentComponentPressDone: str = notok
    currentComponentPressDatetime: str = defaultTime

    originalNoBunkAfterComponentPressCheckImage: Union[np.ndarray, None] = None
    processedNoBunkAfterComponentPressCheckImage: Union[np.ndarray, None] = None
    currentNoBunkAfterComponentPressCheckResult: Union[str, None] = None
    currentNoBunkAfterComponentPressCheckDatetime: str = defaultTime

    currentTighteningTorque2: float = 0.0
    currentTighteningTorque2CheckResult: str = notok
    currentTighteningTorque2Datetime: str = defaultTime

    originalSplitPinAndWasherCheckImage: Union[np.ndarray, None] = None
    processedSplitPinAndWasherCheckImage: Union[np.ndarray, None] = None
    currentSplitPinAndWasherCheckResult: Union[str, None] = None
    currentSplitPinAndWasherCheckDatetime: str = defaultTime

    originalCapCheckImage: Union[np.ndarray, None] = None
    processedCapCheckImage: Union[np.ndarray, None] = None
    currentCapCheckResult: Union[str, None] = None
    currentCapCheckDatetime: str = defaultTime

    originalBunkForCapPressCheckImage: Union[np.ndarray, None] = None
    processedBunkForCapPressCheckImage: Union[np.ndarray, None] = None
    currentBunkForCapPressCheckResult: Union[str, None] = None
    currentBunkForCapPressCheckDatetime: str = defaultTime

    currentCapPressDone: str = notok
    currentCapPressDatetime: str = defaultTime

    currentRotationTorque1: float = 0.0
    currentRotationTorque1CheckResult: str = notok
    currentRotationTorque1Datetime: str = defaultTime

    # Variable for storing final result
    finalResult: str = notok

    emergencyButtonPressed : bool = False

    # Variables for determining how much time to show large version of ok and notok images
    TIME_TO_SHOW_OK_IMAGE_MSEC : int = int(CosThetaConfigurator.getInstance().getTimeToDisplayOkImages() * 1000)
    TIME_TO_SHOW_NOT_OK_IMAGE_MSEC : int = int(CosThetaConfigurator.getInstance().getTimeToDisplayNotOkImages() * 1000)

    # Variable for storing general remarks
    remarks : str = ""
    CURRENT_WIDTH : int = 10
    CURRENT_HEIGHT: int = 10
    RESULTS_CONTAINER_TOP : int = 10

    def __init__(self, mode : str = 'Test', username : str = 'default', role : str = 'Operator'):
        super().__init__()

        self.mode = mode
        setDatabaseName(mode=self.mode, createDB=False)
        self.username = username
        self.role = role
        AutoCompanyFrontEnd.logSource = getFullyQualifiedName(__file__, __class__)
        self.hostname = CosThetaConfigurator.getInstance().getRedisHost()
        self.port = CosThetaConfigurator.getInstance().getRedisPort()
        self.timeStarted = datetime.now()
        self.currentComponentStartTime = datetime.now()
        self.timeStartedAsString = datetime.now().strftime("%H:%M:%S")

        try:
            self.labelHeight = CosThetaConfigurator.getInstance().getLabelInitialHeight()
            self.initializeUI()
            self.splashScreenPath = f"{get_project_root()}/internalimages/SplashScreen.png"
            splash = CosThetaInitialSplashScreen(self.splashScreenPath,
                                                 CosThetaConfigurator.getInstance().getSplashScreenTime())
            splash.display()
            self.connectToRedis()
            self.showMaximized()
            QApplication.processEvents()
            self.resultsContainer.calculateAndSetIdealFontForInstructionLabel()
            self.calculateAndSetIdealFontForModeLabel()
            self.calculateAndSetIdealFontForQRCodeLabel()
            self.calculateAndSetIdealFontForDateTimeLabel()
            self.calculateAndSetIdealFontForCreatorLabel()
            self.setInitialInstruction()
            self.setQRCodeContainerDisplay(displayString="")
            self.createWorkers()
            self.resetAllDataPoints()
            self.requestQRCode()
            AutoCompanyFrontEnd.CURRENT_WIDTH = self.width()
            AutoCompanyFrontEnd.CURRENT_HEIGHT = self.height()
            AutoCompanyFrontEnd.RESULTS_CONTAINER_TOP = self.resultsContainer.geometry().top()
            self.largeImageWindow: LargeImageWindow = LargeImageWindow(self)
            self.largeImageWindow.hide()
            self.installEventFilter(self)  # Add event filter for key press events
            self.update()
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": "*****************"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": "Started FE Server"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": "*****************"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            self.setFixedWidth(AutoCompanyFrontEnd.CURRENT_WIDTH)
            self.setFixedHeight(AutoCompanyFrontEnd.CURRENT_HEIGHT)
        except Exception as e:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"Unhandled exception in __init__: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)

    def connectToRedis(self, forceRenew = False):
        if forceRenew:
            AutoCompanyFrontEnd.processUpdationRedisConnection = None
            AutoCompanyFrontEnd.processUpdationRedisConnected = False
            AutoCompanyFrontEnd.connectionsUpdationRedisConnection = None
            AutoCompanyFrontEnd.connectionsUpdationRedisConnected = False
            AutoCompanyFrontEnd.emergencyUpdationRedisConnection = None
            AutoCompanyFrontEnd.emergencyUpdationRedisConnected = False
            AutoCompanyFrontEnd.heartbeatRedisConnection = None
            AutoCompanyFrontEnd.heartbeatRedisConnected = False
            AutoCompanyFrontEnd.databaseUpdationRedisConnection = None
            AutoCompanyFrontEnd.databaseUpdationRedisConnected = False
        if not AutoCompanyFrontEnd.processUpdationRedisConnected:
            try:
                AutoCompanyFrontEnd.processUpdationRedisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                AutoCompanyFrontEnd.processUpdationRedisConnected = True
            except:
                AutoCompanyFrontEnd.processUpdationRedisConnected = False
                logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"Redis Connection status in frontend for getting pictures from camera server is {self.processUpdationRedisConnected}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.WARNING)

        if not AutoCompanyFrontEnd.connectionsUpdationRedisConnected:
            try:
                AutoCompanyFrontEnd.connectionsUpdationRedisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                AutoCompanyFrontEnd.connectionsUpdationRedisConnected = True
            except:
                AutoCompanyFrontEnd.connectionsUpdationRedisConnected = False
                logMessageToConsoleAndFile(AutoCompanyFrontEnd.connectionsUpdationRedisConnection, {"text": f"Redis Connection status in frontend for getting connection statuses from Heartbeat Server is {self.connectionsUpdationRedisConnected}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.WARNING)

        if not AutoCompanyFrontEnd.emergencyUpdationRedisConnected:
            try:
                AutoCompanyFrontEnd.emergencyUpdationRedisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                AutoCompanyFrontEnd.emergencyUpdationRedisConnected = True
            except:
                AutoCompanyFrontEnd.emergencyUpdationRedisConnected = False
                logMessageToConsoleAndFile(AutoCompanyFrontEnd.emergencyUpdationRedisConnection, {"text": f"Redis Connection status in frontend for getting emergency status from IO server is {self.emergencyUpdationRedisConnected}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.WARNING)

        if not AutoCompanyFrontEnd.heartbeatRedisConnected:
            try:
                AutoCompanyFrontEnd.heartbeatRedisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                AutoCompanyFrontEnd.heartbeatRedisConnected = True
            except:
                AutoCompanyFrontEnd.heartbeatRedisConnected = False
                logMessageToConsoleAndFile(AutoCompanyFrontEnd.heartbeatRedisConnection, {"text": f"Redis Connection status for frontend heartbeat is {self.heartbeatRedisConnected}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.WARNING)
        if not AutoCompanyFrontEnd.databaseUpdationRedisConnected:
            try:
                AutoCompanyFrontEnd.databaseUpdationRedisConnection = Redis(self.hostname, self.port, retry_on_timeout=True)
                AutoCompanyFrontEnd.databaseUpdationRedisConnected = True
            except:
                AutoCompanyFrontEnd.databaseUpdationRedisConnected = False
                logMessageToConsoleAndFile(AutoCompanyFrontEnd.databaseUpdationRedisConnection, {"text": f"Redis Connection status in frontend for updating state is {self.databaseUpdationRedisConnected}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.WARNING)


    def initializeUI(self):
        """Initialize the window and display its contents to the screen."""

        self.setWindowTitle(AutoCompanyFrontEnd.windowTitle)

        self.setupWidgets()
        self.setupMenu()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)

    def setupWidgets(self):

        cMode = self.mode.upper()
        central_widget = QGroupBox(f"IN {cMode.upper()} MODE")
        self.setCentralWidget(central_widget)
        grid_layout = QGridLayout(central_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)  # No space between widgets

        # ********************************** START MODE GROUP BOX *********************************
        modeGroupBox = QGroupBox("Mode")
        modeLayout = QHBoxLayout()
        modeLayout.setContentsMargins(0, 0, 0, 0)
        modeLayout.setSpacing(0)  # No space between widgets
        modeGroupBox.setLayout(modeLayout)

        self.modeText = self.mode.upper() + " - Knuckle, Hub, and Disc Assembly"

        self.modeLabel = QLabel(self.modeText)  # Container's title
        self.modeLabel.setContentsMargins(0,0,0,0)
        self.modeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.modeLabel.setStyleSheet(modeLabelStylesheet.format(
            QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        modeFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
        modeFont = QFont('Segoe UI', pointSize=modeFontSize, weight=QFont.Weight.Bold)
        self.modeLabel.setFont(modeFont)

        qrCodeDisplay = "QR Code : 34567 87654 90 765432 1234567 7654329876 5643219087 12346786876"
        self.qrCodeLabel = QLabel(qrCodeDisplay)  # Container's title
        self.qrCodeLabel.setContentsMargins(0,0,0,0)
        self.qrCodeLabel.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.qrCodeLabel.setStyleSheet(modeLabelStylesheet_with_no_qr_code.format(
            QColor(Qt.GlobalColor.black).name()))  # Set the background and foreground color of the container's label
        initialFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
        qrCodeLabelFont = QFont('Segoe UI', pointSize=initialFontSize, weight=QFont.Weight.Bold)
        self.qrCodeLabel.setFont(qrCodeLabelFont)

        modeLayout.addWidget(self.modeLabel, 1)
        modeLayout.addWidget(CosThetaQVLine(), 0)
        modeLayout.addWidget(self.qrCodeLabel, 1)

        grid_layout.addWidget(modeGroupBox, 0, 0, 1, 2)

        # ********************************** END MODE GROUP BOX *********************************

        # self.setQRCodeContainerDisplay(displayString="")

        # ********************************** START CONNECTION GROUP BOX *********************************

        self._statusFont = QFont('Courier', pointSize=int(20), weight=QFont.Weight.Bold)
        self.cameraServerConnectionStatusContainer = ToggleMessageContainer(okText =f"Camera connected",
                                                                            notokText = f"Camera not connected",
                                                                            okStyleSheet = okLabelStylesheet, notokStyleSheet = notokLabelStylesheet,
                                                                            font = self._statusFont, okforegroundColor = QColor(Qt.GlobalColor.white),
                                                                            notokforegroundColor = QColor(Qt.GlobalColor.white),
                                                                            minimumWidth = 50,
                                                                            labelHeight = self.labelHeight, name='CAMERACONNECTION', forceUseOfFontSize=13)
        self.ioServerConnectionStatusContainer = ToggleMessageContainer(okText =f"I/O Module connected",
                                                                        notokText = f"I/O Module not connected",
                                                                        okStyleSheet = okLabelStylesheet, notokStyleSheet = notokLabelStylesheet,
                                                                        font = self._statusFont, okforegroundColor = QColor(Qt.GlobalColor.white),
                                                                        notokforegroundColor = QColor(Qt.GlobalColor.white),
                                                                        minimumWidth = 50,
                                                                        labelHeight = self.labelHeight, name='IOCONNECTION',
                                                                        forceUseOfFontSize=13)
        self.dbServerConnectionStatusContainer = ToggleMessageContainer(okText =f"Database connected",
                                                                        notokText = f"Database not connected",
                                                                        okStyleSheet = okLabelStylesheet, notokStyleSheet = notokLabelStylesheet,
                                                                        font = self._statusFont, okforegroundColor = QColor(Qt.GlobalColor.white),
                                                                        notokforegroundColor = QColor(Qt.GlobalColor.white),
                                                                        minimumWidth = 50,
                                                                        labelHeight = self.labelHeight, name='DBCONNECTION',
                                                                        forceUseOfFontSize=13)
        self.qrCodeServerConnectionStatusContainer = ToggleMessageContainer(okText =f"QRCode Scanner connected",
                                                                            notokText = f"QRCode Scanner not connected",
                                                                            okStyleSheet = okLabelStylesheet, notokStyleSheet = notokLabelStylesheet,
                                                                            font = self._statusFont, okforegroundColor = QColor(Qt.GlobalColor.white),
                                                                            notokforegroundColor = QColor(Qt.GlobalColor.white),
                                                                            minimumWidth = 50,
                                                                            labelHeight = self.labelHeight, name='QRCODE',
                                                                            forceUseOfFontSize=13)

        connectionStatusesGroupBox = QGroupBox("CONNECTION STATUS OF DEVICES")
        connectionStatusLayout = QHBoxLayout()
        connectionStatusesGroupBox.setLayout(connectionStatusLayout)
        connectionStatusLayout.setContentsMargins(0, 0, 0, 0)
        connectionStatusLayout.setSpacing(0)  # No space between widgets

        connectionStatusLayout.addWidget(self.cameraServerConnectionStatusContainer, 1)
        connectionStatusLayout.addWidget(CosThetaQVLine(), 0)
        connectionStatusLayout.addWidget(self.qrCodeServerConnectionStatusContainer, 1)
        connectionStatusLayout.addWidget(CosThetaQVLine(), 0)

        connectionStatusLayout.addWidget(self.ioServerConnectionStatusContainer, 1)
        connectionStatusLayout.addWidget(CosThetaQVLine(), 0)
        connectionStatusLayout.addWidget(self.dbServerConnectionStatusContainer, 1)

        grid_layout.addWidget(connectionStatusesGroupBox, 1, 0, 1, 2)

        # ********************************** END CONNECTION GROUP BOX *********************************

        self.resultsContainer = CosThetaResultsContainer()

        grid_layout.addWidget(self.resultsContainer, 2, 0, 1, 2)

        # ********************************** START GENERAL INFO GROUP BOX *********************************

        self.dateTimeFont = QFont('Segoe UI', pointSize=int(12), weight=QFont.Weight.Bold)
        self.dateTimeText = (
            'Today is {}. Started: {}; Running time: {}    '
            '; Components produced : This week - {}; This month - {}\n'
            'User: {}; Current component processing time: {}    '
            '; Components produced today - {}'
        )
        currentComponentProcessingStarted : bool = (AutoCompanyFrontEnd.currentQRCode is not None) and (AutoCompanyFrontEnd.currentQRCode != "")
        currentDatetimeText = self.dateTimeText.format(datetime.now().strftime('%d-%m-%Y %a'),
                                                       self.timeStartedAsString,
                                                       (':'.join(str(datetime.now() - self.timeStarted).split(':')[:3])).split('.')[0],
                                                       0,
                                                       0,
                                                       f'{self.username} - {self.role}',
                                                       (':'.join(str(datetime.now() - self.currentComponentStartTime).split(':')[:3])).split('.')[0] if currentComponentProcessingStarted else "0",
                                                       0)
        # printLight(currentDatetimeText)
        self.dateTimeStatus = SimpleMessageContainer(
            text=currentDatetimeText,
            styleSheet = outcomeLabelStylesheet,
            font = self.dateTimeFont, foregroundColor = QColor(Qt.GlobalColor.white).name(),
            minimumWidth = 50, name='DateTimeStatus')
        self.dateTimeStatus.setAlignment(Qt.AlignmentFlag.AlignLeft)
        general_info_cell_frame_left = QFrame()
        general_info_layout_left = QHBoxLayout(general_info_cell_frame_left)
        general_info_layout_left.setContentsMargins(0, 0, 0, 0)
        general_info_layout_left.setSpacing(0)  # No space between widgets
        general_info_layout_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        general_info_layout_left.addWidget(self.dateTimeStatus)

        self.creatorString = "Created by CosTheta Technologies and Auto Company"
        self.creatorFont = QFont('Segoe UI', pointSize=int(12), weight=QFont.Weight.Bold, italic=True)
        self.creatorFont.setItalic(True)
        self.creatorStatus = SimpleMessageContainer(text = self.creatorString,
                                                    styleSheet = companyNameStylesheet.format(QColor(Qt.GlobalColor.white).name()),
                                                    font = self.creatorFont, foregroundColor = QColor(Qt.GlobalColor.white).name(), minimumWidth = 50, name='Creator Status')
        self.creatorStatus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.creatorStatus.setWordWrap(False)

        # --- Auto Company logo ---
        self.AutoCompanyLogoLabel = QLabel()
        self.AutoCompanyLogoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.AutoCompanyLogoLabel.setContentsMargins(2, 1, 2, 1)
        self.AutoCompanyLogoLabel.setScaledContents(False)
        _al_logo_path = f"{get_project_root()}/internalimages/AutoCompany_logo.png"
        _al_pixmap = QPixmap(_al_logo_path)
        if not _al_pixmap.isNull():
            self.AutoCompanyLogoLabel.setPixmap(
                _al_pixmap.scaledToHeight(int(self.labelHeight * 0.85), Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.AutoCompanyLogoLabel.setText("AL")

        # --- CosTheta logo ---
        self.cosThetaLogoLabel = QLabel()
        self.cosThetaLogoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cosThetaLogoLabel.setContentsMargins(2, 1, 2, 1)
        self.cosThetaLogoLabel.setScaledContents(False)
        _ct_logo_path = f"{get_project_root()}/internalimages/costheta_logo.png"
        _ct_pixmap = QPixmap(_ct_logo_path)
        if not _ct_pixmap.isNull():
            self.cosThetaLogoLabel.setPixmap(
                _ct_pixmap.scaledToHeight(int(self.labelHeight * 0.85), Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.cosThetaLogoLabel.setText("CT")

        general_info_cell_frame_right = QFrame()
        general_info_layout_right = QHBoxLayout(general_info_cell_frame_right)
        general_info_layout_right.setContentsMargins(0, 0, 0, 0)
        general_info_layout_right.setSpacing(4)
        general_info_layout_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        general_info_layout_right.addWidget(self.AutoCompanyLogoLabel)
        general_info_layout_right.addWidget(self.creatorStatus)
        general_info_layout_right.addWidget(self.cosThetaLogoLabel)

        generalInfoGroupBox = QGroupBox("DATE / RUNNING DURATION PANEL")
        general_info_layout = QHBoxLayout()
        generalInfoGroupBox.setLayout(general_info_layout)
        general_info_layout.setContentsMargins(0, 0, 0, 0)
        general_info_layout.setSpacing(0)  # No space between widgets
        general_info_layout.addWidget(self.dateTimeStatus, 2)
        general_info_layout.addWidget(CosThetaQVLine(),0)
        general_info_layout.addWidget(general_info_cell_frame_right, 1)

        grid_layout.addWidget(generalInfoGroupBox, 3, 0, 1, 2)

        # ********************************** END GENERAL INFO GROUP BOX *********************************

        # ********************************** DEFINE VERTICAL SPACE OF EACH ROW *********************************

        grid_layout.setRowStretch(0, 1)  # Row 1
        grid_layout.setRowStretch(1, 1)  # Row 2
        grid_layout.setRowStretch(2, 7)  # Row 3 (7 times the stretch of others)
        grid_layout.setRowStretch(3, 1)  # Row 4
        # Add a vertical spacer to push rows and show stretch effect
        grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding), 4, 0, 1, 2)

        self.update()

    # Call this after self.show(), then QApplication.processEvents(), then self.resultsContainer.calculateAndSetIdealFontForInstructionLabel()
    def calculateAndSetIdealFontForModeLabel(self):
        currentModeFont = self.modeLabel.font()
        currentFontPointSize = currentModeFont.pointSize()
        currentModeFont.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(currentModeFont)
        labelTextRect = metrics.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignLeft, f"       {self.modeLabel.text()}       ")
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        modeLabelWidth = self.modeLabel.width()
        modeLabelHeight = self.modeLabel.height()
        reductionFactor = min(modeLabelWidth * 1.0 / textWidth,
                              modeLabelHeight * 1.0 / textHeight) * 0.95
        fontSize = int(reductionFactor * currentFontPointSize)
        currentModeFont.setPointSize(fontSize)
        self.modeLabel.setFont(currentModeFont)

    # Call this after self.show(), then QApplication.processEvents(), then self.resultsContainer.calculateAndSetIdealFontForInstructionLabel()
    def calculateAndSetIdealFontForQRCodeLabel(self):
        currentQRCodeFont = self.qrCodeLabel.font()
        currentFontPointSize = currentQRCodeFont.pointSize()
        currentQRCodeFont.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(currentQRCodeFont)
        labelTextRect = metrics.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignCenter, f"   {self.qrCodeLabel.text()}   ")
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        qrCodeLabelWidth = self.qrCodeLabel.width()
        qrCodeLabelHeight = self.qrCodeLabel.height()
        reductionFactor = min(qrCodeLabelWidth * 1.0 / textWidth,
                              qrCodeLabelHeight * 1.0 / textHeight) * 0.95
        fontSize = int(reductionFactor * currentFontPointSize)
        currentQRCodeFont.setPointSize(fontSize)
        self.qrCodeLabel.setFont(currentQRCodeFont)

    def calculateAndSetIdealFontForDateTimeLabel(self):
        currentDateTimeFont = self.dateTimeStatus.font()
        currentFontPointSize = currentDateTimeFont.pointSize()
        currentDateTimeFont.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(currentDateTimeFont)

        labelTextRect = metrics.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignLeft, f"   {self.dateTimeStatus.getText()}   ")
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        datetimeLabelWidth = self.dateTimeStatus.width()
        datetimeLabelHeight = self.dateTimeStatus.height()
        reductionFactor = min(datetimeLabelWidth * 1.0 / textWidth,
                              datetimeLabelHeight * 1.0 / textHeight) * 0.8
        fontSize = int(reductionFactor * currentFontPointSize)
        currentDateTimeFont.setPointSize(fontSize)
        self.dateTimeStatus.setFont(currentDateTimeFont)

    def calculateAndSetIdealFontForCreatorLabel(self):
        currentCreatorFont = self.creatorStatus.font()
        currentFontPointSize = currentCreatorFont.pointSize()
        currentCreatorFont.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(currentCreatorFont)

        labelTextRect = metrics.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignLeft, f"   {self.creatorStatus.getText()}   ")
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        creatorLabelWidth = self.creatorStatus.width()
        creatorLabelHeight = self.creatorStatus.height()
        reductionFactor = min(creatorLabelWidth * 1.0 / textWidth,
                              creatorLabelHeight * 1.0 / textHeight) * 0.8
        fontSize = int(reductionFactor * currentFontPointSize)
        currentCreatorFont.setPointSize(fontSize)
        self.creatorStatus.setFont(currentCreatorFont)

    def setupMenu(self):
        """Set up menubar."""
        # Create actions for mode menu
        changePassword_act = QAction(' Change Own Password ', self)
        changePassword_act.setShortcut(' Ctrl+Alt+P ')
        changePassword_act.triggered.connect(lambda : changePasswordForSelf(currentUser=self.username, currentRole=self.role))

        exit_act = QAction(' Exit ', self)
        exit_act.setShortcut(' Ctrl+Alt+E ')
        exit_act.triggered.connect(self.goToClose)

        addnewuser_act = QAction(' Add New User ', self)
        addnewuser_act.setShortcut(' Ctrl+Alt+N ')
        addnewuser_act.triggered.connect(lambda : createAccount(currentUser=self.username, currentRole=self.role))

        manageuserpasswords_act = QAction(' Manage Other Users Passwords ', self)
        manageuserpasswords_act.setShortcut(' Ctrl+Alt+M ')
        manageuserpasswords_act.triggered.connect(lambda : changePassword(currentUser=self.username, currentRole=self.role))

        changerole_act = QAction(' Change User Role ', self)
        changerole_act.setShortcut(' Ctrl+Alt+R ')
        changerole_act.triggered.connect(lambda : changeRole(currentUser=self.username, currentRole=self.role))

        activateuser_act = QAction(' Activate an Inactive User ', self)
        activateuser_act.setShortcut(' Ctrl+Alt+C ')
        activateuser_act.triggered.connect(lambda : activateUser(currentUser=self.username, currentRole=self.role))

        inactivateuser_act = QAction(' Inactivate User ', self)
        inactivateuser_act.setShortcut(' Ctrl+Alt+I ')
        inactivateuser_act.triggered.connect(lambda : inactivateUser(currentUser=self.username, currentRole=self.role))

        createreportbymodelname_act = QAction(' Create Production Report By Model Name', self)
        createreportbymodelname_act.setShortcut(' Ctrl+Alt+S ')
        createreportbymodelname_act.triggered.connect(lambda : createProductionReportByModelName())

        createreportbymodelnameforperiod_act = QAction(' Create Production Report By Model Name For a Period', self)
        createreportbymodelnameforperiod_act.setShortcut(' Ctrl+Alt+F ')
        createreportbymodelnameforperiod_act.triggered.connect(lambda : createProductionReportByModelNameAndDateLimits())

        createreportbymodelnamefortoday_act = QAction(' Create Production Report By Model Name For Today', self)
        createreportbymodelnamefortoday_act.setShortcut(' Ctrl+Alt+A ')
        createreportbymodelnamefortoday_act.triggered.connect(lambda : createProductionReportOfTodayByModelName())

        createreportforaperiodforallmodels_act = QAction(' Create Production Report for a Period for all Models', self)
        createreportforaperiodforallmodels_act.setShortcut(' Ctrl+Alt+D ')
        createreportforaperiodforallmodels_act.triggered.connect(lambda : createProductionReportByDateLimits())

        createreportfortodayforallmodels_act = QAction(' Create Full Production Report for Today for all Models', self)
        createreportfortodayforallmodels_act.setShortcut(' Ctrl+Alt+D ')
        createreportfortodayforallmodels_act.triggered.connect(lambda : createProductionReportOfToday())

        info_act = QAction(' About ', self)
        info_act.setShortcut(' Ctrl+Alt+A ')
        info_act.triggered.connect(self.goToInfo)

        help_act = QAction(' Help ', self)
        help_act.setShortcut(' Ctrl+Alt+H ')
        help_act.triggered.connect(self.goToHelp)

        # Add Manual Abort action
        manual_abort_act = QAction(' (Z)Manual Abort ', self)
        manual_abort_act.setShortcut('Ctrl+Alt+Z')
        manual_abort_act.triggered.connect(self.manualAbort)

        # Create menubar
        menu_bar = self.menuBar()
        # # For MacOS users, places menu bar in main window
        menu_bar.setNativeMenuBar(False)
        #
        # # Create Actions menu and add actions
        action_menu = menu_bar.addMenu(' Actions ')
        action_menu.addAction(exit_act)
        action_menu.addAction(changePassword_act)
        action_menu.addSeparator()
        action_menu.addAction(manual_abort_act)

        # Create Admin menu and add actions
        admin_menu = menu_bar.addMenu(' Administration ')
        admin_menu.addAction(addnewuser_act)
        admin_menu.addAction(manageuserpasswords_act)
        admin_menu.addAction(changerole_act)

        # Create Activate/Inactivate menu and add actions
        activate_inactivate_menu = menu_bar.addMenu(' Activate / Inactivate ')
        activate_inactivate_menu.addAction(activateuser_act)
        activate_inactivate_menu.addAction(inactivateuser_act)

        # Create Report menu and add actions
        send_report_menu = menu_bar.addMenu(' Report ')
        send_report_menu.addAction(createreportbymodelname_act)
        send_report_menu.addAction(createreportbymodelnameforperiod_act)
        send_report_menu.addAction(createreportbymodelnamefortoday_act)
        send_report_menu.addSeparator()
        send_report_menu.addAction(createreportforaperiodforallmodels_act)
        send_report_menu.addAction(createreportfortodayforallmodels_act)
        send_report_menu.addSeparator()

        # Create Information menu and add actions
        info_menu = menu_bar.addMenu(' Information ')
        info_menu.addAction(help_act)
        info_menu.addAction(info_act)

        # Create Machine Settings menu and add actions
        machine_settings_act = QAction(' Update Machine Settings ', self)
        machine_settings_act.setShortcut(' Ctrl+Alt+U ')
        machine_settings_act.triggered.connect(lambda: updateMachineSettingsDialog())

        machine_settings_menu = menu_bar.addMenu(' Machine Settings ')
        machine_settings_menu.addAction(machine_settings_act)

        if self.role == "Operator":
            addnewuser_act.setDisabled(True)
            manageuserpasswords_act.setDisabled(True)
            changerole_act.setDisabled(True)
            activateuser_act.setDisabled(True)
            inactivateuser_act.setDisabled(True)
            machine_settings_act.setDisabled(True)
        self.update()

    @Slot()
    def hideLargeImageWindow(self):
        self.largeImageWindow.hide()

    def stopAndCleanThread(self, thread : QThread):
        try:
            if thread and thread.isRunning():
                thread.quit()
                thread.wait()
                thread.deleteLater()
        except:
            pass

    def goToClose(self):
        # print("Entered goToClose()")
        ret = QMessageBox.question(self, 'Close Application', "Are you sure you want to exit the application ?",
                                   buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, defaultButton=QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.No:
            return
        elif ret == QMessageBox.StandardButton.Yes:
            try:
                pass
            except:
                pass

            AutoCompanyFrontEnd.shutdownThreads = True
            sendStopToAll()
            endSplash = CosThetaExitingSplashScreen(self.splashScreenPath,
                                                 CosThetaConfigurator.getInstance().getEndScreenTime())
            if self.largeImageWindow is not None:
                try:
                    self.largeImageWindow.close()
                except Exception as e:
                    logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"Could not close largeImageWindow: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.WARNING)
            endSplash.display()
            try:
                self.heartbeatWorker.stop()
                self.stopAndCleanThread(self.heartbeatThread)
            except Exception as e:
                pass
            self.stopAndCleanThread(self.timeDurationUpdateThread)
            self.stopAndCleanThread(self.getQRCodeThread)
            self.stopAndCleanThread(self.getPictureAndResultThread)
            self.stopAndCleanThread(self.getTorqueReadingAndResultThread)
            self.stopAndCleanThread(self.connectionStatusUpdateThread)
            self.stopAndCleanThread(self.emergencyAbortStatusUpdateThread)
            self.close()
        return

    def goToInfo(self):
        # print("Entered goToInfo()")
        QMessageBox.question(self, 'Information', "Software Version: v 1.0\n\n" +
                             "This application is built by CosTheta Technologies Pvt Ltd. " +
                             "All copyright belongs to CosTheta Technologies Pvt Ltd.\n\n" +
                             "This application does quality inspection and recording of \n" +
                             "a) capsules for 3 bottles on right and left disc\n" +
                             "b) acceptance and rejection of bottles\n", QMessageBox.StandardButton.Ok)
        return

    def goToHelp(self):
        # print("Entered goToHelp()")
        QMessageBox.question(self, 'Help about using the menu', "When any of the menu choices are being used, \n" +
                             "the remaining menu items will be clickable.\n\n" +
                             "However, clicking on any other menu item will not be acted upon \n" +
                             "by the system till the currently-in-use menu action is completed \n" +
                             "or cancelled.\n", QMessageBox.StandardButton.Ok)
        return

    def closeEvent(self, event):
        sp = event.spontaneous()
        if sp:
            event.ignore()
            self.goToClose()
        else:
            event.accept()
            try:
                pass
            except:
                pass
            AutoCompanyFrontEnd.shutdownThreads = True
            sendStopToAll()
            endSplash = CosThetaExitingSplashScreen(self.splashScreenPath,
                                                 CosThetaConfigurator.getInstance().getEndScreenTime())
            if self.largeImageWindow is not None:
                try:
                    self.largeImageWindow.close()
                except Exception as e:
                    pass
            endSplash.display()
            try:
                self.heartbeatWorker.stop()
                self.stopAndCleanThread(self.heartbeatThread)
            except Exception as e:
                pass
            self.stopAndCleanThread(self.timeDurationUpdateThread)
            self.stopAndCleanThread(self.getQRCodeThread)
            self.stopAndCleanThread(self.getPictureAndResultThread)
            self.stopAndCleanThread(self.getTorqueReadingAndResultThread)
            self.stopAndCleanThread(self.connectionStatusUpdateThread)
            self.stopAndCleanThread(self.emergencyAbortStatusUpdateThread)
            self.close()

    # ********************************************

    def resetAllDataPoints(self):

        defaultTime = "1970-01-01 00:00:00"

        AutoCompanyFrontEnd.currentQRCode = None
        AutoCompanyFrontEnd.currentQRCodeForDisplay = None
        AutoCompanyFrontEnd.currentComponentAssemblyStartDatetime = defaultTime

        AutoCompanyFrontEnd.originalKnuckleCheckImage = None
        AutoCompanyFrontEnd.processedKnuckleCheckImage = None
        AutoCompanyFrontEnd.currentKnuckleCheckResult = None
        AutoCompanyFrontEnd.currentKnuckleCheckDatetime = defaultTime

        AutoCompanyFrontEnd.originalHubAndBottomBearingCheckImage = None
        AutoCompanyFrontEnd.processedHubAndBottomBearingCheckImage = None
        AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult = None
        AutoCompanyFrontEnd.currentHubAndBottomBearingCheckDatetime = defaultTime

        AutoCompanyFrontEnd.originalTopBearingCheckImage = None
        AutoCompanyFrontEnd.processedTopBearingCheckImage = None
        AutoCompanyFrontEnd.currentTopBearingCheckResult = None
        AutoCompanyFrontEnd.currentTopBearingCheckDatetime = defaultTime

        AutoCompanyFrontEnd.originalNutAndPlateWasherCheckImage = None
        AutoCompanyFrontEnd.processedNutAndPlateWasherCheckImage = None
        AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult = None
        AutoCompanyFrontEnd.currentNutAndPlateWasherCheckDatetime = defaultTime

        AutoCompanyFrontEnd.currentTighteningTorque1 = 0.0
        AutoCompanyFrontEnd.currentTighteningTorque1CheckResult = notok
        AutoCompanyFrontEnd.currentTighteningTorque1Datetime = defaultTime

        AutoCompanyFrontEnd.currentFreeRotationsDone = False
        AutoCompanyFrontEnd.currentFreeRotationsDatetime = defaultTime

        AutoCompanyFrontEnd.originalBunkForComponentPressCheckImage = None
        AutoCompanyFrontEnd.processedBunkForComponentPressCheckImage = None
        AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult = None
        AutoCompanyFrontEnd.currentBunkForComponentPressCheckDatetime = defaultTime

        AutoCompanyFrontEnd.currentComponentPressDone = False
        AutoCompanyFrontEnd.currentComponentPressDatetime = defaultTime

        AutoCompanyFrontEnd.originalNoBunkAfterComponentPressCheckImage = None
        AutoCompanyFrontEnd.processedNoBunkAfterComponentPressCheckImage = None
        AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult = None
        AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckDatetime = defaultTime

        AutoCompanyFrontEnd.currentTighteningTorque2 = 0.0
        AutoCompanyFrontEnd.currentTighteningTorque2CheckResult = notok
        AutoCompanyFrontEnd.currentTighteningTorque2Datetime = defaultTime

        AutoCompanyFrontEnd.originalSplitPinAndWasherCheckImage = None
        AutoCompanyFrontEnd.processedSplitPinAndWasherCheckImage = None
        AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult = None
        AutoCompanyFrontEnd.currentSplitPinAndWasherCheckDatetime = defaultTime

        AutoCompanyFrontEnd.originalCapCheckImage = None
        AutoCompanyFrontEnd.processedCapCheckImage = None
        AutoCompanyFrontEnd.currentCapCheckResult = None
        AutoCompanyFrontEnd.currentCapCheckDatetime = defaultTime

        AutoCompanyFrontEnd.originalBunkForCapPressCheckImage = None
        AutoCompanyFrontEnd.processedBunkForCapPressCheckImage = None
        AutoCompanyFrontEnd.currentBunkForCapPressCheckResult = None
        AutoCompanyFrontEnd.currentBunkForCapPressCheckDatetime = defaultTime

        AutoCompanyFrontEnd.currentCapPressDone = notok
        AutoCompanyFrontEnd.currentCapPressDatetime = defaultTime

        AutoCompanyFrontEnd.currentRotationTorque1 = 0.0
        AutoCompanyFrontEnd.currentRotationTorque1CheckResult = notok
        AutoCompanyFrontEnd.currentRotationTorque1Datetime = defaultTime

        # Variable for storing final result
        AutoCompanyFrontEnd.finalResult = notok

        # Variable for storing general remarks
        AutoCompanyFrontEnd.remarks = ""


    def getCurrentState(self):
        return AutoCompanyFrontEnd.machineState.getCurrentState()

    def setCurrentState(self, newState : MachineState):
        AutoCompanyFrontEnd.machineState.setCurrentState(newState=newState)
        logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"The new state of the machine is {AutoCompanyFrontEnd.machineState.getCurrentState()}"}, AutoCompanyFrontEnd.logSource)

    def printStateOfAllSeekers(self):
        logMessageToConsole(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"{GetQRCodeWorker.seekQRCode = },\n {GetPictureAndResultWorker.seekPictureAndResult = },\n {GetTorqueReadingPlusCapPressAndResultWorker.seekTorqueReadingPlusCapPressAndResult = }"}, AutoCompanyFrontEnd.logSource)

    # ********************************************

    def createWorkers(self):
        self.createTimeDurationUpdateWorker()
        self.createGetQRCodeWorker()
        self.createGetPictureAndResultWorker()
        self.createGetTorqueReadingPlusCapPressAndResultWorker()
        self.createConnectionStatusUpdateWorker()
        self.createEmergencyAbortUpdateWorker()
        self.createHeartbeatWorker()

    # ********************************************

    def createHeartbeatWorker(self):
        self.heartbeatWorker = HeartbeatSenderWorker()
        self.heartbeatThread = QThread()
        self.heartbeatWorker.moveToThread(self.heartbeatThread)
        self.heartbeatThread.started.connect(self.heartbeatWorker.start)
        self.heartbeatThread.start()

    # ********************************************

    def createTimeDurationUpdateWorker(self):
        self.timeDurationUpdateWorker = TimeDurationUpdateWorker()
        self.timeDurationUpdateThread = QThread()
        self.timeDurationUpdateWorker.doTimeDurationUpdate.connect(self.updateTimeDurationStatus)
        self.timeDurationUpdateThread.finished.connect(self.timeDurationUpdateThread.deleteLater)
        self.timeDurationUpdateWorker.moveToThread(self.timeDurationUpdateThread)
        self.timeDurationUpdateThread.start()

    @Slot()
    def updateTimeDurationStatus(self):
        currentComponentProcessingStarted : bool = (AutoCompanyFrontEnd.currentQRCode is not None) and (AutoCompanyFrontEnd.currentQRCode != "")
        # Fetch production counts safely — a DB hiccup must never crash the status update loop
        try:
            _db = getDatabaseName()
            _countToday = getComponentsProducedToday(_db)
        except Exception:
            _countToday = 0
        try:
            _db = getDatabaseName()
            _countWeek = getComponentsProducedThisWeek(_db)
        except Exception:
            _countWeek = 0
        try:
            _db = getDatabaseName()
            _countMonth = getComponentsProducedThisMonth(_db)
        except Exception:
            _countMonth = 0
        currentDatetimeText = self.dateTimeText.format(
            datetime.now().strftime('%d-%m-%Y %a'),
            self.timeStartedAsString,
            (':'.join(str(datetime.now() - self.timeStarted).split(':')[:3])).split('.')[0],
            _countWeek,
            _countMonth,
            f'{self.username} - {self.role}',
            (':'.join(str(datetime.now() - self.currentComponentStartTime).split(':')[:3])).split('.')[0] if currentComponentProcessingStarted else "0",
            _countToday,
        )
        self.dateTimeStatus.updateStatus(currentDatetimeText)

    # ********************************************

    def createConnectionStatusUpdateWorker(self):
        self.connectionStatusUpdateWorker = ConnectionStatusUpdateWorker()
        self.connectionStatusUpdateThread = QThread()
        self.connectionStatusUpdateWorker.doConnectionStatusUpdate.connect(self.updateConnectionStatus)
        self.connectionStatusUpdateThread.finished.connect(self.connectionStatusUpdateThread.deleteLater)
        self.connectionStatusUpdateWorker.moveToThread(self.connectionStatusUpdateThread)
        self.connectionStatusUpdateThread.start()

    @Slot()
    def updateConnectionStatus(self):
        cameraServerStatus, qrCodeServerStatus, ioServerStatus, dbServerStatus = (
            readHeartbeatsInFEServerFromHeartbeatServer(AutoCompanyFrontEnd.connectionsUpdationRedisConnection,
                                                        block=None))   # ← non-blocking: if no data, return False immediately
        AutoCompanyFrontEnd.cameraServerConnectionStatus = cameraServerStatus
        AutoCompanyFrontEnd.qrCodeServerConnectionStatus = qrCodeServerStatus
        AutoCompanyFrontEnd.ioServerConnectionStatus = ioServerStatus
        AutoCompanyFrontEnd.dbServerConnectionStatus = dbServerStatus
        self.cameraServerConnectionStatusContainer.updateStatus(AutoCompanyFrontEnd.cameraServerConnectionStatus)
        self.qrCodeServerConnectionStatusContainer.updateStatus(AutoCompanyFrontEnd.qrCodeServerConnectionStatus)
        self.ioServerConnectionStatusContainer.updateStatus(AutoCompanyFrontEnd.ioServerConnectionStatus)
        self.dbServerConnectionStatusContainer.updateStatus(AutoCompanyFrontEnd.dbServerConnectionStatus)

    # ********************************************

    def createEmergencyAbortUpdateWorker(self):
        self.emergencyAbortUpdateWorker = EmergencyStatusMonitoringWorker()
        self.emergencyAbortStatusUpdateThread = QThread()
        self.emergencyAbortUpdateWorker.doEmergencyPressedUpdate.connect(self.updateEmergencyAbortPressed)
        self.emergencyAbortStatusUpdateThread.finished.connect(self.emergencyAbortStatusUpdateThread.deleteLater)
        self.emergencyAbortUpdateWorker.moveToThread(self.emergencyAbortStatusUpdateThread)
        self.emergencyAbortStatusUpdateThread.start()

    @Slot()
    def updateEmergencyAbortPressed(self):
        emergencyPressed = readEmergencyAbortInFEServerFromIOServer(AutoCompanyFrontEnd.emergencyUpdationRedisConnection,
                                                                    block=None)   # ← non-blocking
        if not emergencyPressed:
            return
        AutoCompanyFrontEnd.emergencyButtonPressed = True
        logMessageToConsoleAndFile(AutoCompanyFrontEnd.emergencyUpdationRedisConnection, {"text": "About to call doFinalProcessing() from updateEmergencyAbortPressed()"}, AutoCompanyFrontEnd.logSource)
        self.doFinalProcessing()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.modifiers() == (
                    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier) and event.key() == Qt.Key.Key_Z:
                self.manualAbort()
                return True
        return super().eventFilter(obj, event)

    def manualAbort(self):
        confirmed : str = getConfirmation(message="Aborting manually. Ensure you have pressed Emergency button on the machine.")
        ok : bool = (confirmed.strip().upper() == "OK")
        if not ok:
            return
        sendAbortFromIOServerToQRCodeServer(AutoCompanyFrontEnd.processUpdationRedisConnection)
        try:
            QThread.msleep(200)
        except:
            pass
        clearKeyCommunicationQueuesOnAbort()
        AutoCompanyFrontEnd.emergencyButtonPressed = True
        logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": "About to call doFinalProcessing() from manualAbort()"}, AutoCompanyFrontEnd.logSource)
        self.doFinalProcessing()

# ********************************************

    def requestQRCode(self):
        GetQRCodeWorker.seekQRCode = True

    def createGetQRCodeWorker(self):
        self.getQRCodeWorker = GetQRCodeWorker()
        self.getQRCodeThread = QThread()
        self.getQRCodeWorker.moveToThread(self.getQRCodeThread)
        self.getQRCodeWorker.gotQRCode.connect(self.updateQRCodeDisplay)
        self.getQRCodeThread.finished.connect(self.getQRCodeThread.deleteLater)
        self.getQRCodeThread.start()

    def setQRCodeContainerDisplay(self, displayString : str = ""):
        displayString = displayString.strip()
        if (displayString is None) or (displayString == ""):
            self.qrCodeLabel.setStyleSheet(modeLabelStylesheet_with_no_qr_code.format(
                QColor(Qt.GlobalColor.black).name()))
            self.qrCodeLabel.setText(f"QR CODE : ")
        else:
            self.qrCodeLabel.setStyleSheet(modeLabelStylesheet_with_qr_code.format(
                QColor(Qt.GlobalColor.black).name()))
            self.qrCodeLabel.setText(f"QR CODE : {displayString}")

    @Slot()
    def updateQRCodeDisplay(self):
        displayString = AutoCompanyFrontEnd.currentQRCodeForDisplay
        self.hideLargeImageWindow()
        self.setQRCodeContainerDisplay(displayString=displayString)
        self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE)
        self.requestPictureAndResult()
        self.resultsContainer.setInstruction(self.machineState.getCurrentInstruction())
        self.currentComponentStartTime = datetime.now()

    # ********************************************

    @Slot()
    def setInitialInstruction(self):
        self.resultsContainer.setInstruction(self.machineState.getCurrentInstruction())

    # ********************************************

    def requestPictureAndResult(self):
        GetPictureAndResultWorker.seekPictureAndResult = True

    def createGetPictureAndResultWorker(self):
        self.getPictureAndResultWorker = GetPictureAndResultWorker()
        self.getPictureAndResultThread = QThread()
        self.getPictureAndResultWorker.moveToThread(self.getPictureAndResultThread)
        self.getPictureAndResultWorker.gotPictureAndResult.connect(self.updatePictureContainer)
        self.getPictureAndResultThread.finished.connect(self.getPictureAndResultThread.deleteLater)
        self.getPictureAndResultThread.start()

    def showATemporaryLargeImage(self, anImage : Union[np.ndarray, None], result : str | None):
        # printBoldYellow(f"Result received is {result}")
        if anImage is None:
            return
        self.largeImageWindow.setPixmap(anyTypeOfImage=anImage, result=result)
        self.show()
        self.raise_()
        self.activateWindow()
        self.largeImageWindow.show()
        self.largeImageWindow.raise_()
        self.largeImageWindow.activateWindow()
        if (result is not None) or (f"{result}".lower() == ok.lower()):
            QTimer.singleShot(AutoCompanyFrontEnd.TIME_TO_SHOW_OK_IMAGE_MSEC, self.hideLargeImageWindow)
        else:
            QTimer.singleShot(AutoCompanyFrontEnd.TIME_TO_SHOW_NOT_OK_IMAGE_MSEC, self.hideLargeImageWindow)

    @Slot()
    def updatePictureContainer(self):
        currentState = AutoCompanyFrontEnd.machineState.getCurrentState()

        stateHandlerMap = {
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE: self._handleKnuckleCheck,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING: self._handleHubAndBottomBearingCheck,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING: self._handleTopBearingCheck,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER: self._handleNutAndPlateWasherCheck,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS: self._handleBunkForComponentPress,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK: self._handleNoBunkAfterComponentPress,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER: self._handleSplitPinAndWasherCheck,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP: self._handleCapCheck,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS: self._handleBunkCheckForCapPress,
        }

        handler = stateHandlerMap.get(currentState)
        if handler:
            handler()

        self.resultsContainer.setInstruction(self.machineState.getCurrentInstruction())

    def _handleKnuckleCheck(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedKnuckleCheckImage,
            result=AutoCompanyFrontEnd.currentKnuckleCheckResult
        )
        self.resultsContainer.setKnuckleCheckData(
            value=AutoCompanyFrontEnd.processedKnuckleCheckImage,
            result=AutoCompanyFrontEnd.currentKnuckleCheckResult
        )
        if AutoCompanyFrontEnd.currentKnuckleCheckResult == ok:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING)
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE)
        self.requestPictureAndResult()

    def _handleHubAndBottomBearingCheck(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedHubAndBottomBearingCheckImage,
            result=AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult
        )
        self.resultsContainer.setHubAndBottomBearingCheckData(
            value=AutoCompanyFrontEnd.processedHubAndBottomBearingCheckImage,
            result=AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult
        )
        if AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult == ok:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING)
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING)
        self.requestPictureAndResult()

    def _handleTopBearingCheck(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedTopBearingCheckImage,
            result=AutoCompanyFrontEnd.currentTopBearingCheckResult
        )
        self.resultsContainer.setTopBearingCheckData(
            value=AutoCompanyFrontEnd.processedTopBearingCheckImage,
            result=AutoCompanyFrontEnd.currentTopBearingCheckResult
        )
        if AutoCompanyFrontEnd.currentTopBearingCheckResult == ok:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER)
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING)
        self.requestPictureAndResult()

    def _handleNutAndPlateWasherCheck(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedNutAndPlateWasherCheckImage,
            result=AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult
        )
        self.resultsContainer.setNutAndPlateWasherCheckData(
            value=AutoCompanyFrontEnd.processedNutAndPlateWasherCheckImage,
            result=AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult
        )
        if AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult == ok:
            self.setCurrentState(MachineState.READ_TIGHTENING_TORQUE_1)
            self.requestTorqueReadingPlusCapPressAndResult()
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER)
            self.requestPictureAndResult()

    def _handleBunkForComponentPress(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedBunkForComponentPressCheckImage,
            result=AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult
        )
        self.resultsContainer.setBunkForComponentPressData(
            value=AutoCompanyFrontEnd.processedBunkForComponentPressCheckImage,
            result=AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult
        )
        if AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult == ok:
            self.setCurrentState(MachineState.READ_COMPONENT_PRESS_DONE)
            self.requestTorqueReadingPlusCapPressAndResult()
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS)
            self.requestPictureAndResult()

    def _handleNoBunkAfterComponentPress(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedNoBunkAfterComponentPressCheckImage,
            result=AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult
        )
        self.resultsContainer.setNoBunkAfterComponentPress(
            value=AutoCompanyFrontEnd.processedNoBunkAfterComponentPressCheckImage,
            result=AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult
        )
        if AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult == ok:
            self.setCurrentState(MachineState.READ_TIGHTENING_TORQUE_2)
            self.requestTorqueReadingPlusCapPressAndResult()
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK)
            self.requestPictureAndResult()

    def _handleSplitPinAndWasherCheck(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedSplitPinAndWasherCheckImage,
            result=AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult
        )
        self.resultsContainer.setSplitPinAndWasherCheckData(
            value=AutoCompanyFrontEnd.processedSplitPinAndWasherCheckImage,
            result=AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult
        )
        if AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult == ok:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP)
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER)
        self.requestPictureAndResult()

    def _handleCapCheck(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedCapCheckImage,
            result=AutoCompanyFrontEnd.currentCapCheckResult
        )
        self.resultsContainer.setCapCheckData(
            value=AutoCompanyFrontEnd.processedCapCheckImage,
            result=AutoCompanyFrontEnd.currentCapCheckResult
        )
        if AutoCompanyFrontEnd.currentCapCheckResult == ok:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS)
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP)
        self.requestPictureAndResult()

    def _handleBunkCheckForCapPress(self):
        self.showATemporaryLargeImage(
            anImage=AutoCompanyFrontEnd.processedBunkForCapPressCheckImage,
            result=AutoCompanyFrontEnd.currentBunkForCapPressCheckResult
        )
        self.resultsContainer.setBunkCheckData(
            value=AutoCompanyFrontEnd.processedBunkForCapPressCheckImage,
            result=AutoCompanyFrontEnd.currentBunkForCapPressCheckResult
        )
        if AutoCompanyFrontEnd.currentBunkForCapPressCheckResult == ok:
            self.setCurrentState(MachineState.READ_CAP_PRESS_DONE)
            self.requestTorqueReadingPlusCapPressAndResult()
        else:
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS)
            self.requestPictureAndResult()

    # ********************************************

    def requestTorqueReadingPlusCapPressAndResult(self):
        GetTorqueReadingPlusCapPressAndResultWorker.seekTorqueReadingPlusCapPressAndResult = True

    def createGetTorqueReadingPlusCapPressAndResultWorker(self):
        self.getTorqueReadingAndResultWorker = GetTorqueReadingPlusCapPressAndResultWorker()
        self.getTorqueReadingAndResultThread = QThread()
        self.getTorqueReadingAndResultWorker.moveToThread(self.getTorqueReadingAndResultThread)
        self.getTorqueReadingAndResultWorker.gotTorqueReadingPlusCapPressAndResult.connect(self.updateTorqueAndCapPressContainer)
        self.getTorqueReadingAndResultThread.finished.connect(self.getTorqueReadingAndResultThread.deleteLater)
        self.getTorqueReadingAndResultThread.start()

    @Slot()
    def updateTorqueAndCapPressContainer(self):
        currentState = AutoCompanyFrontEnd.machineState.getCurrentState()

        stateHandlerMap = {
            MachineState.READ_TIGHTENING_TORQUE_1: self._handleTighteningTorque1,
            MachineState.READ_FREE_ROTATIONS_DONE: self._handleFreeRotations,
            MachineState.READ_COMPONENT_PRESS_DONE: self._handleComponentPressDone,
            MachineState.READ_TIGHTENING_TORQUE_2: self._handleTighteningTorque2,
            MachineState.READ_CAP_PRESS_DONE: self._handleCapPressResult,
            MachineState.READ_FREE_ROTATION_TORQUE_1: self._handleRotationTorque1
        }

        handler = stateHandlerMap.get(currentState)
        if handler:
            handler()

        self.resultsContainer.setInstruction(self.machineState.getCurrentInstruction())

    def _handleTighteningTorque1(self):
        if AutoCompanyFrontEnd.currentTighteningTorque1CheckResult == ok:
            self.resultsContainer.setTighteningTorque1Data(
                value=f"{AutoCompanyFrontEnd.currentTighteningTorque1:.2f}", result=ok
            )
            self.setCurrentState(MachineState.READ_FREE_ROTATIONS_DONE)
        else:
            self.resultsContainer.setTighteningTorque1Default()
            self.setCurrentState(MachineState.READ_TIGHTENING_TORQUE_1)
        self.requestTorqueReadingPlusCapPressAndResult()

    def _handleFreeRotations(self):
        if AutoCompanyFrontEnd.currentFreeRotationsDone == ok:
            self.resultsContainer.setFreeRotationsData(
                value=f"Done", result=ok
            )
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS)
            self.requestPictureAndResult()
        else:
            self.resultsContainer.setFreeRotationDefault()
            self.setCurrentState(MachineState.READ_FREE_ROTATIONS_DONE)
            self.requestTorqueReadingPlusCapPressAndResult()

    def _handleComponentPressDone(self):
        if AutoCompanyFrontEnd.currentComponentPressDone == ok:
            self.resultsContainer.setComponentPressData(
                value=f"Done", result=ok
            )
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK)
            self.requestPictureAndResult()
        else:
            self.resultsContainer.setComponentPressDefault()
            self.setCurrentState(MachineState.READ_COMPONENT_PRESS_DONE)
            self.requestTorqueReadingPlusCapPressAndResult()

    def _handleTighteningTorque2(self):
        if AutoCompanyFrontEnd.currentTighteningTorque2CheckResult == ok:
            self.resultsContainer.setTighteningTorque2Data(
                value=f"{AutoCompanyFrontEnd.currentTighteningTorque2:.2f}", result=ok
            )
            self.setCurrentState(MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER)
            self.requestPictureAndResult()
        else:
            self.resultsContainer.setTighteningTorque2Default()
            self.setCurrentState(MachineState.READ_TIGHTENING_TORQUE_2)
            self.requestTorqueReadingPlusCapPressAndResult()

    def _handleCapPressResult(self):
        if AutoCompanyFrontEnd.currentCapPressDone == ok:
            self.resultsContainer.setCapPressResultData(value="Done", result=ok)
            self.setCurrentState(MachineState.READ_FREE_ROTATION_TORQUE_1)
        else:
            self.resultsContainer.setCapPressResultDefault()
            self.setCurrentState(MachineState.READ_CAP_PRESS_DONE)
        self.requestTorqueReadingPlusCapPressAndResult()

    def _handleRotationTorque1(self):
        if AutoCompanyFrontEnd.currentRotationTorque1CheckResult == ok:
            concatenated_value :str = f"Done\n{AutoCompanyFrontEnd.currentRotationTorque1:.2f}"
            self.resultsContainer.setCapPressResultData(value=concatenated_value, result=ok)
        else:
            self.setCurrentState(MachineState.READ_FREE_ROTATION_TORQUE_1)
        logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": "About to call doFinalProcessing() from normal path"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
        self.doFinalProcessing()

    def doFinalProcessing(self):
        logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": "Entered doFinalProcessing()"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)

        checks = [
            AutoCompanyFrontEnd.currentKnuckleCheckResult == ok,
            AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult == ok,
            AutoCompanyFrontEnd.currentTopBearingCheckResult == ok,
            AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult == ok,
            AutoCompanyFrontEnd.currentTighteningTorque1CheckResult == ok,  # ADD
            AutoCompanyFrontEnd.currentFreeRotationsDone == ok,
            AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult == ok,
            AutoCompanyFrontEnd.currentComponentPressDone == ok,
            AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult == ok,
            AutoCompanyFrontEnd.currentTighteningTorque2CheckResult == ok,  # ADD
            AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult == ok,
            AutoCompanyFrontEnd.currentCapCheckResult == ok,
            AutoCompanyFrontEnd.currentBunkForCapPressCheckResult == ok,
            AutoCompanyFrontEnd.currentCapPressDone == ok,  # ADD
            AutoCompanyFrontEnd.currentRotationTorque1CheckResult == ok,
        ]

        theFinalResult = all(checks)
        AutoCompanyFrontEnd.finalResult = ok if theFinalResult else notok
        # The delay of 2000 ms ensures that it accounts for the travel time from station 4 back to station 1
        QTimer.singleShot(750, self.setInProcessDefaultDisplay)

    def okNotokResult(self, value):
        if value is None:
            return notok
        if str(value) == notok:
            return notok
        if isinstance(value, bool):
            if value:
                return ok
            else:
                return notok
        if str(value) == ok:
            return ok
        return notok

        # return value if ((value is not None) and (value)) else notok

    @Slot()
    def setInProcessDefaultDisplay(self):
        logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"Entered setInProcessDefaultDisplay(), with {AutoCompanyFrontEnd.emergencyButtonPressed = }"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)

        if self.getCurrentState() == MachineState.READ_QR_CODE:
            AutoCompanyFrontEnd.emergencyButtonPressed = False
            return

        self.show()
        self.raise_()
        self.activateWindow()

        if AutoCompanyFrontEnd.emergencyButtonPressed:
            self.largeImageWindow.showEmergencyAbort()
        elif AutoCompanyFrontEnd.finalResult:
            self.largeImageWindow.showSuccess()
        else:
            self.largeImageWindow.showFailure()

        # NOTE : This is the place where the Emergency button pressed needs to be reset to False,
        #        because of the use of QTimer in calling setInProcessDefaultDisplay()
        AutoCompanyFrontEnd.emergencyButtonPressed = False

        sendDataFromFEServerToDatabaseServer(redisConnection=AutoCompanyFrontEnd.databaseUpdationRedisConnection,
                                             qrCode=AutoCompanyFrontEnd.currentQRCode,
                                             knucklePicture=AutoCompanyFrontEnd.originalKnuckleCheckImage,
                                             knuckleResult=self.okNotokResult(AutoCompanyFrontEnd.currentKnuckleCheckResult),
                                             knuckleDatetime=AutoCompanyFrontEnd.currentKnuckleCheckDatetime,
                                             hubAndBottomBearingPicture=AutoCompanyFrontEnd.originalHubAndBottomBearingCheckImage,
                                             hubAndBottomBearingResult=self.okNotokResult(AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult),
                                             hubAndBottomBearingDatetime=AutoCompanyFrontEnd.currentHubAndBottomBearingCheckDatetime,
                                             topBearingPicture=AutoCompanyFrontEnd.originalTopBearingCheckImage,
                                             topBearingResult=self.okNotokResult(AutoCompanyFrontEnd.currentTopBearingCheckResult),
                                             topBearingDatetime=AutoCompanyFrontEnd.currentTopBearingCheckDatetime,
                                             nutAndPlateWasherPicture=AutoCompanyFrontEnd.originalNutAndPlateWasherCheckImage,
                                             nutAndPlateWasherResult=self.okNotokResult(AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult),
                                             nutAndPlateWasherDatetime=AutoCompanyFrontEnd.currentNutAndPlateWasherCheckDatetime,
                                             tighteningTorque1=AutoCompanyFrontEnd.currentTighteningTorque1,
                                             tighteningTorque1Result=self.okNotokResult(AutoCompanyFrontEnd.currentTighteningTorque1CheckResult),
                                             tighteningTorque1Datetime=AutoCompanyFrontEnd.currentTighteningTorque1Datetime,
                                             freeRotationDone=self.okNotokResult(AutoCompanyFrontEnd.currentFreeRotationsDone),
                                             freeRotationDatetime=AutoCompanyFrontEnd.currentFreeRotationsDatetime,
                                             componentPressBunkCheckingPicture=AutoCompanyFrontEnd.originalBunkForComponentPressCheckImage,
                                             componentPressBunkCheckingResult=self.okNotokResult(AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult),
                                             componentPressBunkCheckDatetime=AutoCompanyFrontEnd.currentBunkForComponentPressCheckDatetime,
                                             componentPressDone=self.okNotokResult(AutoCompanyFrontEnd.currentComponentPressDone),
                                             componentPressDoneDatetime=AutoCompanyFrontEnd.currentComponentPressDatetime,
                                             noBunkCheckingPicture=AutoCompanyFrontEnd.originalNoBunkAfterComponentPressCheckImage,
                                             noBunkCheckingResult=self.okNotokResult(AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult),
                                             noBunkCheckDatetime=AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckDatetime,
                                             tighteningTorque2=AutoCompanyFrontEnd.currentTighteningTorque2,
                                             tighteningTorque2Result=self.okNotokResult(AutoCompanyFrontEnd.currentTighteningTorque2CheckResult),
                                             tighteningTorque2Datetime=AutoCompanyFrontEnd.currentTighteningTorque2Datetime,
                                             splitPinAndWasherPicture=AutoCompanyFrontEnd.originalSplitPinAndWasherCheckImage,
                                             splitPinAndWasherResult=self.okNotokResult(AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult),
                                             splitPinAndWasherDatetime=AutoCompanyFrontEnd.currentSplitPinAndWasherCheckDatetime,
                                             capCheckingPicture=AutoCompanyFrontEnd.originalCapCheckImage,
                                             capCheckingResult=self.okNotokResult(AutoCompanyFrontEnd.currentCapCheckResult),
                                             capCheckingDatetime=AutoCompanyFrontEnd.currentCapCheckDatetime,
                                             bunkCheckingPicture=AutoCompanyFrontEnd.originalBunkForCapPressCheckImage,
                                             capPressBunkCheckingResult=self.okNotokResult(AutoCompanyFrontEnd.currentBunkForCapPressCheckResult),
                                             capPressBunkCheckDatetime=AutoCompanyFrontEnd.currentBunkForCapPressCheckDatetime,
                                             pressDone=self.okNotokResult(AutoCompanyFrontEnd.currentCapPressDone),
                                             capPressDoneDatetime=AutoCompanyFrontEnd.currentCapPressDatetime,
                                             freeRotationTorque1=AutoCompanyFrontEnd.currentRotationTorque1,
                                             freeRotationTorque1Result=self.okNotokResult(AutoCompanyFrontEnd.currentRotationTorque1CheckResult),
                                             freeRotationTorque1Datetime=AutoCompanyFrontEnd.currentRotationTorque1Datetime,
                                             overallResult=ok if AutoCompanyFrontEnd.finalResult == ok else notok
                                             )
        self.resetAllDataPoints()
        self.setCurrentState(MachineState.READ_QR_CODE)
        self.resultsContainer.setInProcessDefaultDisplay()
        self.setQRCodeContainerDisplay(displayString="")
        self.requestQRCode()
        self.resultsContainer.setInstruction(self.machineState.getCurrentInstruction())

    # ********************************************



# ****************************************************

class GetQRCodeWorker(QObject):
    gotQRCode = Signal()
    seekQRCode = False

    def __init__(self):
        super(GetQRCodeWorker, self).__init__()
        self.pollTimer = QTimer(self)
        self.pollTimer.timeout.connect(self.checkForQRCodeTrigger)
        self.pollTimer.start(250)  # Check every 0.25 sec

        self.qrCheckTimer = QTimer(self)
        self.qrCheckTimer.timeout.connect(self.tryReadQRCode)
        self.qrCheckTimer.setInterval(250)  # Faster retry until found
        self.qrCheckTimer.setSingleShot(False)

    @Slot()
    def checkForQRCodeTrigger(self):
        if (AutoCompanyFrontEnd.machineState.getCurrentState() == MachineState.READ_QR_CODE) and GetQRCodeWorker.seekQRCode:
            self.qrCheckTimer.start()  # Start the QR reading loop
            self.pollTimer.stop()      # Pause regular checking during active reading

    @Slot()
    def tryReadQRCode(self):
        qrCodeValue, qrCodeDisplayString, qrCodeFound = readDataInFEServerFromQRCodeServer(AutoCompanyFrontEnd.processUpdationRedisConnection,
                                                                                           block=None) # non-blocking call
        if qrCodeFound:
            AutoCompanyFrontEnd.currentQRCode = qrCodeValue
            AutoCompanyFrontEnd.currentQRCodeForDisplay = qrCodeDisplayString
            self.gotQRCode.emit()

            # Stop retrying, reset state
            GetQRCodeWorker.seekQRCode = False
            self.qrCheckTimer.stop()
            self.pollTimer.start(250)  # Resume periodic polling

    def __del__(self):
        self.pollTimer.stop()
        self.pollTimer.deleteLater()
        self.qrCheckTimer.stop()
        self.qrCheckTimer.deleteLater()

# ****************************************************

class TimeDurationUpdateWorker(QObject):
    doTimeDurationUpdate = Signal()

    def __init__(self):
        super(TimeDurationUpdateWorker, self).__init__()
        self.updateTimer = QTimer(self)
        self.updateTimer.timeout.connect(self.emitUpdateSignal)
        self.updateTimer.start(self._getIntervalMs())

    def _getIntervalMs(self) -> int:
        """Fetch the interval from CosThetaConfigurator and return it in milliseconds"""
        try:
            return int(CosThetaConfigurator.getInstance().getTimeDurationSleepInterval() * 1000)
        except Exception as e:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"[TimeDurationUpdateWorker] Failed to get interval, defaulting to 1000ms: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            return 1000  # Fallback to 1 second

    @Slot()
    def emitUpdateSignal(self):
        if not AutoCompanyFrontEnd.shutdownThreads:
            # printBoldGreen("Emitting doTimeDurationUpdate()")
            self.doTimeDurationUpdate.emit()
        else:
            self.updateTimer.stop()
            # printBoldRed("Stopped TimeDurationUpdateWorker due to shutdown.")

    def __del__(self):
        self.updateTimer.stop()
        self.updateTimer.deleteLater()

# ****************************************************

class ConnectionStatusUpdateWorker(QObject):
    doConnectionStatusUpdate = Signal()

    def __init__(self):
        super(ConnectionStatusUpdateWorker, self).__init__()
        self.updateTimer = QTimer(self)
        self.updateTimer.timeout.connect(self.emitUpdateSignal)
        self.updateTimer.start(self._getIntervalMs())

    def _getIntervalMs(self) -> int:
        """Fetch interval from config and return in milliseconds"""
        try:
            return int(CosThetaConfigurator.getInstance().getGeneralConnectionStatusSleepInterval() * 1000)
        except Exception as e:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"[ConnectionStatusUpdateWorker] Failed to get interval, defaulting to 5000ms: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            return 5000  # Default fallback

    @Slot()
    def emitUpdateSignal(self):
        if not AutoCompanyFrontEnd.shutdownThreads:
            # printBoldGreen("Emitting doConnectionStatusUpdate")
            self.doConnectionStatusUpdate.emit()
        else:
            self.updateTimer.stop()
            # printBoldRed("Stopped ConnectionStatusUpdateWorker due to shutdown.")

    def __del__(self):
        self.updateTimer.stop()
        self.updateTimer.deleteLater()

# ****************************************************

class EmergencyStatusMonitoringWorker(QObject):
    doEmergencyPressedUpdate = Signal()

    def __init__(self):
        super(EmergencyStatusMonitoringWorker, self).__init__()
        self.updateTimer = QTimer(self)
        self.updateTimer.timeout.connect(self.emitEmergencyStatus)
        self.updateTimer.start(self._getIntervalMs())  # Check every 1 second

    def _getIntervalMs(self) -> int:
        """Fetch interval from config and return in milliseconds"""
        try:
            return int(CosThetaConfigurator.getInstance().getFrontEndEmergencyStatusSleepInterval() * 1000)
        except Exception as e:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"[EmergencyStatusMonitoringWorker] Failed to get interval, defaulting to 1000ms: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            return 1000  # Default fallback

    @Slot()
    def emitEmergencyStatus(self):
        if not AutoCompanyFrontEnd.shutdownThreads:
            # printBoldGreen("Emitting doEmergencyPressedUpdate")
            self.doEmergencyPressedUpdate.emit()
        else:
            self.updateTimer.stop()
            # printBoldRed("Stopped EmergencyStatusMonitoringWorker due to shutdown.")

    def __del__(self):
        self.updateTimer.stop()
        self.updateTimer.deleteLater()

# ****************************************************

class GetPictureAndResultWorker(QObject):

    gotPictureAndResult = Signal()
    seekPictureAndResult : bool = False

    validStates : list = [
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP,
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS
        ]

    def __init__(self):
        super(GetPictureAndResultWorker, self).__init__()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.checkForPictureAndResult)
        self.timer.start(250)  # match original polling interval

    @Slot()
    def checkForPictureAndResult(self):
        if AutoCompanyFrontEnd.shutdownThreads:
            self.timer.stop()
            return

        if not GetPictureAndResultWorker.seekPictureAndResult:
            return

        currentState = AutoCompanyFrontEnd.machineState.getCurrentState()

        if currentState not in GetPictureAndResultWorker.validStates:
            return

        try:
            timeOfMessage, decodedOriginalImage, decodedProcessedImage, decodedResult, currentMachineState = readDataInFEServerFromCameraServer(AutoCompanyFrontEnd.processUpdationRedisConnection,
                                                                                                                                                block=None) # non-blocking call

            if decodedResult is not None:

                GetPictureAndResultWorker.seekPictureAndResult = False

                if decodedOriginalImage is not None:
                    if not isinstance(decodedOriginalImage, np.ndarray):
                        decodedOriginalImage = blankWhiteImage
                else:
                    decodedOriginalImage = blankWhiteImage

                if decodedProcessedImage is not None:
                    if not isinstance(decodedProcessedImage, np.ndarray):
                        decodedProcessedImage = blankWhiteImage
                else:
                    decodedProcessedImage = blankWhiteImage

                if currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE:
                    AutoCompanyFrontEnd.originalKnuckleCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedKnuckleCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentKnuckleCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentKnuckleCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING:
                    AutoCompanyFrontEnd.originalHubAndBottomBearingCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedHubAndBottomBearingCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentHubAndBottomBearingCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentHubAndBottomBearingCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING:
                    AutoCompanyFrontEnd.originalTopBearingCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedTopBearingCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentTopBearingCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentTopBearingCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER:
                    AutoCompanyFrontEnd.originalNutAndPlateWasherCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedNutAndPlateWasherCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentNutAndPlateWasherCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentNutAndPlateWasherCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS:
                    AutoCompanyFrontEnd.originalBunkForComponentPressCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedBunkForComponentPressCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentBunkForComponentPressCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentBunkForComponentPressCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK:
                    AutoCompanyFrontEnd.originalNoBunkAfterComponentPressCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedNoBunkAfterComponentPressCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentNoBunkAfterComponentPressCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER:
                    AutoCompanyFrontEnd.originalSplitPinAndWasherCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedSplitPinAndWasherCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentSplitPinAndWasherCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentSplitPinAndWasherCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP:
                    AutoCompanyFrontEnd.originalCapCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedCapCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentCapCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentCapCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                elif currentState == MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS:
                    AutoCompanyFrontEnd.originalBunkForCapPressCheckImage = decodedOriginalImage
                    AutoCompanyFrontEnd.processedBunkForCapPressCheckImage = decodedProcessedImage
                    AutoCompanyFrontEnd.currentBunkForCapPressCheckResult = decodedResult
                    AutoCompanyFrontEnd.currentBunkForCapPressCheckDatetime = getPostgresDatetimeFromString(getCurrentTime())

                self.gotPictureAndResult.emit()

        except Exception as e:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"[GetPictureAndResultWorker] Exception: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)

    def __del__(self):
        self.timer.stop()
        self.timer.deleteLater()

# ****************************************************

class GetTorqueReadingPlusCapPressAndResultWorker(QObject):
    gotTorqueReadingPlusCapPressAndResult = Signal()
    seekTorqueReadingPlusCapPressAndResult = False

    def __init__(self):
        super(GetTorqueReadingPlusCapPressAndResultWorker, self).__init__()
        self.validStates = {
            MachineState.READ_TIGHTENING_TORQUE_1: self._handleTighteningTorque1,
            MachineState.READ_FREE_ROTATIONS_DONE: self._handleFreeRotations,
            MachineState.READ_COMPONENT_PRESS_DONE: self._handleComponentPress,
            MachineState.READ_TIGHTENING_TORQUE_2: self._handleTighteningTorque2,
            MachineState.READ_CAP_PRESS_DONE: self._handleCapPress,
            MachineState.READ_FREE_ROTATION_TORQUE_1: self._handleRotationTorque1
        }

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.checkForTorqueAndResult)
        self.timer.start(250)  # match original polling interval

    @Slot()
    def checkForTorqueAndResult(self):
        if AutoCompanyFrontEnd.shutdownThreads:
            self.timer.stop()
            return

        if not GetTorqueReadingPlusCapPressAndResultWorker.seekTorqueReadingPlusCapPressAndResult:
            return

        currentState = AutoCompanyFrontEnd.machineState.getCurrentState()

        if currentState not in self.validStates:
            return

        currentMachineState, moveToState, action, value, result = readDataInFEServerFromIOServer(
            AutoCompanyFrontEnd.processUpdationRedisConnection, block=None # non-blocking call
        )

        if currentMachineState == MachineState.INVALID_STATE:
            return

        # Validate that the incoming message's state matches the expected state
        # This prevents processing stale/leftover data from a different state
        if currentMachineState != currentState:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"[GetTorqueReadingPlusCapPressAndResultWorker] State mismatch: expected {currentState}, got {currentMachineState}. Ignoring message."}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)
            return

        GetTorqueReadingPlusCapPressAndResultWorker.seekTorqueReadingPlusCapPressAndResult = False

        try:
            handler = self.validStates[currentState]
            handler(value, result)
            self.gotTorqueReadingPlusCapPressAndResult.emit()
        except Exception as e:
            logMessageToConsoleAndFile(AutoCompanyFrontEnd.processUpdationRedisConnection, {"text": f"[GetTorqueReadingPlusCapPressAndResultWorker] Error handling state {currentState}: {e}"}, AutoCompanyFrontEnd.logSource, level=LogLevel.CRITICAL)

    # --- State Handlers ---

    def _handleTighteningTorque1(self, value, result):
        if result == ok:
            AutoCompanyFrontEnd.currentTighteningTorque1 = (int(value * 100)) / 100
            AutoCompanyFrontEnd.currentTighteningTorque1CheckResult = ok
        else:
            AutoCompanyFrontEnd.currentTighteningTorque1 = 0.0
            AutoCompanyFrontEnd.currentTighteningTorque1CheckResult = notok
        AutoCompanyFrontEnd.currentTighteningTorque1Datetime = getPostgresDatetimeFromString(getCurrentTime())

    def _handleFreeRotations(self, value, result):
        if result == ok:
            AutoCompanyFrontEnd.currentFreeRotationsDone = ok
        else:
            AutoCompanyFrontEnd.currentFreeRotationsDone = notok
        AutoCompanyFrontEnd.currentFreeRotationsDatetime = getPostgresDatetimeFromString(getCurrentTime())

    def _handleComponentPress(self, value, result):
        if result == ok:
            AutoCompanyFrontEnd.currentComponentPressDone = ok
        else:
            AutoCompanyFrontEnd.currentComponentPressDone = notok
        AutoCompanyFrontEnd.currentComponentPressDatetime = getPostgresDatetimeFromString(getCurrentTime())

    def _handleTighteningTorque2(self, value, result):
        if result == ok:
            AutoCompanyFrontEnd.currentTighteningTorque2 = (int(value * 100)) / 100
            AutoCompanyFrontEnd.currentTighteningTorque2CheckResult = ok
        else:
            AutoCompanyFrontEnd.currentTighteningTorque2 = 0.0
            AutoCompanyFrontEnd.currentTighteningTorque2CheckResult = notok
        AutoCompanyFrontEnd.currentTighteningTorque2Datetime = getPostgresDatetimeFromString(getCurrentTime())

    def _handleCapPress(self, value, result):
        if result == ok:
            AutoCompanyFrontEnd.currentCapPressDone = ok
        else:
            AutoCompanyFrontEnd.currentCapPressDone = notok
        AutoCompanyFrontEnd.currentCapPressDatetime = getPostgresDatetimeFromString(getCurrentTime())

    def _handleRotationTorque1(self, value, result):
        if result == ok:
            AutoCompanyFrontEnd.currentRotationTorque1 = (int(value * 100)) / 100
            AutoCompanyFrontEnd.currentRotationTorque1CheckResult = ok
        else:
            AutoCompanyFrontEnd.currentRotationTorque1 = 0.0
            AutoCompanyFrontEnd.currentRotationTorque1CheckResult = notok
        AutoCompanyFrontEnd.currentRotationTorque1Datetime = getPostgresDatetimeFromString(getCurrentTime())

    def __del__(self):
        self.timer.stop()
        self.timer.deleteLater()

# ****************************************************

class HeartbeatSenderWorker(QObject):
    pingInterval = int(CosThetaConfigurator.getInstance().getFrontendStatusSleepInterval()*1000)

    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.send_heartbeat)

    def start(self):
        self.timer.start(HeartbeatSenderWorker.pingInterval)  # 250 milliseconds

    def stop(self):
        self.timer.stop()

    def send_heartbeat(self):
        sendHeartbeatFromFEServerToHeartbeatServer(AutoCompanyFrontEnd.heartbeatRedisConnection, ALIVE)

    def __del__(self):
        self.timer.stop()
        self.timer.deleteLater()

# ****************************************************

class LargeImageWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """

    def __init__(self, parent = None):
        super().__init__(parent)
        self.setWindowTitle("Large Image Display")
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.Dialog)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.width = int(AutoCompanyFrontEnd.CURRENT_WIDTH * 0.5)
        self.height = int(AutoCompanyFrontEnd.CURRENT_HEIGHT * 0.5)
        self.left = int((AutoCompanyFrontEnd.CURRENT_WIDTH - self.width) / 2)
        self.top =  int(AutoCompanyFrontEnd.RESULTS_CONTAINER_TOP + self.height / 10)
        self.setFixedWidth(self.width)
        self.setFixedHeight(self.height)
        self.setGeometry(self.left, self.top, self.width, self.height)
        layout = QVBoxLayout()
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setScaledContents(False)
        anImage = createImage(text="Sample Image", imageDimensions=(self.width - 35, self.height - 35),
                                        fontColor=QColor(15, 15, 15), replaceChar=[' ',' '], backgroundColor = QColor(125, 210, 185))
        self.image = getPixmapImage(anImage)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.label.setPixmap(self.image)
        self.successImage = createImage(text="Component Successfully Done", imageDimensions=(self.width - 35, self.height - 35),
                                            fontColor=QColor(15, 15, 15), replaceChar=[' ',' '], backgroundColor = QColor(125, 210, 185))
        self.failureImage = createImage(text="Component Not Successfully Done", imageDimensions=(self.width - 35, self.height - 35),
                                        fontColor=QColor(15, 15, 15), replaceChar=[' ',' '], backgroundColor = QColor(210, 90, 90))
        self.emergencyImage = createImage(text="Component Processing Aborted", imageDimensions=(self.width - 35, self.height - 35),
                                        fontColor=QColor(15, 15, 15), replaceChar=[' ',' '], backgroundColor = QColor(210, 90, 90))


    def setPixmap(self, anyTypeOfImage:  QImage | QPixmap | ndarray | str, result : str = "no result"):
        pixMapImage = getPixmapImage(anyTypeOfImage)
        if result == ok:
            self.label.setStyleSheet("background-color: green;border: 0px;border-radius: 5px;QLabel { margin: auto; }")
        elif result == notok:
            self.label.setStyleSheet("background-color: red;border: 0px;border-radius: 5px;QLabel { margin: auto; }")
        else:
            self.label.setStyleSheet("background-color: white;border: 0px;border-radius: 5px;QLabel { margin: auto; }")
        pixMapImage = resize_pixmap(pixmap=pixMapImage, width=self.width-35, height=self.height-35)
        self.label.setPixmap(pixMapImage)

    def showSuccess(self):
        self.setPixmap(self.successImage)
        self.show()
        self.raise_()
        self.activateWindow()

    def showFailure(self):
        self.setPixmap(self.failureImage)
        self.show()
        self.raise_()
        self.activateWindow()

    def showEmergencyAbort(self):
        self.setPixmap(self.emergencyImage)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.hide()
        if self.parent():
            self.parent().setFocus()
        event.accept()

    def close(self):
        self.deleteLater()

    def dispose(self):
        self.deleteLater()
# ****************************************************


def startFrontEnd(mode : str, username : str, role : str):
    gfe = AutoCompanyFrontEnd(mode=mode, username=username, role=role)
    app.exec()
    app.quit()


# startFrontEnd("Test", "admin", "admin")
# printBoldBlue("****************")
# printBoldBlue("Started FrontEnd Server")
# printBoldBlue("****************")