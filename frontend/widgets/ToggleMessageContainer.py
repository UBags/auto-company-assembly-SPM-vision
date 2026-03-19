from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QVBoxLayout, QMessageBox
from PySide6 import QtCore, QtGui
from PySide6.QtGui import QFont, QFontMetrics, QColor
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool, Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction
from PySide6.QtWidgets import QSizePolicy, QWidget, QLabel, QFrame

class ToggleMessageContainer(QWidget):

    def __init__(self, okText : str, notokText : str, okStyleSheet : str, notokStyleSheet : str, font : QFont, okforegroundColor : QColor, notokforegroundColor : QColor, minimumWidth : int, labelHeight : int, name = '', forceUseOfFontSize : int = 0) :
        super().__init__()

        super().resize(minimumWidth, labelHeight)
        self._okText = okText
        self._notokText = notokText
        self._okStyleSheet = okStyleSheet
        self._notokStyleSheet = notokStyleSheet
        self._okforegroundColor = okforegroundColor
        self._notokforegroundColor = notokforegroundColor
        self._status = True
        # print(f"{minimumWidth = }")
        self._minimumWidth = minimumWidth
        self.setMinimumWidth(self._minimumWidth)
        self.setObjectName(f"ToggleMessageContainer_{name}")

        labelFont = font
        okTextLen = len(okText)
        notokTextLen = len(notokText)
        if okTextLen > notokTextLen:
            sampleText = okText + "    "
        else:
            sampleText = notokText + "    "
        labelFontSize = labelFont.pointSize()
        if forceUseOfFontSize == 0:
            metrics = QFontMetrics(labelFont)
            labelTextRect = metrics.boundingRect(0, 0, 0, 0,
                                                 Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                                 sampleText)
            textWidth = labelTextRect.width()
            textHeight = labelTextRect.height()
            reductionFactor = min(super().geometry().width() * 1.0 / textWidth,
                                  labelHeight * 1.0 / textHeight) * 0.95
            fontSize = int(reductionFactor * labelFontSize)
            # print(f"{super().geometry().width() = }, {reductionFactor = }, {labelFontSize = }, {fontSize = }")
            labelFont.setPointSize(fontSize)
            # print(f"For {okText}, set font size as {fontSize}")
            self.fontSize = fontSize
        else:
            labelFont.setPointSize(forceUseOfFontSize)
            self.fontSize = forceUseOfFontSize

        self._font = labelFont

        self._container_label = QLabel(self._notokText) # Container's title
        self._container_label.setStyleSheet(self._notokStyleSheet.format(self._notokforegroundColor.name()))
        self._container_label.setFont(self._font)
        self._container_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_frame = QFrame() # Main container to hold the object
        container_frame.setObjectName(f"ToggleMessage_ContainerFrame_{name}")

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

    def updateStatus(self, currentStatus : bool):
        self._status = currentStatus
        if self._status:
            self._container_label.setText(self._okText)
            self._container_label.setStyleSheet(self._okStyleSheet.format(self._okforegroundColor.name()))
        else:
            self._container_label.setText(self._notokText)
            self._container_label.setStyleSheet(self._notokStyleSheet.format(self._notokforegroundColor.name()))
        # KEMSFrontEnd.logger.debug(f"About to update self widget in ToggleMessageContainer.updateStatus() in {super().objectName()}")
        self.update()

    def setFont(self, newFont : QFont):
        self._font = newFont
        self._container_label.setFont(newFont)
        self._font.setPointSize(self.fontSize)

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