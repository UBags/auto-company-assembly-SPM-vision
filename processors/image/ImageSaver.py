# Writes the images that have been processed by the Image Processor.
# Uses the ffmpeg library to write compressed images at good speed
import threading

import cv2
import ffmpeg
import numpy as np

from Configuration import *
CosThetaConfigurator.getInstance()

from processors.GenericQueueProcessor import *

PICTURE="Picture"
TIME_OF_MESSAGE="timeOfMessage"

class ImageWriter(GenericQueueProcessor):

	logSource = getFullyQualifiedName(__file__)

	def __init__(self, savingDir : str, name : str = "ImageSaver", width = CosThetaConfigurator.getTargetWidth(),
				 height = CosThetaConfigurator.getTargetHeight(), debugWrite : bool = False, monitorRedisQueueForStopping : bool =False,
				 logEveryXFrames: int = CosThetaConfigurator.getImageWriterReportingInterval(), max_size = 4096, **kwargs):
		GenericQueueProcessor.__init__(self, name=name, consumer=None, sleepTime=0, blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping, max_size=max_size, **kwargs)
		ImageWriter.logSource = getFullyQualifiedName(__file__, __class__)
		self.counter = 0
		self.savingDir = savingDir
		try :
			os.makedirs(os.path.dirname(self.savingDir))
			# print(f"Made directory {self.savingDir}")
		except Exception as e:
			pass
		self.width = width
		self.height = height
		self.debugWrite = debugWrite
		self.logEveryXFrames = logEveryXFrames
		# Set non-blocking in case we don't get output for a frame
		# fcntl.fcntl(self.process.stderr, fcntl.F_SETFL, os.O_NONBLOCK)

	def addItem(self, item : Any) -> Union[Any, None]:
		if isinstance(item, np.ndarray) or isinstance(item, dict):
			return super().addItem(item)

	def preWorkLoop(self):
		return

	def processItem(self, item : Any) -> Any:
		try:
			if item is not None:
				# printBoldYellow(f"Received item type: {type(item)} in ImageSaver")
				added = False
				if isinstance(item, np.ndarray):
					fullPath = f"{self.savingDir}{getYMDHMSmFormatFromTimeDotTime(item[TIME_OF_MESSAGE])}-{getCurrentTime()}.png"
					if (item.shape[1] != self.width) or (item.shape[0] != self.height):
						item = cv2.resize(item, (self.width, self.height), cv2.INTER_NEAREST_EXACT)
					added = cv2.imwrite(fullPath, item)
					# print(added)
				elif isinstance(item, dict):
					# printBoldYellow(f"In dict branch of processItem in ImageSaver")
					image = item[PICTURE]
					if isinstance(image, np.ndarray):
						# fullPath = f"{self.savingDir}{getCurrentTime()}.png"
						fullPath = f"{self.savingDir}{getYMDHMSmFormatFromTimeDotTime(item[TIME_OF_MESSAGE])}-{getCurrentTime()}.png"
						# printBoldGreen(f"Saved {item[TIME_OF_MESSAGE]} {type(item[TIME_OF_MESSAGE])} to {fullPath}")
						# printBoldYellow(f"In np.ndarray branch of dict branch of processItem in ImageSaver, saving to {fullPath}")
						if (image.shape[1] != self.width) or (image.shape[0] != self.height):
							image = cv2.resize(image, (self.width, self.height), cv2.INTER_NEAREST_EXACT)
						# printBoldYellow(f"About to write image {'None' if image is None else 'anImage'} of shape {image.shape} to {fullPath}")
						added = cv2.imwrite(fullPath, image)
						# print(added)
				if self.logEveryXFrames != 0 and added:
					self.counter += 1
					if self.debugWrite and (self.counter % self.logEveryXFrames == 0):
						SlaveFileLogger.getInstance().logTakeNote(ImageWriter.logSource,
																  f"Writing image no {self.counter} in ImageWriter.{self.name}.processItem()",
																  Logger.SUCCESS)
						SlaveConsoleLogger.getInstance().logTakeNote(ImageWriter.logSource,
																	 f"Writing image no {self.counter} in ImageWriter.{self.name}.processItem()",
																	 Logger.SUCCESS)
				return True
		except Exception as e:
			SlaveFileLogger.getInstance().logTakeNote(ImageWriter.logSource,
													  f"In ImageWriter.{self.name}, could not write image using FFMPEG to {self.path} due to {e}",
													  Logger.RISK)
			SlaveConsoleLogger.getInstance().logTakeNote(ImageWriter.logSource,
														 f"In ImageWriter.{self.name}, could not write image using FFMPEG to {self.path} due to {e}",
														 Logger.RISK)
		return False

	def postWorkLoop(self):
		SlaveFileLogger.getInstance().logTakeNote(ImageWriter.logSource,
												  f"Closed down the ImageWriter.{self.name}",
												  Logger.SUCCESS)
		SlaveConsoleLogger.getInstance().logTakeNote(ImageWriter.logSource,
													 f"Closed down the ImageWriter.{self.name}",
													 Logger.SUCCESS)

