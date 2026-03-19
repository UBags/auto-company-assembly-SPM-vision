from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (QSizePolicy, QLabel)

from frontend.frontendutils.CosThetaImageUtils import *


# def tearDown():
#     del app
#     return super().tearDown()

class CosThetaPixmapLabel(QLabel):

    logger = None

    def __init__(self, max_enlargement=2.0):
        super(CosThetaPixmapLabel, self).__init__()
        self.max_enlargement = max_enlargement
        self.pixmapWidth: int = 1
        self.pixmapHeight: int = 1
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(1, 1)
        self.__image = None

    def setImage(self, image) -> None:
        pixmapImage = getPixmapImage(image)
        # printPlain("Before setPixmap() - 1")
        super(CosThetaPixmapLabel, self).setPixmap(pixmapImage)
        self.__image = QPixmap.toImage(pixmapImage)
        # printPlain("After setPixmap() - 1")
        self.pixmapWidth = pixmapImage.width()
        self.pixmapHeight = pixmapImage.height()
        self.resize(self.sizeHint())
        self.update()

    # def setImage(self, startingImage: QImage) -> None:
    #     self.__image = startingImage
    #     # printPlain("Before setPixmap() - 1")
    #     super(CosThetaPixmapLabel, self).setPixmap(QPixmap.fromImage(self.__image))
    #     # printPlain("After setPixmap() - 1")
    #     self.resize(self.sizeHint())
    #     self.update()

    # def setPixmap(self, pixmap: QPixmap) -> None:
    #     self.pixmapWidth = pixmap.width()
    #     self.pixmapHeight = pixmap.height()
    #     # printPlain("Before setPixmap() - 2")
    #     super(CosThetaPixmapLabel, self).setPixmap(pixmap)
    #     # printPlain("After setPixmap() - 2")
    #     self.__image = QPixmap.toImage(pixmap)
    #     self.update()

    def sizeHint(self):
        if self.__image:
            return self.__image.size() * self.max_enlargement
        else:
            return QSize(1, 1)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        if self.pixmap() is not None:
            scaled = self.pixmap.scaled(a0.size(), aspectMode = Qt.IgnoreAspectRatio, mode = Qt.SmoothTransformation)
            # pixmapWidth = self.pixmap().width()
            # pixmapHeight = self.pixmap().height()
            # if pixmapWidth <= 0 or pixmapHeight <= 0:
            #     return
            # w, h = self.width(), self.height()
            # if w <= 0 or h <= 0:
            #     return
            # printPlain("Before setPixmap() - 3")
            self.setPixmap(scaled)
            # printPlain("After setPixmap() - 3")
        super(CosThetaPixmapLabel, self).resizeEvent(a0)

