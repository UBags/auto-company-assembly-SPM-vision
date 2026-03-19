# from multidispatch import dispatch
import sys

from PySide6.QtWidgets import QMainWindow, QGroupBox, QHBoxLayout, QMessageBox, QDialog
from PySide6 import QtCore
from PySide6.QtCore import QThread, Signal, Slot, QRunnable, QThreadPool
from PySide6.QtCore import QTimer
from PySide6.QtGui import QResizeEvent, QMouseEvent, QKeyEvent, QAction, Qt
from PySide6.QtWidgets import QSizePolicy

from Configuration import *
from frontend.CosThetaMonitorDimensions import getAppInstance, populateMonitorDimensions
from frontend.CosThetaStylesheets import *

app = getAppInstance()
populateMonitorDimensions() # needs to be called to ensure that a QtGui context is there for some calls to work

class CosThetaLoginDialog(QDialog):

    logger = None

    def __init__(self):
        super().__init__()

    def closeEvent(self, event):
        if event.spontaneous():
            # CosThetaLoginDialog.logger.critical("Invalid login - No uid / password provided. Shutting down the application")
            sys.exit(1)

    def keyPressEvent(self, event):
       if not event.key() == Qt.Key_Escape:
           super(CosThetaLoginDialog, self).keyPressEvent(event)

