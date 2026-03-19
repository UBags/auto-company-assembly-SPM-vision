from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QMessageBox
from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool, Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction
from PySide6.QtWidgets import QSizePolicy, QWidget, QLabel, QFrame
from frontend.frontendutils.CosThetaImageUtils import *

class CosThetaQHLine(QFrame):
    def __init__(self):
        super(CosThetaQHLine, self).__init__()
        self.setFixedHeight(5)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

class CosThetaQVLine(QFrame):
    def __init__(self):
        super(CosThetaQVLine, self).__init__()
        self.setFixedWidth(5)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
