# Image Processor processes the anImage it receives from the Image Input Stream.
# Uses Process Tablets class to process the images
import types

import numpy as np
from types import *

from processors.image.Bytes2ImageAndScaler import *
from processors.image.ImageWriter import *
from processors.image.ImageDisplayer import *
from logutils.SlaveLoggers import *
from utils.RedisUtils import *
from processors.GenericQueueProcessor import *
from video.ImageProcessingFunctions import *
from processors.GenericQueueProcessor import *

class GenericImageProcessor(GenericQueueProcessor):

	logSource = getFullyQualifiedName(__file__)

	# def __init__(self, transform : Callable[[ndarray, ndarray, ndarray], ndarray, ndarray, int, bool], transformedImageConsumer : ImageDisplayer, *args, **kwargs):
	def __init__(self, name: str, cameraId : int, consumer: GenericQueueProcessor, polygonPoints : List, transform : types.FunctionType,
				 timeout : int = 1, sleepTime: float = 0, monitorRedisQueueForStopping : bool = True, max_size=32, **kwargs):
		GenericQueueProcessor.__init__(self, name=name, consumer=consumer, timeout=timeout, sleepTime=sleepTime,
									   blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping,
									   max_size=max_size, **kwargs)
		GenericImageProcessor.logSource = getFullyQualifiedName(__file__, __class__)
		self.cameraId = cameraId
		self.transform = transform
		self.rightPolygonPoints = createPolygon(polygonPoints[2])
		self.middlePolygonPoints = createPolygon(polygonPoints[1])
		self.leftPolygonPoints = createPolygon(polygonPoints[0])

	def doTransform(self, image):
		if self.transform is not None:
			return self.transform(image, self.rightPolygonPoints, self.middlePolygonPoints, self.leftPolygonPoints)
		else:
			return None

	def addItem(self, item):
		if isinstance(item, np.ndarray) or isinstance(item, bytes):
			return super().addItem(item)

	def preWorkLoop(self):
		return

	def processItem(self, item : Any) -> Any :
		pass

	def postWorkLoop(self):
		return

