from PySide6 import QtCore
from PySide6.QtGui import QLinearGradient
from PySide6.QtWidgets import QWidget, QHBoxLayout

from frontend.widgets.CosThetaRoundButtonWithColorGradient import CosThetaRoundButtonWithColorGradient
from frontend.frontendutils.CosThetaImageUtils import *
from Configuration import *

# def tearDown():
#     del app
#     return super().tearDown()

class CosThetaControlBar(QWidget):
    """ docstring for ControlBar"""

    logger = None

    def __init__(self, parent=None, width = 440, height = 100):
        super(CosThetaControlBar, self).__init__(parent)
        # CosThetaControlBar.logger.debug(f"Resized CosThetaControlBar to [{width},{height}]")
        self.resize(width, height)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setWindowTitle("QLinearGradient Vertical Gradient ")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # CosThetaControlBar.logger.debug(f"Set CosThetaControlBar to FramelessWindow, Vertical linear gradient, translucent")
        self.buildUi()

    def mousePressEvent(self, event):
        self.offset = event.scenePosition()

    def mouseMoveEvent(self, event):
        try:
            p = event.globalPosition()
            globalPos = p.toPoint()
            self.dragPos = globalPos
            # x=event.globalX()
            # y=event.globalY()
            x=globalPos.x()
            y=globalPos.y()
            x_w = self.offset.x()
            y_w = self.offset.y()
            self.move(x-x_w, y-y_w)
        except: pass

    def paintEvent(self, ev):
        painter = QPainter(self)
        gradient = QLinearGradient(QtCore.QRectF(self.rect()).topLeft(),QtCore.QRectF(self.rect()).bottomLeft())
        gradient.setColorAt(0.0, QtCore.Qt.GlobalColor.black)
        gradient.setColorAt(0.4, QtCore.Qt.gray)
        gradient.setColorAt(0.7, QtCore.Qt.GlobalColor.black)
        painter.setBrush(gradient)
        painter.drawRoundedRect(0, 0, 440, 100, 20.0, 20.0)
        painter.end()

    def buildUi(self):
        CosThetaControlBar.logger.debug(f"Building CosThetaControlBar UI")
        self.hoelayout = QHBoxLayout()
        self.openBtn = CosThetaRoundButtonWithColorGradient("Hello")
        self.backBtn = CosThetaRoundButtonWithColorGradient()
        self.pausBtn = CosThetaRoundButtonWithColorGradient()
        self.nextBtn = CosThetaRoundButtonWithColorGradient()
        self.hoelayout.addStretch(1)
        self.hoelayout.addWidget(self.openBtn)
        self.hoelayout.addStretch(1)
        self.hoelayout.addWidget(self.backBtn)
        self.hoelayout.addStretch(1)
        self.hoelayout.addWidget(self.pausBtn)
        self.hoelayout.addStretch(1)
        self.hoelayout.addWidget(self.nextBtn)
        self.hoelayout.addStretch(1)
        self.setLayout(self.hoelayout)
        CosThetaControlBar.logger.debug(f"Built CosThetaControlBar UI")
