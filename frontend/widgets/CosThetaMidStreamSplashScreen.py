from PySide6.QtWidgets import QSplashScreen, QProgressBar

from frontend.widgets.CosThetaResultsContainer import *
from frontend.frontendutils.CosThetaImageUtils import *
from frontend.CosThetaMonitorDimensions import *
from time import time

app = getAppInstance()

class CosThetaMidstreamSplashScreen(QSplashScreen):

    logger = None

    def __init__(self, path, message, delayTime):
        super().__init__()
        self._path = path
        self._message = message
        self._delayTime = delayTime
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        pixmap = QPixmap(self._path)
        self.setPixmap(pixmap)
        self.setEnabled(False)

    def show(self) -> None:
        # add fade to splashscreen
        progressBar = QProgressBar(self)
        spacing = 50
        progressBar.setGeometry(spacing / 2, self.pixmap().height() - spacing, self.pixmap().width() - spacing, 20)
        self.setMask(self.pixmap().mask())
        super().show()
        super().showMessage(f"<h1><font color='blue'>{self._message}</font></h1>", Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                           Qt.GlobalColor.black)
        sleepTime = 0.1
        timeDelay = int(self._delayTime / sleepTime)
        for i in range(timeDelay):
            time.sleep(sleepTime)
            progressBar.setValue(i * 100 / timeDelay)
            app.processEvents()


    def display(self):
        # printBoldBlue("Here 1")
        # CosThetaMidstreamSplashScreen.logger.debug('About to show midstream splash screen')
        self.show()
        # printBoldBlue("Here 2")
        # CosThetaMidstreamSplashScreen.logger.debug('About to close midstream splash screen')
        # self.setVisible(False)
        self.close() # close the splash screen

