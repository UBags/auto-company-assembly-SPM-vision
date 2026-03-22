# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QVBoxLayout, QMessageBox
from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool, Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QSizePolicy, QWidget, QLabel, QFrame

from frontend.CosThetaMonitorDimensions import *

class SimpleMessageContainer(QWidget):

    def __init__(self, text, styleSheet, font, foregroundColor, minimumWidth, name = '') :

        super().__init__()
        self._text = text
        self._styleSheet = styleSheet
        self._font = font
        self._foregroundColor = foregroundColor
        self._minimumWidth = minimumWidth
        # self.setMinimumWidth(self._minimumWidth)
        self.setObjectName(f"SimpleMessageContainer_{name}")

        self._container_label = QLabel(self._text) # Container's title
        self._container_label.setContentsMargins(0, 0, 0, 0)
        self._container_label.setStyleSheet(self._styleSheet.format(self._foregroundColor))
        self._container_label.setFont(self._font)
        self._container_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._container_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # container_frame = QFrame() # Main container to hold the object
        # container_frame.setObjectName(f"SimpleMessage_ContainerFrame_{name}")
        # frame_v_box_layout = QVBoxLayout()
        # frame_v_box_layout.insertWidget(-1, self._container_label)
        # frame_v_box_layout.setSpacing(0)
        # frame_v_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # frame_v_box_layout.setContentsMargins(0, 0, 0, 0)
        # container_frame.setLayout(frame_v_box_layout)

        message_h_box_layout = QHBoxLayout()
        self.setLayout(message_h_box_layout)
        message_h_box_layout.setSpacing(0)
        message_h_box_layout.setContentsMargins(0, 0, 0, 0)
        message_h_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # message_h_box_layout.insertWidget(-1, container_frame)
        message_h_box_layout.addWidget(self._container_label,1)

    def updateStatus(self, currentStatus : str):
        self._text = currentStatus
        self._container_label.setText(self._text)
        # KEMSFrontEnd.logger.debug(
        #     f"About to update self widget in SimpleMessageContainer.updateStatus() in {super().objectName()}")
        self.update()

    def getText(self):
        return self._container_label.text()

    def setFont(self, newFont):
        self._font = newFont
        self._container_label.setFont(newFont)

    def setAlignment(self, newAlignment):
        self._container_label.setAlignment(newAlignment)

    def setWordWrap(self, value = True):
        self._container_label.setWordWrap(value)

    def setMinimumHeight(self, minHeight):
        self._container_label.setMinimumHeight(minHeight)



class CosThetaSimpleMessageContainer(QWidget):

    logger = None

    def __init__(self, text, styleSheet, font, foregroundColor, minimumWidth) :

        super().__init__()
        self._text = text
        self._styleSheet = styleSheet
        self._font = font
        self._foregroundColor = foregroundColor
        self._minimumWidth = minimumWidth
        self.setMinimumWidth(self._minimumWidth)
        self.setObjectName("SimpleMessageContainer")

        self._container_label = QLabel(self._text) # Container's title
        self._container_label.setStyleSheet(self._styleSheet.format(self._foregroundColor))
        self._container_label.setFont(self._font)
        self._container_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_frame = QFrame() # Main container to hold the object
        container_frame.setObjectName("SimpleMessage_ContainerFrame")

        frame_v_box = QVBoxLayout()
        frame_v_box.insertWidget(-1, self._container_label)
        frame_v_box.setSpacing(0)
        frame_v_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        frame_v_box.setContentsMargins(0, 0, 0, 0)
        container_frame.setLayout(frame_v_box)

        message_v_box = QVBoxLayout()
        message_v_box.insertWidget(-1, container_frame)
        message_v_box.setSpacing(0)
        message_v_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        message_v_box.setContentsMargins(0, 0, 0, 0)
        self.setLayout(message_v_box)

    def updateStatus(self, currentStatus : str):
        self._text = currentStatus
        self._container_label.setText(self._text)

    def setFont(self, newFont):
        self._font = newFont
        self._container_label.setFont(newFont)

    def setAlignment(self, newAlignment):
        self._container_label.setAlignment(newAlignment)

    def setWordWrap(self, value = True):
        self._container_label.setWordWrap(value)

    def setMinimumHeight(self, minHeight):
        self._container_label.setMinimumHeight(minHeight)
