from PySide6 import QtCore
from PySide6.QtCore import QSize
from PySide6.QtGui import QLinearGradient, QPainter
from PySide6.QtWidgets import QPushButton

from frontend.CosThetaStylesheets import *
from utils.CosThetaFileUtils import *

# def tearDown():
#     del app
#     return super().tearDown()

class CosThetaRoundButtonWithColorGradient(QPushButton):
    """ docstring for RoundEdgeButton"""

    logger = None

    def __init__(self,text=None, width = 80, height = 20, parent=None):
        super(CosThetaRoundButtonWithColorGradient, self).__init__(parent)
        super().setMinimumSize(QSize(width, height))
        self.height = height
        if text:
            self.setText(text)

    def paintEvent(self, ev):
        btnPaint = QPainter(self)
        btnGradient = QLinearGradient(QtCore.QRectF(self.rect()).topLeft(), QtCore.QRectF(self.rect()).bottomLeft())
        btnGradient.setColorAt(0.8, QtCore.Qt.GlobalColor.black)
        btnGradient.setColorAt(0.1, QtCore.Qt.gray)
        btnGradient.setColorAt(0.8, QtCore.Qt.GlobalColor.black)
        btnPaint.setBrush(btnGradient)
        btnPaint.drawRoundedRect(self.rect(), 8, 8)
        btnPaint.end()

