# Writes the images that have been processed by the Image Processor.
# Uses the ffmpeg library to write compressed images at good speed
import threading

import ffmpeg

from Configuration import *
CosThetaConfigurator.getInstance()

from processors.GenericQueueProcessor import *

class ImageWriter(GenericQueueProcessor):

	logSource = getFullyQualifiedName(__file__)

	def __init__(self, name : str = "ImageWriter", path : str = f"{getCurrentTime()}.mp4", fps = 20, width = CosThetaConfigurator.getTargetWidth(),
				 height = CosThetaConfigurator.getTargetHeight(), debugWrite : bool = False, monitorRedisQueueForStopping : bool =False,
				 logEveryXFrames: int = CosThetaConfigurator.getImageWriterReportingInterval(), max_size = 2048, **kwargs):
		GenericQueueProcessor.__init__(self, name=name, consumer=None, sleepTime=0, blocking=True, monitorRedisQueueForStopping=monitorRedisQueueForStopping, max_size=max_size, **kwargs)
		ImageWriter.logSource = getFullyQualifiedName(__file__, __class__)
		self.counter = 0
		self.path = path
		try :
			os.makedirs(os.path.dirname(self.path))
		except Exception as e:
			pass
		self.fps = fps 	# Though fps does not mean anything for a writer,
						# this is being specified so that an appropriate sleep time can be given
						# to enable other threads to get CPU time
		self.width = width
		self.height = height
		self.debugWrite = debugWrite
		self.logEveryXFrames = logEveryXFrames
		# self.process = (
		# 	ffmpeg
		# 		.input('pipe:', format='rawvideo', pix_fmt='rgb24', s='{}x{}'.format(self.width, self.height))
		# 		.output(self.path, pix_fmt='yuv420p', vcodec='libx264', r=self.fps, crf=15, bitrate="8M", preset="slow", loglevel="quiet")
		# 		.overwrite_output()
		# 		.run_async(pipe_stdin=True)
		# )
		self.process = (
			ffmpeg
				.input('pipe:', format='rawvideo', pix_fmt='rgb24', s='{}x{}'.format(self.width, self.height))
				.output(self.path, pix_fmt='yuv422p', vcodec='libx264', r=self.fps, crf=10, bitrate="8M", preset="slow", loglevel="quiet")
				.overwrite_output()
				.run_async(pipe_stdin=True)
		)
		# Set non-blocking in case we don't get output for a frame
		# fcntl.fcntl(self.process.stderr, fcntl.F_SETFL, os.O_NONBLOCK)

	def addItem(self, item : Any) -> Union[Any, None]:
		if isinstance(item, np.ndarray):
			return super().addItem(item)

	def preWorkLoop(self):
		# self.lock = threading.Lock()
		return

	def processItem(self, item : Any) -> Any:
		# self.lock.acquire()
		# print("Acquired stateLock")
		try:
			if item is not None and isinstance(item, np.ndarray):
				self.process.stdin.write(
					cv2.cvtColor(item, cv2.COLOR_BGR2RGB)
						.astype(np.uint8)
						.tobytes()
				)
				# self.process.stderr.read()
				if self.logEveryXFrames != 0:
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
		# finally:
		# 	self.lock.release()
		return False

	def postWorkLoop(self):
		# print("In postWorkLoop")
		self.process.stdin.close()
		# print("In postWorkLoop - after close")
		self.process.wait()
		# print("In postWorkLoop - after wait")
		SlaveFileLogger.getInstance().logTakeNote(ImageWriter.logSource,
												  f"Closed down the ImageWriter.{self.name}",
												  Logger.SUCCESS)
		SlaveConsoleLogger.getInstance().logTakeNote(ImageWriter.logSource,
													 f"Closed down the ImageWriter.{self.name}",
													 Logger.SUCCESS)

	def __del__(self):
		if hasattr(self, "process"):
			if self.process.poll():
				self.process.stdin.close()
				self.process.wait()