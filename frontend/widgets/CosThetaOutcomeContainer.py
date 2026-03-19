from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import *
from multimethod import multimethod
# from multidispatch import dispatch
from frontend.CosThetaMonitorDimensions import getAppInstance, populateMonitorDimensions
from frontend.CosThetaStylesheets import okLabelStylesheet, notokLabelStylesheet, noResultLabelStylesheet, \
    outcomeLabelStylesheet
from frontend.frontendutils.CosThetaLabelUtils import *
from frontend.frontendutils.CosThetaImageUtils import *
from Configuration import *
import cv2

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosThetaOutcomeContainer(QWidget):

    spacingBetweenWidgets = 5
    logger = None
    OK_STYLESHEET = okLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    NOT_OK_STYLESHEET = notokLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    RESULT_AWAITED_STYLESHEET = noResultLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())

    def __init__(self, title, width, height, image, labelHeight = 50., bg_color = Qt.GlobalColor.white, fg_color = Qt.GlobalColor.black, default_status = "  Result Awaited  ", forceTopLabelFontSizeTo : int = 0, forceMiddleLabelFontSizeTo : int = 0, forceBottomLabelFontSizeTo : int = 0):
        super().__init__()
        self.setAcceptDrops(False)
        self.setObjectName(f"{title}_OutcomeContainerWidget")
        self.width = width
        self.height = height
        self.labelHeight = int(labelHeight)
        self.default_status = default_status
        self.currentStatus = self.default_status
        self.forceTopLabelFontSizeTo = forceTopLabelFontSizeTo
        self.forceMiddleLabelFontSizeTo = forceMiddleLabelFontSizeTo
        self.forceBottomLabelFontSizeTo = forceBottomLabelFontSizeTo

        self.setContentsMargins(0,0,0,0)

        self.default_pixmap = getPixmapImage(image)
        self.imageWidth = self.default_pixmap.width()
        self.imageHeight = self.default_pixmap.height()
        self.currentPixmap = self.default_pixmap

        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.setContentsMargins(0, 0, 0, 0)
        self.vboxlayout.setSpacing(0)
        self.vboxlayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # CosThetaOutcomeContainer.logger.debug(f"Creating OutcomeContainer {self.objectName()}")
        labelFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
        self.labelFont = QFont(CosThetaConfigurator.getInstance().getFontFace(), labelFontSize)
        self.labelFont.setWeight(QFont.Weight.Bold)

        if forceTopLabelFontSizeTo > 0:
            self.labelFont.setPointSize(forceTopLabelFontSizeTo)
        else:
            metrics = QFontMetrics(self.labelFont)
            labelTextRect = metrics.boundingRect(0, 0, 0, 0,
                                            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                            title)
            textWidth = labelTextRect.width()
            textHeight = labelTextRect.height()
            reductionFactor = min(width * 1.0 / textWidth, labelHeight * 1.0 / textHeight) * 0.90
            fontSize = int(reductionFactor * labelFontSize)
            self.labelFont.setPointSize(fontSize)

        self.title_label = QLabel(title)  # Container's title
        self.title_label.setFont(self.labelFont)
        self.title_label.resize(self.width, self.labelHeight)
        # self.outcome_container_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(outcomeLabelStylesheet.format(QColor(fg_color).name())) # Set the background and foreground color of the container's label
        self.title_label.setFixedHeight(self.labelHeight)
        self.title_label.setFixedWidth(self.width)
        # self.title_label.setScaledContents(True)

        # self.image_frame_vboxlayout.setGeometry(QRect(0,0,self.width, self.height))
        # self.image_frame_vboxlayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.image_label = QLabel()  # Image label
        self.image_label.setFixedWidth(self.imageWidth)
        self.image_label.setFixedHeight(self.imageHeight)
        self.image_label.setContentsMargins(0,0,0,0)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        self.image_label.setPixmap(self.default_pixmap)

        # Use a horizontal layout for centering the image
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0,0,0,0)
        hbox.setSpacing(0)
        hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center horizontally
        hbox.addWidget(self.image_label)

        self.vboxlayout.addWidget(self.title_label)
        self.vboxlayout.addSpacing(1)
        self.vboxlayout.addLayout(hbox)
        self.vboxlayout.addSpacing(1)

        self.result_label = createResultLabel(result = self.currentStatus, width = self.width, labelHeight = self.labelHeight, forceLabelFontSizeTo=forceBottomLabelFontSizeTo)  # Label
        self.vboxlayout.addWidget(self.result_label)
        self.setLayout(self.vboxlayout)

        self.update()

    def sizeHint(self):
        return QSize(self.width, self.height)

    @multimethod
    def getResultImage(self, result : str):
        if result.upper() == 'OK':
            # CosThetaOutcomeContainer.logger.debug(f"Creating OK result startingImage")
            result_image = createGreenImage(result, imageDimensions=(self.width, self.labelHeight))
        elif result.upper() == 'NOT OK' or result.upper() == 'NOT\bOK':
            # CosThetaOutcomeContainer.logger.debug(f"Creating Not OK result startingImage")
            result_image = createRedImage(result, imageDimensions=(self.width, self.labelHeight))
        else:
            # CosThetaOutcomeContainer.logger.debug(f"Creating blue startingImage with {result}")
            result_image = createBlueImage(result, imageDimensions=(self.width, self.labelHeight))
        return getPixmapImage(result_image)

    @multimethod
    def getResultImage(self, result : float):
        # CosThetaOutcomeContainer.logger.debug(f"Creating blue startingImage with value {result}")
        result = str(result)
        result_image = createBlueImage(result, imageDimensions=(self.width, self.labelHeight))
        return getPixmapImage(result_image)

    @multimethod
    def getResultImage(self, result : str, width : float, height : float):
        if result.upper() == 'OK':
            # CosThetaOutcomeContainer.logger.debug(f"Creating OK result startingImage")
            result_image = createGreenImage(result, imageDimensions=(width, height))
        elif result.upper() == 'NOT OK' or result.upper() == 'NOT\bOK':
            # CosThetaOutcomeContainer.logger.debug(f"Creating Not OK result startingImage")
            result_image = createRedImage(result, imageDimensions=(width, height))
        else:
            # CosThetaOutcomeContainer.logger.debug(f"Creating blue startingImage with {result}")
            result_image = createBlueImage(result, imageDimensions=(width, height))
        return getPixmapImage(result_image)

    @multimethod
    def getResultImage(self, result : int, width : float, height : float):
        # CosThetaOutcomeContainer.logger.debug(f"Creating blue startingImage with {result}")
        result = str(result)
        result_image = createBlueImage(result, imageDimensions=(width, height))
        return getPixmapImage(result_image)

    def getCurrentStatus(self):
        return self.currentStatus

    def getCurrentPixmap(self):
        return self.currentPixmap

    def getResult(self):
        return self.result_label.text()

    def setResult(self, result : Union[str, bool]):
        if isinstance(result, bool):
            if result:
                result = "OK"
            else:
                result = "Not OK"
        if isinstance(result, str):
            if (result == "ok") or (result == "OK"):
                result = "OK"
            elif (result.lower().strip() == "notok") or (result.lower().strip() == "not ok"):
                result = "Not OK"
        # self.result_label.setPixmap(self.getResultImage(result))
        self.result_label.setText(result)
        self.currentStatus = result
        # printPlain(f"About to do comparison of result with value {result.lower()}")
        if result.lower() == 'ok':
            # CosThetaOutcomeContainer.logger.debug(f"Creating OK result label")
            self.result_label.setStyleSheet(okLabelStylesheet.format(
                QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        elif result.lower() == 'not ok':
            # CosThetaOutcomeContainer.logger.debug(f"Creating Not OK result label")
            self.result_label.setStyleSheet(notokLabelStylesheet.format(
                QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        else:
            # CosThetaOutcomeContainer.logger.debug(f"Creating label with {result}")
            self.result_label.setStyleSheet(noResultLabelStylesheet.format(
                QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        self.update()

    def setImage(self, image : QImage | QPixmap | ndarray | str):
        # printPlain("Before setPixmap() - 7")
        pix = getPixmapImage(image)
        pix = resize_pixmap(pix, self.imageWidth, self.imageHeight)
        self.image_label.setPixmap(pix)
        self.currentPixmap = pix
        self.update()

    def setImageAndResult(self, image : QImage | QPixmap | ndarray | str, result : str):
        self.setResult(result)
        self.setImage(image)
        self.update()

    def setDefault(self):
        self.setImageAndResult(self.default_pixmap, self.default_status)

    def displayDefault(self):
        self.setDefault()

    def goToDefault(self):
        self.setDefault()

    def setText(self, text: str):
        if self.getResult().upper() == "OK":
            backgroundcolor = QColor(225, 220, 245)
        elif (self.getResult().upper() == "NOT OK") or (self.getResult().upper() == "NOTOK"):
            backgroundcolor = QColor(255, 185, 185)
            result = "Not OK"
        else:
            backgroundcolor = QColor(206, 206, 206)
        image = createImage(text, imageDimensions=(self.imageWidth, self.imageHeight),
                    fontColor=QColor(Qt.GlobalColor.darkBlue), replaceChar=['=', ' '], backgroundColor=backgroundcolor, forceUseOfFontSizeAs=self.forceMiddleLabelFontSizeTo)
        self.setImage(image)

    def setTextAndResult(self, text: str, result : str):
        # printBoldRed("In setTextAndResult - with ", text, result)
        if result.upper() == "OK":
            backgroundcolor = QColor(225, 220, 245)
        elif (result.upper() == "NOT OK") or (result.upper() == "NOTOK"):
            backgroundcolor = QColor(255, 185, 185)
            result = "Not OK"
        else:
            backgroundcolor = QColor(206, 206, 206)
        image = createImage(text, imageDimensions=(self.imageWidth, self.imageHeight),
                    fontColor=QColor(Qt.GlobalColor.darkBlue), replaceChar=['=', ' '], backgroundColor=backgroundcolor, forceUseOfFontSizeAs=self.forceMiddleLabelFontSizeTo)
        # printPlain("Reached here - 2")
        self.setImageAndResult(image, result)

    def setResultAndText(self, text: str, result : str):
        if result.upper() == "OK":
            backgroundcolor = QColor(225, 220, 245)
        elif (result.upper() == "NOT OK") or (result.upper() == "NOTOK"):
            backgroundcolor = QColor(255, 185, 185)
            result = "Not OK"
        else:
            backgroundcolor = QColor(206, 206, 206)
        image = createImage(text, imageDimensions=(self.imageWidth, self.imageHeight),
                    fontColor=QColor(Qt.GlobalColor.darkBlue), replaceChar=['=', ' '], backgroundColor=backgroundcolor, forceUseOfFontSizeAs=self.forceMiddleLabelFontSizeTo)
        self.setImageAndResult(image, result)

    def setBackgroundAndResult(self, ndarrayimage, result : str, alpha = 0.8):
        if result.upper() == "OK":
            backgroundcolor = QColor(225, 220, 245)
        elif (result.upper() == "NOT OK") or (result.upper() == "NOTOK"):
            backgroundcolor = QColor(255, 185, 185)
            result = "Not OK"
        else:
            backgroundcolor = QColor(206, 206, 206)
        if ndarrayimage is not None:
            width = self.imageWidth
            height = self.imageHeight
            qPixmap : QPixmap = convertNDArrayToPixmap(ndarrayimage)
            pixmap : QPixmap = qPixmap.scaled(width, height, aspectMode = Qt.AspectRatioMode.IgnoreAspectRatio, mode = Qt.TransformationMode.SmoothTransformation)
            self.setImageAndResult(pixmap, result)

    def getImageWidth(self):
        return self.imageWidth

    def getImageHeight(self):
        return self.imageHeight

