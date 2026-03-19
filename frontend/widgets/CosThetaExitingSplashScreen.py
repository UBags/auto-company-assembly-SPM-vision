from PySide6.QtWidgets import QSplashScreen, QProgressBar
from PySide6.QtCore import Qt

from frontend.frontendutils.CosThetaImageUtils import *
from frontend.CosThetaMonitorDimensions import *
import time
from time import sleep

app = getAppInstance()

class CosThetaExitingSplashScreen(QSplashScreen):

    logger = None

    def __init__(self, path, delayTime):
        super().__init__()
        self._path = path
        self._delayTime = delayTime
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        pixmap = QPixmap(self._path)
        self.setPixmap(pixmap)
        self.setEnabled(False)

    def show(self) -> None:
        # add fade to splashscreen
        self.progressBar = QProgressBar(self)
        spacing = 50
        self.progressBar.setGeometry(spacing // 2, self.pixmap().height() - spacing, self.pixmap().width() - spacing, 20)
        self.setMask(self.pixmap().mask())
        super().show()
        super().showMessage("<h1><font color='green'>Saving data and preparing for close. Please be patient !</font></h1>", Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                           Qt.GlobalColor.black)
        sleepTime = 0.1
        timeDelay = int(self._delayTime / sleepTime)
        for i in range(timeDelay):
            time.sleep(sleepTime)
            self.progressBar.setValue(i * 100 / timeDelay)
            app.processEvents()


    def display(self):
        # printBoldBlue("Here 1")
        self.show()
        # printBoldBlue("Here 2")
        self.close() # close the splash screen