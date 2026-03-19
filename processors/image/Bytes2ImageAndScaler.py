import numpy as np

from processors.image.ImageDisplayer import *
from processors.image.ImageWriter import *
from processors.image.GenericImageProcessor import *
from logutils.SlaveLoggers import *

import warnings
warnings.filterwarnings('ignore', '.*h264.*', )

from Configuration import *
CosThetaConfigurator.getInstance()

from processors.GenericQueueProcessor import *

class Bytes2ImageAndScaling(GenericQueueProcessor):

    logSource = getFullyQualifiedName(__file__)

    def __init__(self, name: str, consumer: GenericQueueProcessor = None, timeout : int = 1, sleepTime : float = 0,
                 targetWidth: int = CosThetaConfigurator.getInstance().getTargetWidth(), targetHeight: int = CosThetaConfigurator.getInstance().getTargetHeight(), monitorRedisQueueForStopping : bool = False, max_size=32, **kwargs):
        GenericQueueProcessor.__init__(self, name=name, consumer=consumer, timeout=timeout, sleepTime=sleepTime, blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping, max_size=max_size, **kwargs)
        Bytes2ImageAndScaling.logSource = getFullyQualifiedName(__file__, __class__)
        self.targetWidth = targetWidth
        self.targetHeight = targetHeight

    def addItem(self, item: Any) -> Union[Any, None]:
        if isinstance(item, np.ndarray) or isinstance(item, bytes):
            return super().addItem(item)

    def preWorkLoop(self):
        return

    def processItem(self, item : Any) -> Any :
        # SlaveConsoleLogger.getInstance().logConsiderAction(Bytes2ImageAndScaling.logSource,
        #                                              f"In Bytes2ImageAndScaling.{self.name}, received {type(item)}",
        #                                              Logger.ISSUE)
        if item is not None:
            try:
                reduced_image = None
                if isinstance(item, np.ndarray):
                    if (item.shape[1] == self.targetWidth) and (item.shape[0] == self.targetHeight):
                        reduced_image = item
                    else:
                        reduced_image = cv2.resize(item, (self.targetWidth, self.targetHeight), interpolation=cv2.INTER_LANCZOS4)
                elif isinstance(item, bytes):
                    # SlaveConsoleLogger.getInstance().logTakeNote(Bytes2ImageAndScaling.logSource,
                    #                                              f"In elif branch in Bytes2ImageAndScaling.{self.name}",
                    #                                              Logger.RISK)
                    img_array = np.asarray(bytearray(item), dtype=np.uint8)
                    img = cv2.imdecode(img_array, -1)
                    if (img.shape[1] == self.targetWidth) and (img.shape[0] == self.targetHeight):
                        reduced_image = img
                    else:
                        reduced_image = cv2.resize(img, (self.targetWidth, self.targetHeight), interpolation=cv2.INTER_AREA)
                return reduced_image
            except Exception as e:
                if self.debugOtherExceptions:
                    SlaveFileLogger.getInstance().logTakeNote(Bytes2ImageAndScaling.logSource,
                                                              f"Could not reduce startingImage in Bytes2ImageAndScaling.{self.name} due to exception {e}",
                                                              Logger.RISK)
                    SlaveConsoleLogger.getInstance().logTakeNote(Bytes2ImageAndScaling.logSource,
                                                                 f"Could not reduce startingImage in Bytes2ImageAndScaling.{self.name} due to exception {e}",
                                                                 Logger.RISK)
        else:
            if self.debugOtherExceptions:
                SlaveFileLogger.getInstance().logTakeNote(Bytes2ImageAndScaling.logSource,
                                                          f"Did not reduce {'None startingImage' if item is None else type(item)} in Bytes2ImageAndScaling.{self.name}",
                                                          Logger.RISK)
                SlaveConsoleLogger.getInstance().logTakeNote(Bytes2ImageAndScaling.logSource,
                                                             f"Did not reduce {'None startingImage' if item is None else type(item)} in Bytes2ImageAndScaling.{self.name}",
                                                             Logger.RISK)
        return None

    def postWorkLoop(self):
        return

