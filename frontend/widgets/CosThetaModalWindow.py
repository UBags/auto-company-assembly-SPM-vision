# from multidispatch import dispatch
from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QMessageBox, QLabel, QVBoxLayout, QWidget, QLineEdit
from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction, Qt
from PySide6.QtWidgets import QSizePolicy
from utils.CosThetaPrintUtils import *

from frontend.CosThetaMonitorDimensions import getAppInstance, populateMonitorDimensions
from frontend.widgets.CosThetaRoundButtonWithColorGradient import *

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosThetaModalMessageWindow(QWidget):

    # This is unfinished. Need to figure out how to propagate the signal of the user click window-close event to the parent

    logger = None

    def __init__(self, parent, message : str, title : str = 'Warning - Action Needed', width : int = 140, height : int = 80):
        super().__init__()
        self._parent = parent
        self.setWindowTitle(title)
        self.setWindowModality(self._parent)
        parentWidth = parent.width()
        parentHeight = parent.height()
        super().setGeometry(parent.x() + parentWidth / 2 - width / 2, parent.y() + parentHeight / 2 - height / 2, width, height)

        self.pwd_h_box = QHBoxLayout()
        self.pwdLabel = QLabel("Password : ")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password...")
        self.password.setEchoMode(QLineEdit.Password)
        self.pwd_h_box.addWidget(self.pwdLabel)
        self.pwd_h_box.addSpacing(15)
        self.pwd_h_box.addWidget(self.password)

        vLayout = QVBoxLayout()
        mLabel = QLabel(message, Qt.AlignmentFlag.AlignCenter)
        actButton = CosThetaRoundButtonWithColorGradient(text = message, width = width, height = height)
        vLayout.addWidget(mLabel)
        vLayout.addWidget(actButton)
        self.setLayout(vLayout)


    def closeEvent(self, event):
        if event.spontaneous():
            CosThetaModalMessageWindow.logger.debug("Attempt to close modal window spontaneously. Attempt over-ridden")
            event.ignore()

    def keyPressEvent(self, event):
       if not event.key() == Qt.Key_O:
           self.close()
