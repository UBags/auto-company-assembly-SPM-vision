from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QPainter, QPen, QBrush, Qt
from PySide6.QtWidgets import QPushButton

from frontend.CosThetaStylesheets import *
from utils.CosThetaFileUtils import *

class CosThetaRoundButton(QPushButton):

    logger = None

    def __init__(self, text, bordersize, outlineColor, fillColor):
        super(CosThetaRoundButton, self).__init__()
        self.bordersize = bordersize
        self.outlineColor = outlineColor
        self.fillColor = fillColor
        self.setText(text)

    def paintEvent(self, event):
        # Create the painter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Create the path
        path = QPainterPath()
        # Set painter colors to given values.
        pen = QPen(self.outlineColor, self.bordersize)
        painter.setPen(pen)
        brush = QBrush(self.fillColor)
        painter.setBrush(brush)

        rect = QRectF(event.rect())
        # Slighly shrink dimensions to account for bordersize.
        rect.adjust(self.bordersize/2, self.bordersize/2, -self.bordersize/2, -self.bordersize/2)

        # Add the rect to path.
        path.addRoundedRect(rect, 10, 10)
        painter.setClipPath(path)

        # Fill shape, draw the border and center the text.
        painter.fillPath(path, painter.brush())
        painter.strokePath(path, painter.pen())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


