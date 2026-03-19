import qtawesome as qta
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy

class CosThetaIconLabel(QWidget):

    iconSize = QSize(16, 16)
    horizontalSpacing = 2

    def __init__(self, qta_id, text, final_stretch=False):
        QWidget.__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        icon = QLabel()
        icon.setPixmap(qta.icon(qta_id).default_pixmap_upper(self.iconSize))

        layout.addWidget(icon)
        layout.addSpacing(self.horizontalSpacing)
        layout.addWidget(QLabel(text))

        if final_stretch:
            layout.addStretch()