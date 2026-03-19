from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QSpacerItem, QSizePolicy, \
    QApplication, QMainWindow
from PySide6.QtGui import *
from multimethod import multimethod
# from multidispatch import dispatch
from frontend.CosThetaMonitorDimensions import getAppInstance, populateMonitorDimensions
from frontend.CosThetaStylesheets import okLabelStylesheet, notokLabelStylesheet, noResultLabelStylesheet, \
    outcomeLabelStylesheet, titleLabelStylesheet, emptyImageStylesheet, numberDisplayStylesheet
from frontend.frontendutils.CosThetaLabelUtils import *
from frontend.frontendutils.CosThetaImageUtils import *
from Configuration import *
import cv2

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosThetaOutcomeContainer(QFrame):

    spacingBetweenWidgets = 5
    logger = None
    OK_STYLESHEET = okLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    NOT_OK_STYLESHEET = notokLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    RESULT_AWAITED_STYLESHEET = noResultLabelStylesheet.format(QColor(Qt.GlobalColor.white).name())
    EMPTY_IMAGE_FONT = QFont('Courier', pointSize=18, weight=QFont.Weight.Bold)
    NUMBER_DISPLAY_FONT = QFont('Courier', pointSize=36, weight=QFont.Weight.Bold)

    def __init__(self, title : str, imageHint : str, bg_color = Qt.GlobalColor.black, fg_color = Qt.GlobalColor.white,
                 default_status = "Result Awaited", forceTopLabelFontSizeTo : int = 0,
                 forceMiddleLabelFontSizeTo : int = 0, forceBottomLabelFontSizeTo : int = 0):

        super().__init__()
        self.setAcceptDrops(False)
        self.setObjectName(f"{title}_OutcomeContainerWidget")
        self.default_status = default_status
        self.currentStatus = self.default_status
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.imageHint = imageHint

        self.setContentsMargins(0,0,0,0)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        self.forceTopLabelFontSizeTo = forceTopLabelFontSizeTo
        self.forceMiddleLabelFontSizeTo = forceMiddleLabelFontSizeTo
        self.forceBottomLabelFontSizeTo = forceBottomLabelFontSizeTo

        self.title_label = QLabel(title)  # Container's title
        self.title_label.setContentsMargins(0,0,0,0)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(titleLabelStylesheet.format(QColor(fg_color).name())) # Set the background and foreground color of the container's label

        self.image_label = QLabel(imageHint)  # Image label
        self.image_label.setContentsMargins(0,0,0,0)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(emptyImageStylesheet)
        self.image_label.setFont(CosThetaOutcomeContainer.EMPTY_IMAGE_FONT)
        # print(f"{self.image_label.width() = }, {self.image_label.height() = }")

        initialResult : str = self.default_status
        self.result_label = QLabel(initialResult)  # Container's title
        self.result_label.setContentsMargins(0,0,0,0)
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if initialResult.lower() == 'ok':
            self.result_label.setStyleSheet(okLabelStylesheet.format(
                QColor(
                    Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        elif initialResult.lower() == 'not ok':
            self.result_label.setStyleSheet(notokLabelStylesheet.format(
                QColor(
                    Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
        else:
            self.result_label.setStyleSheet(noResultLabelStylesheet.format(
                QColor(
                    Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label

        # Set size policies for expansion
        for label in [self.title_label, self.image_label, self.result_label]:
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(grid_layout)

        grid_layout.addWidget(self.title_label, 0, 0)  # Row 0
        grid_layout.addWidget(self.image_label, 1, 0)  # Row 1 (height needs to be emphasized)
        grid_layout.addWidget(self.result_label, 2, 0)  # Row 2


        # Set the row stretch to adjust the height ratios
        grid_layout.setRowStretch(0, 1)  # First row (title) stretch factor
        grid_layout.setRowStretch(1, 5)  # Second row (image) stretch factor
        grid_layout.setRowStretch(2, 1)  # Third row (result) stretch factor
        # Add a vertical spacer to push rows and show stretch effect
        grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding), 3, 0, 1, 2)

        labelFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
        self.titleLabelFont = QFont(CosThetaConfigurator.getInstance().getFontFace(), labelFontSize)
        self.titleLabelFont.setWeight(QFont.Weight.Bold)
        if forceTopLabelFontSizeTo > 0:
            self.titleLabelFont.setPointSize(forceTopLabelFontSizeTo)
            self.title_label.setFont(self.titleLabelFont)

        resultFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
        self.resultFont = QFont(CosThetaConfigurator.getInstance().getFontFace(), resultFontSize)
        self.resultFont.setWeight(QFont.Weight.Bold)
        if forceBottomLabelFontSizeTo > 0:
            self.resultFont.setPointSize(forceBottomLabelFontSizeTo)
            self.result_label.setFont(self.resultFont)

        self.update()
        # self.adjustSize()
        # self.show()
        # QApplication.processEvents()
        # print(f"{self.image_label.width() = }, {self.image_label.height() = }")

    # def createDefaultImageAndShowIt(self, forceUseOfFontSizeAs : int = 0):
    #     defaultImage = createImageAlternateViaCV2(self.imageHint, imageDimensions=(self.image_label.width(), self.image_label.height()),
    #                 forceUseOfFontSizeAs=forceUseOfFontSizeAs, returnPixMapImage=True)
    #     # print(f"Image type = {type(defaultImage)}")
    #     self.setDefaultImage(defaultImage)
    #     self.setDefault()

    def getImageLabelWidth(self):
        return self.image_label.width()

    def getImageLabelHeight(self):
        return self.image_label.height()

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
        pix = resize_pixmap(pix, self.image_label.width(), self.image_label.height())
        self.image_label.setPixmap(pix)
        self.currentPixmap = pix
        self.update()

    def setImageAndResult(self, image : QImage | QPixmap | ndarray | str, result : str):
        self.setResult(result)
        self.setImage(image)
        self.update()

    def setDefaultImage(self, image : QImage | QPixmap | ndarray | str):
        self.default_pixmap = getPixmapImage(image)
        self.currentPixmap = self.default_pixmap
        self.update()

    def setDefault(self):
        # self.setImageAndResult(self.default_pixmap, self.default_status)
        self.image_label.setStyleSheet(emptyImageStylesheet)
        self.image_label.setFont(CosThetaOutcomeContainer.EMPTY_IMAGE_FONT)
        self.image_label.setText(self.imageHint)
        self.setResult(self.default_status)
        self.update()

    def displayDefault(self):
        self.setDefault()

    def goToDefault(self):
        self.setDefault()

    def setText(self, text: str | float | int):
        # if self.getResult().upper() == "OK":
        #     backgroundcolor = QColor(225, 220, 245)
        # elif (self.getResult().upper() == "NOT OK") or (self.getResult().upper() == "NOTOK"):
        #     backgroundcolor = QColor(255, 185, 185)
        #     result = "Not OK"
        # else:
        #     backgroundcolor = QColor(206, 206, 206)
        # image = createImage(text, imageDimensions=(self.image_label.width(), self.image_label.height()),
        #             fontColor=QColor(Qt.GlobalColor.darkBlue), replaceChar=['=', ' '], backgroundColor=backgroundcolor, forceUseOfFontSizeAs=self.forceMiddleLabelFontSizeTo)
        # self.setImage(image)
        self.image_label.setStyleSheet(numberDisplayStylesheet)
        self.image_label.setFont(CosThetaOutcomeContainer.NUMBER_DISPLAY_FONT)
        self.image_label.setText(f"{text}")
        self.update()

    def setTextAndResult(self, text: str | float | int, result : str):
        # printBoldRed("In setTextAndResult - with ", text, result)
        # if result.upper() == "OK":
        #     backgroundcolor = QColor(225, 220, 245)
        # elif (result.upper() == "NOT OK") or (result.upper() == "NOTOK"):
        #     backgroundcolor = QColor(255, 185, 185)
        #     result = "Not OK"
        # else:
        #     backgroundcolor = QColor(206, 206, 206)
        # image = createImage(text, imageDimensions=(self.image_label.width(), self.image_label.height()),
        #             fontColor=QColor(Qt.GlobalColor.darkBlue), replaceChar=['=', ' '], backgroundColor=backgroundcolor, forceUseOfFontSizeAs=self.forceMiddleLabelFontSizeTo)
        # printPlain("Reached here - 2")
        self.image_label.setStyleSheet(numberDisplayStylesheet)
        self.image_label.setFont(CosThetaOutcomeContainer.NUMBER_DISPLAY_FONT)
        self.image_label.setText(f"{text}")
        self.setResult(result)
        self.update()

    def setResultAndText(self, text: str, result : str):
        # if result.upper() == "OK":
        #     backgroundcolor = QColor(225, 220, 245)
        # elif (result.upper() == "NOT OK") or (result.upper() == "NOTOK"):
        #     backgroundcolor = QColor(255, 185, 185)
        #     result = "Not OK"
        # else:
        #     backgroundcolor = QColor(206, 206, 206)
        # image = createImage(text, imageDimensions=(self.image_label.width(), self.image_label.height()),
        #             fontColor=QColor(Qt.GlobalColor.darkBlue), replaceChar=['=', ' '], backgroundColor=backgroundcolor, forceUseOfFontSizeAs=self.forceMiddleLabelFontSizeTo)
        # self.setImageAndResult(image, result)
        self.image_label.setStyleSheet(numberDisplayStylesheet)
        self.image_label.setFont(CosThetaOutcomeContainer.NUMBER_DISPLAY_FONT)
        self.image_label.setText(f"{text}")
        self.setResult(result)
        self.update()

    def setBackgroundAndResult(self, ndarrayimage, result : str, alpha = 0.8):
        # if result.upper() == "OK":
        #     backgroundcolor = QColor(225, 220, 245)
        # elif (result.upper() == "NOT OK") or (result.upper() == "NOTOK"):
        #     backgroundcolor = QColor(255, 185, 185)
        #     result = "Not OK"
        # else:
        #     backgroundcolor = QColor(206, 206, 206)
        if ndarrayimage is not None:
            width = self.image_label.width()
            height = self.image_label.height()
            qPixmap = convertNDArrayToPixmap(ndarrayimage)
            pixmap = qPixmap.scaled(width, height, aspectMode = Qt.AspectRatioMode.IgnoreAspectRatio, mode = Qt.TransformationMode.SmoothTransformation)
            self.setImageAndResult(pixmap, result)

    def getImageWidth(self):
        return self.image_label.width()

    def getImageHeight(self):
        return self.image_label.height()

# Testing out the container
# def main():
#
#     if not QApplication.instance():
#         app = QApplication(sys.argv)
#     else:
#         app = QApplication.instance()
#
#     # Create main window
#     main_window = QMainWindow()
#     main_window.setWindowTitle("CosThetaOutcomeContainer Test")
#
#     # Create central widget and layout
#     central_widget = QWidget()
#     layout = QVBoxLayout(central_widget)
#
#     # # Create a sample image (you can replace this with your own image)
#     # image = QImage(200, 150, QImage.Format.Format_RGB32)
#     # image.fill(Qt.GlobalColor.lightGray)
#
#     # Create CosThetaOutcomeContainer instance
#     outcome_container = CosThetaOutcomeContainer(
#         title="Test Container",
#         imageHint="An\nImage\nHint",
#         bg_color=Qt.GlobalColor.white,
#         fg_color=Qt.GlobalColor.black,
#         default_status="Waiting..."
#     )
#
#     # Add the container to the layout
#     layout.addWidget(outcome_container)
#
#     # Set the central widget
#     main_window.setCentralWidget(central_widget)
#
#     # Show the main window
#     main_window.show()
#
#     # Run the application
#     sys.exit(app.exec())
#
#
# if __name__ == "__main__":
#     main()