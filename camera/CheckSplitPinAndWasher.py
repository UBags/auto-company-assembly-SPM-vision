# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

import copy
from threading import Thread
from queue import *
import cv2

from utils.CosThetaFileUtils import *
from utils.RedisUtils import *
from BaseUtils import *
from logutils.SlaveLoggers import logBoth
from logutils.Logger import MessageType
from concurrent.futures import ThreadPoolExecutor, wait

import warnings
warnings.filterwarnings('ignore', '.*h264.*', )

from Configuration import *
CosThetaConfigurator.getInstance()

class CheckSplitPinAndWasher():

    @staticmethod
    def checkSplitPinAndWasher(anImage: np.ndarray, currentPictures : Dict [str, np.ndarray | None] = None,
                               componentQRCode : str = DOST, gamma: float = 2.0) -> Tuple[np.ndarray | None, bool]:
        _src = getFullyQualifiedName(__file__, CheckSplitPinAndWasher)
        logBoth('logDebug', _src, f"CheckSplitPinAndWasher.checkSplitPinAndWasher() called with anImage = {anImage.shape if anImage is not None else 'None'}", MessageType.GENERAL)
        # logBoth('logDebug', _src, f"{countNonNoneValues(currentPictures) = }, and {componentQRCode = }", MessageType.GENERAL)
        if componentQRCode is None:
            return anImage, False
        return anImage, True
