# from multidispatch import dispatch
from PySide6.QtWidgets import QHBoxLayout

from frontend.CosThetaMonitorDimensions import getMonitorWidth, getMonitorHeight
from frontend.CosThetaStylesheets import modeLabelStylesheet, actionAwaitedStylesheet, instructionAwaitedStylesheet
from frontend.widgets.CosThetaOutcomeContainer import *
from frontend.frontendutils.CosThetaLabelUtils import *
from frontend.widgets.CosTheta_TwoOutcomesContainer import CosTheta_TwoOutcomesContainer
# from frontend.frontendutils.CosThetaImageUtils import createImage
from typing import Union, get_origin, get_args

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosThetaResultsContainer(QWidget):

    averageLabelHeight = 40.
    horizontalSpacing : int = 4
    verticalSpacing : int = 2
    monitorWidth = getMonitorWidth()
    monitorHeight = getMonitorHeight()
    # imageRatio : float = monitorWidth * 1.0 / monitorHeight
    # print(f"{imageRatio = }, {monitorWidth = }, {monitorHeight = }")
    # width_of_each_container = int(monitorWidth * 0.8 / 7)

    width_of_each_container = int((monitorWidth - 8 * horizontalSpacing) / 7.0)
    # height_of_each_container = int (monitorWidth * 3 / 11)
    height_of_each_container = int ((monitorHeight - 10 * CosThetaConfigurator.getInstance().getLabelInitialHeight() - 3 * CosThetaOutcomeContainer.spacingBetweenWidgets) / 2.0)

    # currentRatio : float = width_of_each_container * 1.0 / height_of_each_container
    # print(f"original {currentRatio = }")

    # if currentRatio < imageRatio:
    #     height_of_each_container = int(height_of_each_container * currentRatio / imageRatio)
    # else:
    #     width_of_each_container = int(width_of_each_container * imageRatio / currentRatio)

    # currentRatio = width_of_each_container * 1.0 / height_of_each_container
    # print(f"final {currentRatio = }")

    defaultImageWidth : int = int(width_of_each_container - 12 * CosThetaOutcomeContainer.spacingBetweenWidgets - CosThetaOutcomeContainer.spacingBetweenWidgets)
    # defaultImageHeight = int(height_of_each_container - 2 * averageLabelHeight - 5 * CosThetaOutcomeContainer.spacingBetweenWidgets - CosThetaOutcomeContainer.spacingBetweenWidgets)
    defaultImageHeight : int = int(height_of_each_container - 2 * CosThetaConfigurator.getInstance().getLabelInitialHeight() - 10 * CosThetaOutcomeContainer.spacingBetweenWidgets - CosThetaOutcomeContainer.spacingBetweenWidgets)
    defaultImageFontSize : int = 17
    topLabelFontSizeInOutcomeContainers : int = 12

    # print(f"{height_of_each_container = }, {defaultImageHeight = }")
    # print(f"{defaultImageWidth = }")

    # imageHeight = int(height_of_each_container - 4 * averageLabelHeight - 5 * CosThetaOutcomeContainer.spacingBetweenWidgets)
    imageHeight = int(height_of_each_container)

    # printPlain(width_of_each_container, height_of_each_container)
    # defaultQRCodeImage = createImage("7204838 B5C47102 088 07.11.2022 2.8T", imageDimensions=(width_of_each_container,
    #                                                                               height_of_each_container - 2 * labelHeight - 2 * CosThetaOutcomeContainer.spacingBetweenWidgets - 6 * CosThetaOutcomeContainer.spacingBetweenWidgets),
    #                                  fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '])
    defaultKnuckleCheckImage = createImage("Knuckle Check", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                           fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultHubAndFirstBearingCheckImage = createImage("Hub\b&\bBearing Check", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                      fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultSecondBearingCheckImage = createImage("Second\bBearing Check", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                 fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultNutAndPlateWasherCheckImage = createImage("Nut\b&\bPlate Washer Check", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                     fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultTighteningTorqueCheckImage1 = createImage("Tightening Torque\b1", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                    fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultRotationTorqueCheckImage1 = createImage("Rotation Torque\b1", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                  fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultTighteningTorqueCheckImage2 = createImage("Tightening Torque\b2", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                    fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultRotationTorqueCheckImage2 = createImage("Rotation Torque\b2", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                  fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultTighteningTorqueCheckImage3 = createImage("Tightening Torque\b3", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                    fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultRotationTorqueCheckImage3 = createImage("Rotation Torque\b3", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                  fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultSplitPinAndWasherImage = createImage("Split\bPin And Washer\bCheck", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultCapCheckImage = createImage("Cap Check", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultBunkCheckImage = createImage("Bunk Check", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                        fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)
    defaultCapPressImage = createImage("Cap\bPress Result", imageDimensions=(defaultImageWidth, defaultImageHeight),
                                                fontColor=Qt.GlobalColor.darkBlue, replaceChar=['=',' '], forceUseOfFontSizeAs=defaultImageFontSize)

    logger = None

    def __init__(self):
        super().__init__()
        self.initializeUI()

    def initializeUI(self):
        """Initialize the window and display its contents to the screen."""
        self.setMinimumSize(800, 400)
        self.setupWidgets()

    def setupWidgets(self):

        self.setContentsMargins(0,0,0,0)

        """Set up the containers and main layout for the window."""
        self.knuckle_check_container = CosThetaOutcomeContainer("Knuckle Check", CosThetaResultsContainer.width_of_each_container,
                                                                CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultKnuckleCheckImage,
                                                                labelHeight=CosThetaResultsContainer.averageLabelHeight,
                                                                bg_color = Qt.GlobalColor.black, fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # =QColor(16, 201, 78))  # Green
        self.hub_and_first_bearing_check_container = CosThetaOutcomeContainer("Hub & Bearing Check", CosThetaResultsContainer.width_of_each_container,
                                                                              CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultHubAndFirstBearingCheckImage,
                                                                              labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                              fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.second_bearing_check_container = CosThetaOutcomeContainer("Second Bearing Check", CosThetaResultsContainer.width_of_each_container,
                                                                       CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultSecondBearingCheckImage,
                                                                       labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                       fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.nut_and_plate_washer_check_container = CosThetaOutcomeContainer("Nut & Washer Check", CosThetaResultsContainer.width_of_each_container,
                                                                             CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultNutAndPlateWasherCheckImage,
                                                                             labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                             fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.tightening_torque1_check_container = CosThetaOutcomeContainer("Tightening Torque 1", CosThetaResultsContainer.width_of_each_container,
                                                                           CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultTighteningTorqueCheckImage1,
                                                                           labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.rotation_torque1_check_container = CosThetaOutcomeContainer("Rotation Torque 1", CosThetaResultsContainer.width_of_each_container,
                                                                         CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultRotationTorqueCheckImage1,
                                                                         labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                         fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.tightening_torque2_check_container = CosThetaOutcomeContainer("Tightening Torque 2", CosThetaResultsContainer.width_of_each_container,
                                                                           CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultTighteningTorqueCheckImage2,
                                                                           labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.rotation_torque2_check_container = CosThetaOutcomeContainer("Rotation Torque 2", CosThetaResultsContainer.width_of_each_container,
                                                                         CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultRotationTorqueCheckImage2,
                                                                         labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                         fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.tightening_torque3_check_container = CosThetaOutcomeContainer("Tightening Torque 3", CosThetaResultsContainer.width_of_each_container,
                                                                           CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultTighteningTorqueCheckImage3,
                                                                           labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.rotation_torque3_check_container = CosThetaOutcomeContainer("Rotation Torque 3", CosThetaResultsContainer.width_of_each_container,
                                                                         CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultRotationTorqueCheckImage3,
                                                                         labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                         fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.splitpin_and_washer_check_container = CosThetaOutcomeContainer("Split Pin & Washer", CosThetaResultsContainer.width_of_each_container,
                                                                           CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultSplitPinAndWasherImage,
                                                                           labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.cap_check_container = CosThetaOutcomeContainer("Cap Check", CosThetaResultsContainer.width_of_each_container,
                                                                           CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultCapCheckImage,
                                                                           labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.bunk_check_container = CosThetaOutcomeContainer("Bunk Check", CosThetaResultsContainer.width_of_each_container,
                                                             CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultBunkCheckImage,
                                                             labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                             fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.cap_press_result_container = CosThetaOutcomeContainer("Cap Press Result", CosThetaResultsContainer.width_of_each_container,
                                                                   CosThetaResultsContainer.height_of_each_container, CosThetaResultsContainer.defaultCapPressImage,
                                                                   labelHeight=CosThetaResultsContainer.averageLabelHeight, bg_color = Qt.GlobalColor.black,
                                                                   fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        initialInstruction : str = "Instruction Label"
        self.instructionLabel = QLabel(initialInstruction)
        self.labelHeight = CosThetaConfigurator.getInstance().getLabelInitialHeight()
        labelFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
        labelFont = QFont('Courier', pointSize=labelFontSize, weight=QFont.Weight.Bold)
        metrics = QFontMetrics(labelFont)
        labelTextRect = metrics.boundingRect(0, 0, 0, 0,
                                             Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                             " " + initialInstruction + " ")
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        reductionFactor = min(super().geometry().width() / textWidth,
                              self.labelHeight * 1.0 / textHeight) * 0.40
        fontSize = int(reductionFactor * labelFontSize)
        labelFont.setPointSize(fontSize)
        self.instructionLabel.setFont(labelFont)
        self.instructionLabel.resize(int(CosThetaResultsContainer.monitorWidth * 0.9), self.labelHeight)
        self.instructionLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.instructionLabel.setStyleSheet(instructionAwaitedStylesheet.format(
            QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        self.instructionLabel.setFixedHeight(self.labelHeight)
        self.instructionLabel.setFixedWidth(int(CosThetaResultsContainer.monitorWidth * 0.9))
        self.instructionLabel.setMinimumSize(QSize(int(CosThetaResultsContainer.monitorWidth), self.labelHeight))

        # Row 1 widget and containers
        self.row1Widget = QWidget()
        row1_box_layout = QHBoxLayout()
        row1_box_layout.setSpacing(0)
        row1_box_layout.setContentsMargins(0,0,0,0)
        row1_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # row1_box_layout.addSpacing(5)
        row1_box_layout.addWidget(self.knuckle_check_container)
        row1_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row1_box_layout.addWidget(self.hub_and_first_bearing_check_container)
        row1_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row1_box_layout.addWidget(self.second_bearing_check_container)
        row1_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row1_box_layout.addWidget(self.nut_and_plate_washer_check_container)
        row1_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row1_box_layout.addWidget(self.tightening_torque1_check_container)
        row1_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row1_box_layout.addWidget(self.rotation_torque1_check_container)
        row1_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row1_box_layout.addWidget(self.tightening_torque2_check_container)
        self.row1Widget.setLayout(row1_box_layout)

        # Row 2 containers
        self.row2Widget = QWidget()
        row2_box_layout = QHBoxLayout()
        row2_box_layout.setSpacing(0)
        row2_box_layout.setContentsMargins(0,0,0,0)
        row2_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # row2_box_layout.addSpacing(5)
        row2_box_layout.addWidget(self.rotation_torque2_check_container)
        row2_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row2_box_layout.addWidget(self.tightening_torque3_check_container)
        row2_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row2_box_layout.addWidget(self.rotation_torque3_check_container)
        row2_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row2_box_layout.addWidget(self.splitpin_and_washer_check_container)
        row2_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row2_box_layout.addWidget(self.cap_check_container)
        row2_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row2_box_layout.addWidget(self.bunk_check_container)
        row2_box_layout.addSpacing(CosThetaResultsContainer.horizontalSpacing)
        row2_box_layout.addWidget(self.cap_press_result_container)
        self.row2Widget.setLayout(row2_box_layout)

        main_central_box_layout = QVBoxLayout()
        main_central_box_layout.setSpacing(0)
        main_central_box_layout.setContentsMargins(0,0,0,0)
        main_central_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_central_box_layout.addSpacing(CosThetaResultsContainer.verticalSpacing)
        main_central_box_layout.addWidget(self.row1Widget)
        main_central_box_layout.addSpacing(CosThetaResultsContainer.verticalSpacing)
        main_central_box_layout.addWidget(self.row2Widget)
        main_central_box_layout.addSpacing(CosThetaResultsContainer.verticalSpacing)
        main_central_box_layout.addWidget(self.instructionLabel)
        # main_central_box_layout.addSpacing(2)
        self.setLayout(main_central_box_layout)
        self.update()
        # print(f"{self.no_bunk_after_component_press_check_container.geometry()}")

    # ****************************************

    def setKnuckleCheckData(self, value, result):
        if isinstance(value, str):
            self.knuckle_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.knuckle_check_container.setImageAndResult(value, result)
        else:
            self.knuckle_check_container.setDefault()

    def setHubAndFirstBearingCheckData(self, value, result):
        if isinstance(value, str):
            self.hub_and_first_bearing_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.hub_and_first_bearing_check_container.setImageAndResult(value, result)
        else:
            self.hub_and_first_bearing_check_container.setDefault()

    def setSecondBearingCheckData(self, value, result):
        if isinstance(value, str):
            self.second_bearing_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.second_bearing_check_container.setImageAndResult(value, result)
        else:
            self.second_bearing_check_container.setDefault()

    def setNutAndPlateWasherCheckData(self, value, result):
        if isinstance(value, str):
            self.nut_and_plate_washer_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.nut_and_plate_washer_check_container.setImageAndResult(value, result)
        else:
            self.nut_and_plate_washer_check_container.setDefault()

    def setTighteningTorque1Data(self, value, result):
        if isinstance(value, str):
            self.tightening_torque1_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.tightening_torque1_check_container.setImageAndResult(value, result)
        else:
            self.tightening_torque1_check_container.setDefault()

    def setRotationTorque1Data(self, value, result):
        if isinstance(value, str):
            self.rotation_torque1_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.rotation_torque1_check_container.setImageAndResult(value, result)
        else:
            self.rotation_torque1_check_container.setDefault()

    def setTighteningTorque2Data(self, value, result):
        if isinstance(value, str):
            self.tightening_torque2_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.tightening_torque2_check_container.setImageAndResult(value, result)
        else:
            self.tightening_torque2_check_container.setDefault()

    def setRotationTorque2Data(self, value, result):
        if isinstance(value, str):
            self.rotation_torque2_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.rotation_torque2_check_container.setImageAndResult(value, result)
        else:
            self.rotation_torque2_check_container.setDefault()

    def setTighteningTorque3Data(self, value, result):
        if isinstance(value, str):
            self.tightening_torque3_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.tightening_torque3_check_container.setImageAndResult(value, result)
        else:
            self.tightening_torque3_check_container.setDefault()

    def setRotationTorque3Data(self, value, result):
        if isinstance(value, str):
            self.rotation_torque3_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.rotation_torque3_check_container.setImageAndResult(value, result)
        else:
            self.rotation_torque3_check_container.setDefault()

    def setSplitPinAndWasherCheckData(self, value, result):
        if isinstance(value, str):
            self.splitpin_and_washer_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.splitpin_and_washer_check_container.setImageAndResult(value, result)
        else:
            self.splitpin_and_washer_check_container.setDefault()

    def setCapCheckData(self, value, result):
        if isinstance(value, str):
            self.cap_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.cap_check_container.setImageAndResult(value, result)
        else:
            self.cap_check_container.setDefault()

    def setBunkCheckData(self, value, result):
        if isinstance(value, str):
            self.bunk_check_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.bunk_check_container.setImageAndResult(value, result)
        else:
            self.bunk_check_container.setDefault()

    def setCapPressResultData(self, value, result):
        if isinstance(value, str):
            self.cap_press_result_container.setTextAndResult(value, result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.cap_press_result_container.setImageAndResult(value, result)
        else:
            self.cap_press_result_container.setDefault()

    def setInstruction(self, value):
        self.instructionLabel.setText(str(value))

    # ****************************************

    def setKnuckleCheckDefault(self):
        self.knuckle_check_container.setDefault()

    def setHubAndFirstBearingCheckDefault(self):
        self.hub_and_first_bearing_check_container.setDefault()

    def setSecondBearingCheckDefault(self):
        self.second_bearing_check_container.setDefault()

    def setNutAndPlateWasherCheckDefault(self):
        self.nut_and_plate_washer_check_container.setDefault()

    def setTighteningTorque1Default(self):
        self.tightening_torque1_check_container.setDefault()

    def setRotationTorque1Default(self):
        self.rotation_torque1_check_container.setDefault()

    def setTighteningTorque2Default(self):
        self.tightening_torque2_check_container.setDefault()

    def setRotationTorque2Default(self):
        self.rotation_torque2_check_container.setDefault()

    def setTighteningTorque3Default(self):
        self.tightening_torque3_check_container.setDefault()

    def setRotationTorque3Default(self):
        self.rotation_torque3_check_container.setDefault()

    def setSplitPinAndWasherCheckDefault(self):
        self.splitpin_and_washer_check_container.setDefault()

    def setCapCheckDefault(self):
        self.cap_check_container.setDefault()

    def setBunkCheckDefault(self):
        self.bunk_check_container.setDefault()

    def setCapPressResultDefault(self):
        self.cap_press_result_container.setDefault()

    def setInstructionDefault(self):
        self.instructionLabel.setText("Instruction Label")

    # ****************************************

    def setInitialDefaultDisplay(self):
        self.setKnuckleCheckDefault()
        self.setHubAndFirstBearingCheckDefault()
        self.setSecondBearingCheckDefault()
        self.setNutAndPlateWasherCheckDefault()
        self.setTighteningTorque1Default()
        self.setRotationTorque1Default()
        self.setTighteningTorque2Default()
        self.setRotationTorque2Default()
        self.setTighteningTorque3Default()
        self.setRotationTorque3Default()
        self.setSplitPinAndWasherCheckDefault()
        self.setCapCheckDefault()
        self.setBunkCheckDefault()
        self.setCapPressResultDefault()
        self.setInstructionDefault()

    def setInProcessDefaultDisplay(self):
        # print(f"setInProcessDefaultDisplay() called")
        self.setKnuckleCheckDefault()
        self.setHubAndFirstBearingCheckDefault()
        self.setSecondBearingCheckDefault()
        self.setNutAndPlateWasherCheckDefault()
        self.setTighteningTorque1Default()
        self.setRotationTorque1Default()
        self.setTighteningTorque2Default()
        self.setRotationTorque2Default()
        self.setTighteningTorque3Default()
        self.setRotationTorque3Default()
        self.setSplitPinAndWasherCheckDefault()
        self.setCapCheckDefault()
        self.setBunkCheckDefault()
        self.setCapPressResultDefault()

    def displayDefault(self):
        self.setInitialDefaultDisplay()

