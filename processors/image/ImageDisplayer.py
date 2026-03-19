# Displays the images that have been processed by Image Processor
import cv2
import numpy as np

import warnings
warnings.filterwarnings('ignore', '.*h264.*', )

from Configuration import *
CosThetaConfigurator.getInstance()

from processors.GenericQueueProcessor import *

class ImageDisplayer(GenericQueueProcessor):

    logSource = getFullyQualifiedName(__file__)

    def __init__(self, name: str, consumer: Any = None, timeout : int = 1, sleepTime : float = 0.00, resizeRatio : float = CosThetaConfigurator.getDisplayerTargetResizeRatio(), displayWindowName='Frames', max_size=2048, **kwargs):
        GenericQueueProcessor.__init__(self, name=name, consumer=None, timeout=timeout, sleepTime=sleepTime, blocking=True, monitorRedisQueueForStopping=False, max_size=max_size, **kwargs)
        ImageDisplayer.logSource = getFullyQualifiedName(__file__, __class__)
        self.resizeRatio = resizeRatio
        self.displayWindowName = displayWindowName

    def addItem(self, item: Any) -> Union[Any, None]:
        if isinstance(item, np.ndarray):
            return super().addItem(item)

    def preWorkLoop(self):
        return

    def processItem(self, item : Any) -> Any :
        if not self.stopped:
            if item is not None and isinstance(item, np.ndarray):
                if self.resizeRatio != 1.0:
                    width = int(item.shape[1] * self.resizeRatio)
                    height = int(item.shape[0] * self.resizeRatio)
                    dim = (width, height)
                    resized = cv2.resize(item, dim, interpolation=cv2.INTER_AREA)
                    cv2.imshow(self.displayWindowName, resized)
                else:
                    cv2.imshow(self.displayWindowName, item)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop()
        return None

    def postWorkLoop(self):
        cv2.destroyAllWindows()
