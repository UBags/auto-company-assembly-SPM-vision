from PySide6.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout
from PySide6.QtCore import Qt

from frontend.frontendutils.CosThetaImageUtils import *


class CosThetaToggleMessageContainer(QWidget):

    logger = None

    def __init__(self, okText, notokText, okStyleSheet, notokStyleSheet, font, okforegroundColor, notokforegroundColor, minimumWidth) :

        super().__init__()
        self._okText = okText
        self._notokText = notokText
        self._okStyleSheet = okStyleSheet
        self._notokStyleSheet = notokStyleSheet
        self._font = font
        self._okforegroundColor = okforegroundColor
        self._notokforegroundColor = notokforegroundColor
        self._status = True
        self._minimumWidth = minimumWidth
        self.setMinimumWidth(self._minimumWidth)
        self.setObjectName("ToggleMessageContainer")

        self._container_label = QLabel(self._notokText) # Container's title
        self._container_label.setStyleSheet(self._notokStyleSheet.format(self._notokforegroundColor))
        self._container_label.setFont(self._font)
        # This centers the text in the label, and doesn't affect the size (width, height) of the label
        self._container_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_frame = QFrame() # Main container to hold the object
        container_frame.setObjectName("ToggleMessage_ContainerFrame")

        frame_v_box = QVBoxLayout()
        frame_v_box.insertWidget(-1, self._container_label)
        frame_v_box.setSpacing(0)
        # If one adds Qt.AlignmentFlag.AlignCenter, it minimises the size (width, height) of the label. Hence, avoid completely !
        frame_v_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        frame_v_box.setContentsMargins(0, 0, 0, 0)
        container_frame.setLayout(frame_v_box)

        message_v_box = QVBoxLayout()
        message_v_box.insertWidget(-1, container_frame)
        message_v_box.setSpacing(0)
        # If one adds Qt.AlignmentFlag.AlignCenter, it minimises the size (width, height) of the label. Hence, avoid completely !
        message_v_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        message_v_box.setContentsMargins(0, 0, 0, 0)
        self.setLayout(message_v_box)

    def updateStatus(self, currentStatus : bool):
        self._status = currentStatus
        if self._status:
            self._container_label.setText(self._okText)
            self._container_label.setStyleSheet(self._okStyleSheet.format(self._okforegroundColor))
        else:
            self._container_label.setText(self._notokText)
            self._container_label.setStyleSheet(self._notokStyleSheet.format(self._notokforegroundColor))

    def setFont(self, newFont):
        self._font = newFont
        self._container_label.setFont(newFont)

    def setAlignment(self, newAlignment):
        self._container_label.setAlignment(newAlignment)

    def setOKText(self, newOkText):
        self._okText = newOkText

    def setNotOKText(self, newNotOkText):
        self._notokText = newNotOkText

    def setWordWrap(self, value = True):
        self._container_label.setWordWrap(value)

    def setMinimumHeight(self, minHeight):
        self._container_label.setMinimumHeight(minHeight)

