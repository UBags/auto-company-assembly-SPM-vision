from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QVBoxLayout, QMessageBox
from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool, Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QSizePolicy, QWidget, QLabel, QFrame

from frontend.CosThetaMonitorDimensions import *

class PictureDisplayWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self):
        super().__init__()
        left = (getMonitorWidth() * 1) // 6
        top =  (getMonitorHeight() * 1) // 6
        width = (getMonitorWidth() * 2) // 3
        height = (getMonitorHeight() * 2) // 3
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        self.setGeometry(left, top, width, height)
        layout = QVBoxLayout()
        self.label = QLabel()
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setWindowFlags(Qt.FramelessWindowHint)

    def setPixmap(self, pixmap):
        self.label.setPixmap(pixmap)
