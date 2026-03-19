from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
# from PySide6.QtCore.Qt import *
from multimethod import multimethod
# from multidispatch import dispatch
from frontend.CosThetaMonitorDimensions import getAppInstance, populateMonitorDimensions
from frontend.CosThetaStylesheets import okLabelStylesheet, notokLabelStylesheet, noResultLabelStylesheet, outcomeLabelStylesheet, whiteBackgroundStylesheet
from frontend.frontendutils.CosThetaLabelUtils import *
from frontend.frontendutils.CosThetaImageUtils import *
from Configuration import *
import cv2
from typing import Union

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosTheta_OK_NotOK_TotalContainer(QWidget):

    spacingBetweenWidgets = 5
    OK_STYLESHEET = okLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    NOT_OK_STYLESHEET = notokLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    TOTAL_STYLESHEET = outcomeLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    WHITE_BG_STYLESHEET = whiteBackgroundStylesheet.format(QColor(Qt.GlobalColor.black).name())

    def __init__(self, cust_name : str, med_name : str, name : str, width : int, height : int, todaysOKCount : int = 0, todaysTotalCount : int = 0, labelHeight : Union[float, int] = 50.):
        super().__init__()
        self.setAcceptDrops(False)
        self.setObjectName(f"{name}_CosTheta_OK_NotOK_TotalContainerWidget")
        self.cust_name = cust_name
        self.med_name = med_name
        self.width = width
        self.height = height
        self.labelHeight = labelHeight
        self.imageHeight = int(self.height)

        self.okCount = todaysOKCount
        self.totalCount = todaysTotalCount
        self.notokCount = self.totalCount - self.okCount

        labelFontSize = int(CosThetaConfigurator.getInstance().getInitialFontsize() * 2)
        self.labelFont = QFont(CosThetaConfigurator.getInstance().getFontFace(), labelFontSize)
        self.labelFont.setWeight(QFont.Weight.Bold)
        # metrics = QFontMetrics(self.labelFont)
        # labelTextRect = metrics.boundingRect(0, 0, 0, 0,
        #                                 Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
        #                                 title)
        # textWidth = labelTextRect.width()
        # textHeight = labelTextRect.height()
        # reductionFactor = min(width * 1.0 / textWidth, labelHeight * 1.0 / textHeight) * 0.90
        # fontSize = int(reductionFactor * labelFontSize)
        # self.labelFont.setPointSize(fontSize)
        # printBold(f"Resized font to {fontSize} for {title}")
        # CosThetaOutcomeContainer.logger.debug(
        #     f"Resized font {CosThetaConfigurator.getInstance().getFontFace()} to {labelFontSize}")
        self.labelFont.setPointSize(labelFontSize)

        self.title_label_ok = QLabel("OK")  # Container's title
        self.title_label_ok.setFont(self.labelFont)
        self.title_label_ok.resize(self.width, int(labelHeight))
        self.title_label_ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label_ok.setStyleSheet(CosTheta_OK_NotOK_TotalContainer.OK_STYLESHEET) # Set the background and foreground color of the container's label
        self.title_label_ok.setFixedHeight(int(labelHeight))
        self.title_label_ok.setFixedWidth(self.width)
        self.title_label_ok.setScaledContents(True)

        self.okCountLabel = QLabel(f"{self.okCount}")  # Container's title
        self.okCountLabel.setFont(self.labelFont)
        self.okCountLabel.resize(self.width, int(labelHeight))
        self.okCountLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.okCountLabel.setStyleSheet(CosTheta_OK_NotOK_TotalContainer.WHITE_BG_STYLESHEET) # Set the background and foreground color of the container's label
        self.okCountLabel.setFixedHeight(int(labelHeight))
        self.okCountLabel.setFixedWidth(self.width)
        self.okCountLabel.setScaledContents(True)


        self.title_label_notok = QLabel("Not OK")  # Container's title
        self.title_label_notok.setFont(self.labelFont)
        self.title_label_notok.resize(self.width, int(labelHeight))
        self.title_label_notok.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label_notok.setStyleSheet(CosTheta_OK_NotOK_TotalContainer.NOT_OK_STYLESHEET) # Set the background and foreground color of the container's label
        self.title_label_notok.setFixedHeight(int(labelHeight))
        self.title_label_notok.setFixedWidth(self.width)
        self.title_label_notok.setScaledContents(True)

        self.notokCountLabel = QLabel(f"{self.notokCount}")  # Container's title
        self.notokCountLabel.setFont(self.labelFont)
        self.notokCountLabel.resize(self.width, int(labelHeight))
        self.notokCountLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notokCountLabel.setStyleSheet(CosTheta_OK_NotOK_TotalContainer.WHITE_BG_STYLESHEET) # Set the background and foreground color of the container's label
        self.notokCountLabel.setFixedHeight(int(labelHeight))
        self.notokCountLabel.setFixedWidth(self.width)
        self.notokCountLabel.setScaledContents(True)

        self.title_label_total = QLabel("Total")  # Container's title
        self.title_label_total.setFont(self.labelFont)
        self.title_label_total.resize(self.width, int(labelHeight))
        self.title_label_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label_total.setStyleSheet(CosTheta_OK_NotOK_TotalContainer.TOTAL_STYLESHEET) # Set the background and foreground color of the container's label
        self.title_label_total.setFixedHeight(int(labelHeight))
        self.title_label_total.setFixedWidth(self.width)
        self.title_label_total.setScaledContents(True)

        self.totalCountLabel = QLabel(f"{self.totalCount}")  # Container's title
        self.totalCountLabel.setFont(self.labelFont)
        self.totalCountLabel.resize(self.width, int(labelHeight))
        self.totalCountLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.totalCountLabel.setStyleSheet(CosTheta_OK_NotOK_TotalContainer.WHITE_BG_STYLESHEET) # Set the background and foreground color of the container's label
        self.totalCountLabel.setFixedHeight(int(labelHeight))
        self.totalCountLabel.setFixedWidth(self.width)
        self.totalCountLabel.setScaledContents(True)

        self.holding_frame = QFrame()  # Main container to hold all TaskWidget objects
        self.holding_frame.setObjectName(f"{name}_OutcomeContainerFrame")
        self.holding_frame_hboxlayout = QHBoxLayout()
        self.holding_frame_hboxlayout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignVCenter)

        self.holding_frame_hboxlayout.setContentsMargins(0, 0, 0, 0)
        self.holding_frame_hboxlayout.addWidget(self.title_label_ok)
        self.holding_frame_hboxlayout.addWidget(self.okCountLabel)
        self.holding_frame_hboxlayout.addSpacing(CosTheta_OK_NotOK_TotalContainer.spacingBetweenWidgets)
        self.holding_frame_hboxlayout.addWidget(self.title_label_notok)
        self.holding_frame_hboxlayout.addWidget(self.notokCountLabel)
        self.holding_frame_hboxlayout.addSpacing(CosTheta_OK_NotOK_TotalContainer.spacingBetweenWidgets)
        self.holding_frame_hboxlayout.addWidget(self.title_label_total)
        self.holding_frame_hboxlayout.addWidget(self.totalCountLabel)
        self.holding_frame.setLayout(self.holding_frame_hboxlayout)

        # CosTheta_TwoOutcomesContainer.logger.debug(f"Creating QFrame {self.holding_frame.objectName()}")
        # Main layout for container class
        self.container_vboxlayout = QVBoxLayout()
        self.container_vboxlayout.setContentsMargins(0, 0, 0, 0)
        self.container_vboxlayout.setSpacing(0)  # No space between widgets
        self.container_vboxlayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.container_vboxlayout.addWidget(self.holding_frame)

        self.setLayout(self.container_vboxlayout)
        self.setMaximumSize(self.width, self.height)
        self.update()

    def sizeHint(self):
        return QSize(self.width, self.height)

    def incrementOKCount(self, incrementCounter : int = 0):
        if incrementCounter == 0:
            incrementCounter = CosThetaConfigurator.getInstance().getNoOfBottlesPerImage(cust_name=self.cust_name, med_name=self.med_name)
        self.okCount += incrementCounter
        self.totalCount = self.okCount + self.notokCount
        self.okCountLabel.setText(f"{self.okCount}")
        self.totalCountLabel.setText(f"{self.totalCount}")
        self.update()

    def incrementNotOKCount(self, incrementCounter : int = 0):
        if incrementCounter == 0:
            incrementCounter = CosThetaConfigurator.getInstance().getNoOfBottlesPerImage(cust_name=self.cust_name, med_name=self.med_name)
        self.notokCount += incrementCounter
        self.totalCount = self.okCount + self.notokCount
        self.notokCountLabel.setText(f"{self.notokCount}")
        self.totalCountLabel.setText(f"{self.totalCount}")
        self.update()

    def setDefault(self):
        self.okCount = 0
        self.notokCount = 0
        self.totalCount = self.okCount + self.notokCount
        self.okCountLabel.setText(f"{self.okCount}")
        self.notokCountLabel.setText(f"{self.notokCount}")
        self.totalCountLabel.setText(f"{self.totalCount}")
        self.update()

    def displayDefault(self):
        self.setDefault()

    def goToDefault(self):
        self.setDefault()
