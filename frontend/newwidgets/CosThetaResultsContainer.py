# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

# from multidispatch import dispatch

from frontend.CosThetaMonitorDimensions import getMonitorWidth, getMonitorHeight
from frontend.CosThetaStylesheets import instructionAwaitedStylesheet
from frontend.newwidgets.CosThetaOutcomeContainer import *
from frontend.frontendutils.CosThetaLabelUtils import *
# from frontend.frontendutils.CosThetaImageUtils import createImage
from typing import Union, get_args

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosThetaResultsContainer(QFrame):

    averageLabelHeight = 40.
    horizontalSpacing : int = 4
    verticalSpacing : int = 2
    monitorWidth = getMonitorWidth()
    monitorHeight = getMonitorHeight()

    topLabelFontSizeInOutcomeContainers : int = 12

    def __init__(self, longestInstruction : str = "  Assemble WASHER and SPLIT PIN. Mark Washer in YELLOW and Split Pin in BLUE. PRESS BOTH BUTTONS to take picture and evaluate  "):
        super().__init__()
        self.longestInstruction = longestInstruction
        self.initializeUI()

    def initializeUI(self):
        """Initialize the window and display its contents to the screen."""
        self.setContentsMargins(0,0,0,0)

        """Set up the containers and main layout for the window."""
        self.knuckle_check_container = CosThetaOutcomeContainer(title = "Knuckle Check", imageHint="Knuckle\nCheck",
                                                                bg_color = Qt.GlobalColor.black, fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # =QColor(16, 201, 78))  # Green
        self.hub_and_bottom_bearing_check_container = CosThetaOutcomeContainer(title ="Hub Check", imageHint="Hub Check",
                                                                               bg_color = Qt.GlobalColor.black,
                                                                               fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.top_bearing_check_container = CosThetaOutcomeContainer(title ="Top Bearing Check", imageHint="Second\nBearing\nCheck",
                                                                    bg_color = Qt.GlobalColor.black,
                                                                    fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.nut_and_plate_washer_check_container = CosThetaOutcomeContainer(title = "Nut & Washer Check",imageHint="Nut &\nPlate Washer\nCheck",
                                                                             bg_color = Qt.GlobalColor.black,
                                                                             fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.tightening_torque1_check_container = CosThetaOutcomeContainer(title = "Tightening Torque 1",imageHint="Tightening\nTorque 1",
                                                                           bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.free_rotations_check_container = CosThetaOutcomeContainer(title = "Free Rotations", imageHint="Free\nRotations\nto settle\nBearing",
                                                                       bg_color = Qt.GlobalColor.black,
                                                                       fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.bunk_for_component_press_check_container = CosThetaOutcomeContainer(title ="Bunk - Component Press", imageHint="Place\nBunk for\n Component Press",
                                                                                 bg_color = Qt.GlobalColor.black,
                                                                                 fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.component_press_check_container = CosThetaOutcomeContainer(title ="Component Press", imageHint="Component\nPress",
                                                                        bg_color = Qt.GlobalColor.black,
                                                                        fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.no_bunk_after_component_press_check_container = CosThetaOutcomeContainer(title ="Remove bunk", imageHint="Remove\nBunk",
                                                                                      bg_color = Qt.GlobalColor.black,
                                                                                      fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.tightening_torque2_check_container = CosThetaOutcomeContainer(title ="Tightening Torque 2",imageHint="Tightening\nTorque 2",
                                                                           bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.splitpin_and_washer_check_container = CosThetaOutcomeContainer(title = "Split Pin & Washer", imageHint="Split Pin\nAnd\nWasher\nCheck",
                                                                           bg_color = Qt.GlobalColor.black,
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.cap_check_container = CosThetaOutcomeContainer(title = "Cap Check", bg_color = Qt.GlobalColor.black, imageHint="Cap\nCheck",
                                                                           fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.bunk_check_container = CosThetaOutcomeContainer(title ="Bunk Check", bg_color = Qt.GlobalColor.black, imageHint="Bunk\nCheck",
                                                             fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue
        self.cap_press_result_container = CosThetaOutcomeContainer(title = "Cap Press Result", bg_color = Qt.GlobalColor.black, imageHint="Cap\nPress\nResult",
                                                                   fg_color = Qt.GlobalColor.white, forceTopLabelFontSizeTo=CosThetaResultsContainer.topLabelFontSizeInOutcomeContainers) # QColor(10, 194, 228))  # Blue

        self.labelHeight = CosThetaConfigurator.getInstance().getLabelInitialHeight()

        initialInstruction : str = f"  {self.longestInstruction}  "
        self.instructionLabel = QLabel(initialInstruction)
        self.instructionLabel.setContentsMargins(0, 0, 0, 0)
        self.instructionLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.instructionLabel.setStyleSheet(instructionAwaitedStylesheet.format(
            QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(0)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(grid_layout)

        grid_layout.addWidget(self.knuckle_check_container, 0, 0, 1, 1)
        grid_layout.addWidget(self.hub_and_bottom_bearing_check_container, 0, 1, 1, 1)
        grid_layout.addWidget(self.top_bearing_check_container, 0, 2, 1, 1)
        grid_layout.addWidget(self.nut_and_plate_washer_check_container, 0, 3, 1, 1)
        grid_layout.addWidget(self.tightening_torque1_check_container, 0, 4, 1, 1)
        grid_layout.addWidget(self.free_rotations_check_container, 0, 5, 1, 1)
        grid_layout.addWidget(self.bunk_for_component_press_check_container, 0, 6, 1, 1)

        grid_layout.addWidget(self.component_press_check_container, 1, 0, 1, 1)
        grid_layout.addWidget(self.no_bunk_after_component_press_check_container, 1, 1, 1, 1)
        grid_layout.addWidget(self.tightening_torque2_check_container, 1, 2, 1, 1)
        grid_layout.addWidget(self.splitpin_and_washer_check_container, 1, 3, 1, 1)
        grid_layout.addWidget(self.cap_check_container, 1, 4, 1, 1)
        grid_layout.addWidget(self.bunk_check_container, 1, 5, 1, 1)
        grid_layout.addWidget(self.cap_press_result_container, 1, 6, 1, 1)

        grid_layout.addWidget(self.instructionLabel, 2, 0, 1, 7)

        # ********************************** DEFINE HORIZONTAL SPACE OF EACH COLUMN *********************************

        # Set equal column stretch for all 7 columns to ensure uniform width
        for col in range(7):
            grid_layout.setColumnStretch(col, 1)

        # ********************************** DEFINE VERTICAL SPACE OF EACH ROW *********************************

        grid_layout.setRowStretch(0, 7)  # Row 1
        grid_layout.setRowStretch(1, 7)  # Row 2
        grid_layout.setRowStretch(2, 2)  # Row 3 (7 times the stretch of others)
        grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding), 3, 0, 1, 7)

        self.update()

    # ****************************************

    # ****************************************

    # Call this after self.show(), then QApplication.processEvents(), then self.resultsContainer.calculateAndSetIdealFontForInstructionLabel()
    def calculateAndSetIdealFontForInstructionLabel(self):
        currentInstructionFont = self.instructionLabel.font()
        currentFontPointSize = currentInstructionFont.pointSize()
        currentInstructionFont.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(currentInstructionFont)
        labelTextRect = metrics.boundingRect(0, 0, 0, 0, Qt.AlignmentFlag.AlignCenter, self.instructionLabel.text())
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        instructionLabelWidth = self.instructionLabel.width()
        instructionLabelHeight = self.instructionLabel.height()
        reductionFactor = min(instructionLabelWidth * 1.0 / textWidth,
                              instructionLabelHeight * 1.0 / textHeight) * 0.95
        fontSize = int(reductionFactor * currentFontPointSize)
        currentInstructionFont.setPointSize(fontSize)
        self.instructionLabel.setFont(currentInstructionFont)

    def setKnuckleCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.knuckle_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.knuckle_check_container.setImageAndResult(value, result)
        else:
            self.knuckle_check_container.setDefault()

    def setHubAndBottomBearingCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.hub_and_bottom_bearing_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.hub_and_bottom_bearing_check_container.setImageAndResult(value, result)
        else:
            self.hub_and_bottom_bearing_check_container.setDefault()

    def setTopBearingCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.top_bearing_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.top_bearing_check_container.setImageAndResult(value, result)
        else:
            self.top_bearing_check_container.setDefault()

    def setNutAndPlateWasherCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.nut_and_plate_washer_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.nut_and_plate_washer_check_container.setImageAndResult(value, result)
        else:
            self.nut_and_plate_washer_check_container.setDefault()

    def setTighteningTorque1Data(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.tightening_torque1_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.tightening_torque1_check_container.setImageAndResult(value, result)
        else:
            self.tightening_torque1_check_container.setDefault()

    def setFreeRotationsData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.free_rotations_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.free_rotations_check_container.setImageAndResult(value, result)
        else:
            self.free_rotations_check_container.setDefault()

    def setBunkForComponentPressData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.bunk_for_component_press_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.bunk_for_component_press_check_container.setImageAndResult(value, result)
        else:
            self.bunk_for_component_press_check_container.setDefault()

    def setComponentPressData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.component_press_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.component_press_check_container.setImageAndResult(value, result)
        else:
            self.component_press_check_container.setDefault()

    def setNoBunkAfterComponentPress(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.no_bunk_after_component_press_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.no_bunk_after_component_press_check_container.setImageAndResult(value, result)
        else:
            self.no_bunk_after_component_press_check_container.setDefault()

    def setTighteningTorque2Data(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.tightening_torque2_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.tightening_torque2_check_container.setImageAndResult(value, result)
        else:
            self.tightening_torque2_check_container.setDefault()

    def setSplitPinAndWasherCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.splitpin_and_washer_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.splitpin_and_washer_check_container.setImageAndResult(value, result)
        else:
            self.splitpin_and_washer_check_container.setDefault()

    def setCapCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.cap_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.cap_check_container.setImageAndResult(value, result)
        else:
            self.cap_check_container.setDefault()

    def setBunkCheckData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.bunk_check_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.bunk_check_container.setImageAndResult(value, result)
        else:
            self.bunk_check_container.setDefault()

    def setCapPressResultData(self, value, result):
        if isinstance(value, str) or isinstance(value, float) or isinstance(value, int):
            self.cap_press_result_container.setTextAndResult(f"{value}", result)
        elif isinstance(value, get_args(Union[QImage, QPixmap, ndarray])):
            self.cap_press_result_container.setImageAndResult(value, result)
        else:
            self.cap_press_result_container.setDefault()

    def setInstruction(self, value):
        self.instructionLabel.setText(f"{value}")

    # ****************************************

    def setKnuckleCheckDefault(self):
        self.knuckle_check_container.setDefault()

    def setHubAndBottomBearingCheckDefault(self):
        self.hub_and_bottom_bearing_check_container.setDefault()

    def setTopBearingCheckDefault(self):
        self.top_bearing_check_container.setDefault()

    def setNutAndPlateWasherCheckDefault(self):
        self.nut_and_plate_washer_check_container.setDefault()

    def setTighteningTorque1Default(self):
        self.tightening_torque1_check_container.setDefault()

    def setFreeRotationDefault(self):
        self.free_rotations_check_container.setDefault()

    def setBunkForComponentPressDefault(self):
        self.bunk_for_component_press_check_container.setDefault()

    def setComponentPressDefault(self):
        self.component_press_check_container.setDefault()

    def setNoBunkAfterComponentPressDefault(self):
        self.no_bunk_after_component_press_check_container.setDefault()

    def setTighteningTorque2Default(self):
        self.tightening_torque2_check_container.setDefault()

    def setSplitPinAndWasherCheckDefault(self):
        self.splitpin_and_washer_check_container.setDefault()

    def setCapCheckDefault(self):
        self.cap_check_container.setDefault()

    def setBunkForCapPressCheckDefault(self):
        self.bunk_check_container.setDefault()

    def setCapPressResultDefault(self):
        self.cap_press_result_container.setDefault()

    def setInstructionDefault(self):
        self.instructionLabel.setText("Instruction Label")

    # ****************************************

    def setInitialDefaultDisplay(self):
        self.setKnuckleCheckDefault()
        self.setHubAndBottomBearingCheckDefault()
        self.setTopBearingCheckDefault()
        self.setNutAndPlateWasherCheckDefault()
        self.setTighteningTorque1Default()
        self.setFreeRotationDefault()
        self.setBunkForComponentPressDefault()
        self.setComponentPressDefault()
        self.setNoBunkAfterComponentPressDefault()
        self.setTighteningTorque2Default()
        self.setSplitPinAndWasherCheckDefault()
        self.setCapCheckDefault()
        self.setBunkForCapPressCheckDefault()
        self.setCapPressResultDefault()
        self.setInstructionDefault()

    def setInProcessDefaultDisplay(self):
        # print(f"setInProcessDefaultDisplay() called")
        self.setKnuckleCheckDefault()
        self.setHubAndBottomBearingCheckDefault()
        self.setTopBearingCheckDefault()
        self.setNutAndPlateWasherCheckDefault()
        self.setTighteningTorque1Default()
        self.setFreeRotationDefault()
        self.setBunkForComponentPressDefault()
        self.setComponentPressDefault()
        self.setNoBunkAfterComponentPressDefault()
        self.setTighteningTorque2Default()
        self.setSplitPinAndWasherCheckDefault()
        self.setCapCheckDefault()
        self.setBunkForCapPressCheckDefault()
        self.setCapPressResultDefault()

    def displayDefault(self):
        self.setInitialDefaultDisplay()

