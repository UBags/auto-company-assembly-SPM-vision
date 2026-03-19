from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QVBoxLayout, QMessageBox
from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool, Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction
from PySide6.QtWidgets import QSizePolicy, QWidget, QLabel, QFrame
from frontend.frontendutils.CosThetaImageUtils import *

from frontend.CosThetaMonitorDimensions import *


class SuccessWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self):
        super().__init__()
        left = (getMonitorWidth() * 2) // 6
        top =  (getMonitorHeight() * 2) // 6
        width = (getMonitorWidth() * 1) // 3
        height = (getMonitorHeight() * 1) // 3
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        self.setGeometry(left, top, width, height)
        layout = QVBoxLayout()
        self.label = QLabel()
        anImage = createImage(text="Operation complete", imageDimensions=((getMonitorWidth() // 3) - 5, (getMonitorHeight() // 3) - 5),
                                        fontColor=QColor(15, 15, 15), replaceChar=[' ',' '], backgroundColor = QColor(125, 210, 185))
        self.successImage = getPixmapImage(anImage)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.label.setPixmap(self.successImage)
        self.setWindowFlags(Qt.FramelessWindowHint)

    def setPixmap(self, pixmap):
        self.label.setPixmap(pixmap)