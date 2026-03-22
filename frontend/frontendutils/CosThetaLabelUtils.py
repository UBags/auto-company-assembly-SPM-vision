# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

from PySide6.QtWidgets import QLabel

from Configuration import *
from frontend.CosThetaStylesheets import okLabelStylesheet, notokLabelStylesheet, noResultLabelStylesheet
from frontend.frontendutils.CosThetaImageUtils import *

def createResultLabel(result = "No Result", width = (1366  - 100) / 4, labelHeight = 50, forceLabelFontSizeTo : int = 0):
    # logger.debug(f"Entered createResultLabel with result={result}, width={width}, labelHeight={labelHeight}")
    fontFace = CosThetaConfigurator.getInstance().getFontFace()
    labelFontSize = CosThetaConfigurator.getInstance().getInitialFontsize()
    labelFont = QFont(fontFace, labelFontSize)
    labelFont.setWeight(QFont.Weight.Bold)
    if forceLabelFontSizeTo > 0:
        labelFont.setPointSize(forceLabelFontSizeTo)
    else:
        metrics = QFontMetrics(labelFont)
        labelTextRect = metrics.boundingRect(0, 0, 0, 0,
                                             Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                             result)
        textWidth = labelTextRect.width()
        textHeight = labelTextRect.height()
        reductionFactor = min(width * 1.0 / textWidth,
                              labelHeight * 1.0 / textHeight) * 0.8
        fontSize = int(reductionFactor * labelFontSize)
        labelFont.setPointSize(fontSize)
    # logger.debug(f"Resized font {fontFace} to {fontSize}")
    result_label = QLabel(result)  # Label's title
    result_label.setContentsMargins(0,0,0,0)
    result_label.setFont(labelFont)
    result_label.resize(int(width), labelHeight)
    # self.outcome_container_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    result_label.setFixedHeight(labelHeight)
    result_label.setFixedWidth(int(width))
    # printPlain(f"About to do comparison of result with value {result.lower()}")
    if result.lower() == 'ok':
        # logger.debug(f"Setting stylesheet as okLabelStylesheet")
        result_label.setStyleSheet(okLabelStylesheet.format(
            QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
    elif result.lower() == 'not ok':
        # logger.debug(f"Setting stylesheet as notokLabelStylesheet")
        result_label.setStyleSheet(notokLabelStylesheet.format(
            QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
    else:
        # logger.debug(f"Setting stylesheet as noResultStylesheet")
        result_label.setStyleSheet(noResultLabelStylesheet.format(
            QColor(Qt.GlobalColor.white).name()))  # Set the background and foreground color of the container's label
    # result_label.setFixedHeight(labelHeight)
    # result_label.setFixedWidth(width)
    # result_label.setScaledContents(True)
    # logger.debug(f"Exiting createResultLabel()")
    return result_label

