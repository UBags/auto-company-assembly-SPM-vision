import threading
import requests
from requests import Response
from requests.auth import HTTPDigestAuth

import ffmpeg
import operator
from pprint import pprint
from datetime import datetime
import cv2
import numpy as np
import socket
from urllib.parse import urlparse, parse_qs
import time
from datetime import datetime
import time
import redis

import argparse
import imutils
import cv2
from threading import Thread, ThreadError
import sys
from queue import Queue
import time
from operator import not_
from collections.abc import *
from typing import *
import copy

from logutils.SlaveLoggers import *
from logutils.Logger import *
from logutils.AbstractSlaveLogger import *
from utils.RedisUtils import *
from utils.IPUtils import *

import warnings
warnings.filterwarnings('ignore', '.*h264.*', )

from Configuration import *
CosThetaConfigurator.getInstance()

'''
0) Install Hikvision Tools Manager
1) *****Install SADP***** and set password as admin and admin. Enable 'Hik-vision Connect' and 'port'
2) Double-click on SADP row to open a browser and see the camera output
3) Check maikl for documeht 'Hikvision PZTZ settings'


a) Go to Configurations -> Network -> Integration Protocol. Enable ONVIF. Then, create a newwidgets user with admin and abcd1234
b) Go to that part which is creating a problem and overwrite the throws clause with 'returns xmlvalue'
c) Clone the github in a directory and install on the machine using 'python setup.py install'. 
   This will ensure that the wsdls are installed in the correct directory and available to all the calls 
d) When you create a project, ensure that the venv has both options ticked for 'inherit global site-packages' and 'make available to all projects'   
'''

class RTSPCam():

    logSource = getFullyQualifiedName(__file__)
    LOG_CONNECTION_PROBLEM_EVERY_N_SECS = CosThetaConfigurator.getInstance().getLogDisconnectionsAfterNSecs()

    def __init__(self, IP: str, port: int, uid: str, password: str, name: str = "aCamera"):
        self.IP = IP
        self.port = port
        self.uid = uid
        self.password = password
        self.name = name
        self.connectionAttempts: int = 0

        self.videoUri1 = f"rtsp://{self.uid}:{self.password}@{self.IP}/cam/realmonitor?channel=1&subtype=0"
        self.camProcess = None
        self.camAvailable = False

        self.stopped = False
        self.stopFrameUpdateThread = False
        self.maxAllowedNoneFrameCountsInCamera = CosThetaConfigurator.getInstance().getMaxAllowedNoneFrameCountsInCamera()

        self.latestCamFrame: Union[None, np.ndarray] = None

        self.width = 0
        self.height = 0
        self.fps = 20  # Default FPS in case probe fails
        self.timeRequiredBetweenFrames = 1.0 / self.fps

        RTSPCam.logSource = getFullyQualifiedName(__file__, __class__)
        self.connected = False
        self.connectionInProgress = False
        self.connectionMonitoringThreadStarted: bool = False
        self.keepaliveThreadStarted: bool = False

        # Attempt initial connection - don't let exceptions crash the server
        try:
            self.reconnect()
        except Exception as e:
            logBoth('logTakeAction', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, unable to create RTSPCamera due to {e}",
                    Logger.PROBLEM)
            # Ensure monitoring thread starts even if initial connection fails
            # This allows recovery when camera becomes available later
            self.connected = False
            self.camAvailable = False
            self.connectionInProgress = False
            if not self.connectionMonitoringThreadStarted:
                try:
                    self.launchMonitorCameraConnectionThread()
                except Exception as e2:
                        logBoth('logTakeAction', RTSPCam.logSource,
                                f"In RTSPCam.{self.name}, could not start monitoring thread: {e2}",
                                Logger.PROBLEM)

        # Start ISAPI keepalive thread to prevent camera from going dormant
        if not self.keepaliveThreadStarted:
            self._launchKeepaliveThread()

    def stop(self):
        self.stopped = True
        self.stopFrameUpdateThread = True
        self.releaseResources()

    def _launchKeepaliveThread(self):
        """
        Launch a background thread that periodically pings the camera via ISAPI
        to prevent it from going dormant due to network inactivity.
        """
        KEEPALIVE_INTERVAL_SECS = 60  # Ping every 60 seconds

        def keepalivePing():
            url = f"http://{self.IP}/ISAPI/System/deviceInfo"
            auth = HTTPDigestAuth(self.uid, self.password)

            while not self.stopped:
                try:
                    try:
                        response = requests.get(url, auth=auth, timeout=10)
                    except Exception as e:
                        response = Response.status_code = 400
                    if response.status_code == 200:
                        logBoth('logDebug', RTSPCam.logSource,
                                f"In RTSPCam.{self.name}, ISAPI keepalive OK",
                                Logger.SUCCESS)
                    else:
                        logBoth('logTakeNote', RTSPCam.logSource,
                                f"In RTSPCam.{self.name}, ISAPI keepalive returned status {response.status_code}",
                                Logger.PROBLEM)
                except Exception as e:
                    logBoth('logTakeNote', RTSPCam.logSource,
                            f"In RTSPCam.{self.name}, ISAPI keepalive exception: {e}",
                            Logger.PROBLEM)

                # Sleep in small increments so we can exit promptly when stopped
                for _ in range(KEEPALIVE_INTERVAL_SECS):
                    if self.stopped:
                        break
                    time.sleep(1)

            logBoth('logTakeNote', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, ISAPI keepalive thread exited",
                    Logger.INFO)

        keepaliveThread = threading.Thread(
            name=f"ISAPI Keepalive for camera at {self.IP}",
            target=keepalivePing,
            daemon=True
        )
        self.keepaliveThreadStarted = True
        keepaliveThread.start()
        logBoth('logTakeNote', RTSPCam.logSource,
                f"In RTSPCam.{self.name}, started ISAPI keepalive thread (interval: {KEEPALIVE_INTERVAL_SECS}s)",
                Logger.INFO)

    def reconnect(self):
        # printLight(f"Entered reconnect")
        if self.connectionInProgress:
            print(f"As {self.connectionInProgress = }, already attempting to reconnect. Hence, exiting")
            return
        # else:
        #     # printBoldBlue(f"{self.attemptingToReconnect = }")
        #     pass
        self.connectionInProgress = True
        self.connectionAttempts += 1
        if (self.connectionAttempts == 1) or ((self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
            # printLight(f"Trying to create camera with {self.IP}, {self.port}, {self.uid}, {self.password}")
            logBoth('logTakeNote', RTSPCam.logSource,
                    f"Trying to create camera with {self.IP}, {self.port}, {self.uid}, {self.password}",
                    Logger.INFO)
            # printBoldGreen(f"Reconnecting to camera at IP {self.IP}")
        camIPAvailable = checkIP(self.IP)
        # printLight(f"Pinged IP {self.IP}; it is {'reachable' if camIPAvailable else 'not reachable'}")
        if not camIPAvailable:
            try:
                if self.camProcess is not None:
                    self.camProcess.kill()
                    self.camProcess = None
                    self.stopFrameUpdateThread = True
            except:
                self.camProcess = None
                self.stopFrameUpdateThread = True
            self.connected = False
            self.camAvailable = False
            if (self.connectionAttempts == 1) or (
                    (self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
                logBoth('logTakeAction', RTSPCam.logSource,
                        f"In RTSPCam.{self.name}, could not connect to camera at IP {self.IP} - IP not reachable",
                        Logger.PROBLEM)
            self.connectionInProgress = False
            # if (self.connectionAttempts == 1) or (
            #         (self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
            #     printBoldRed(f"No camera available at IP {self.IP} - IP not reachable - exiting reconnect() after setting {self.connectionInProgress = }")
            # raise Exception(f"No camera available at IP {self.IP} - IP not reachable")
        else:
            try:
                # printBoldBlue(f"As IP {self.IP} is reachable, attempting to connect.")
                try:
                    if self.camProcess is not None:
                        logBoth('logTakeAction', RTSPCam.logSource,
                                f"In RTSPCam.{self.name}, about to kill camProcess as it is not None",
                                Logger.ISSUE)
                        self.camProcess.kill()
                        self.camProcess = None
                        self.stopFrameUpdateThread = True
                except:
                    self.camProcess = None
                    self.stopFrameUpdateThread = True
                self.connected = False
                self.camAvailable = False
                # SlaveFileLogger.getInstance().logDebug(RTSPCam.logSource,
                #                                           f"In RTSPCam.{self.name}, about to create stream at IP {self.IP}",
                #                                           Logger.SUCCESS)
                # SlaveConsoleLogger.getInstance().logDebug(RTSPCam.logSource,
                #                                              f"In RTSPCam.{self.name}, about to create stream at IP {self.IP}",
                #                                              Logger.SUCCESS)
                if not self.stopped:
                    self.renewCam()
                    # printBoldBlue(f"In RTSPCam.{self.name}, about to launch frame update thread")
                    # self.connected = True
                    # printBoldBlue(f"In RTSPCam.{self.name}, created camera at IP {self.IP}")
                if self.connected:
                    logBoth('logDebug', RTSPCam.logSource,
                            f"In RTSPCam.{self.name}, created camera and connected to camera at IP {self.IP}",
                            Logger.SUCCESS)
            except Exception as e:
                logBoth('logTakeAction', RTSPCam.logSource,
                        f"In RTSPCam.{self.name}, could not create camera due to {e}",
                        Logger.PROBLEM)
                self.camera = None
                try:
                    if self.camProcess is not None:
                        self.camProcess.kill()
                        self.camProcess = None
                        self.stopFrameUpdateThread = True
                except:
                    self.camProcess = None
                    self.stopFrameUpdateThread = True
                self.connected = False
                self.camAvailable = False
                if (self.connectionAttempts == 1) or (
                        (self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
                    logBoth('logTakeAction', RTSPCam.logSource,
                            f"In RTSPCam.{self.name}, could not connect to camera at IP {self.IP}, though IP is reachable, due to {str(e)}",
                            Logger.PROBLEM)
                # printBoldRed(f"No camera available at IP {self.IP}, though IP is reachable")
                self.connectionInProgress = False
                if (self.connectionAttempts == 1) or (
                        (self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
                    logBoth('logTakeAction', RTSPCam.logSource,
                            f"In RTSPCam.{self.name}, could not create camera though {self.IP} is reachable - exiting reconnect() after setting connectionInProgress={self.connectionInProgress}",
                            Logger.PROBLEM)
                return
                # raise Exception(f"No camera available at IP {self.IP}, though IP is reachable")
        try:
            if self.connected:
                self.stopFrameUpdateThread = False
                self.launchFrameUpdateThread()
            if not self.connectionMonitoringThreadStarted:
                # printBoldBlue(f"In RTSPCam.{self.name}, about to launch camera connection monitoring thread")
                self.launchMonitorCameraConnectionThread()
        except Exception as e:
            logBoth('logTakeAction', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, exception while launching threads: {e}",
                    Logger.PROBLEM)
            self.connected = False
            self.camAvailable = False
        finally:
            self.connectionInProgress = False
        # printBoldGreen(
        #     f"Exiting reconnect() after setting {self.attemptingToReconnect = }")

    def renewCam(self) -> None:
        # printBoldYellow(f"Inside renewCam()")
        self.camAvailable = False
        # print(f"Setting {self.camAvailable = } in renewCam()")
        if self.camProcess is not None:
            try:
                self.camProcess.kill()
                self.camProcess = None
                self.stopFrameUpdateThread = True
            except:
                self.camProcess = None
                self.stopFrameUpdateThread = True
                # pass
        try:
            self.camProcess = self.startFFMPEG_RTSP_Process()
            if self.camProcess is not None:
                self.camAvailable = True
                self.stopFrameUpdateThread = False
                self.connected = True
                self.connectionAttempts = 0
        except:
            self.camProcess = None
            self.camAvailable = False
            self.stopFrameUpdateThread = True
            self.connected = False
            # print(f"Setting {self.camAvailable = } in renewCam()")
            pass
        # printBoldYellow(f"Exiting renewCam() with {self.camAvailable = }")
        return None

    def startFFMPEG_RTSP_Process(self):
        FFPROBE_TIMEOUT = 15  # seconds
        try:
            args = {
                "rtsp_transport": "tcp",
                "fflags": "nobuffer",
                "flags": "low_delay"
            }
            # Use subprocess with timeout for ffprobe instead of ffmpeg.probe()
            # This prevents hanging indefinitely on unresponsive cameras
            import subprocess
            import json

            ffprobe_cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-rtsp_transport', 'tcp',
                self.videoUri1
            ]

            try:
                result = subprocess.run(
                    ffprobe_cmd,
                    capture_output=True,
                    text=True,
                    timeout=FFPROBE_TIMEOUT
                )
                if result.returncode != 0:
                    raise Exception(f"ffprobe failed with return code {result.returncode}")

                probe = json.loads(result.stdout)
                cap_info = next(x for x in probe['streams'] if x['codec_type'] == 'video')

            except subprocess.TimeoutExpired:
                logBoth('logTakeAction', RTSPCam.logSource,
                        f"In RTSPCam.{self.name}, ffprobe timed out after {FFPROBE_TIMEOUT}s",
                        Logger.PROBLEM)
                return None
            except json.JSONDecodeError as e:
                logBoth('logTakeAction', RTSPCam.logSource,
                        f"In RTSPCam.{self.name}, ffprobe returned invalid JSON: {e}",
                        Logger.PROBLEM)
                return None

            self.width = cap_info['width']
            self.height = cap_info['height']
            up, down = str(cap_info['r_frame_rate']).split('/')
            self.fps = eval(up) / eval(down)
            self.timeRequiredBetweenFrames = 1.0 / self.fps
            logBoth('logInfo', RTSPCam.logSource, f"fps: {self.fps}", Logger.GENERAL)

            cameraProcess = (
                ffmpeg
                .input(self.videoUri1, **args)
                .output(
                    'pipe:',
                    format='rawvideo',
                    pix_fmt='bgr24',
                    fflags='nobuffer',
                    analyzeduration='1',
                    loglevel='error'
                )
                .overwrite_output()
                .run_async(pipe_stdout=True)
            )
            logBoth('logTakeNote', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, got FFMPEG process",
                    Logger.SUCCESS)
            return cameraProcess

        except Exception as e:
            logBoth('logTakeAction', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, unable to create FFMPEG process due to {e}",
                    Logger.PROBLEM)
            return None

    def launchFrameUpdateThread(self):
        objRef = self

        def updateFrame():
            import sys
            import queue

            # Detect platform
            is_windows = sys.platform.startswith('win')

            READ_TIMEOUT = 5.0  # seconds - timeout for reading a frame
            PROCESS_CHECK_INTERVAL = 1.0  # Check if FFMPEG process is alive every N seconds
            WATCHDOG_TIMEOUT = 15.0  # If no successful frame for this many seconds, force disconnect
            STARTUP_GRACE_PERIOD = 20.0  # Don't trigger watchdog for first N seconds after connection

            consecutiveCount = 0
            frameCount = 0
            last_process_check = time.time()
            last_successful_frame_time = time.time()  # Watchdog timer
            first_frame_received = False  # Track if we've ever received a frame
            thread_start_time = time.time()  # Track when this thread started

            # For Windows: use a threaded reader with queue since select() doesn't work on pipes
            read_queue = queue.Queue() if is_windows else None
            reader_thread = None
            reader_stop_event = threading.Event() if is_windows else None

            def threaded_reader():
                """Background thread that reads frames and puts them in a queue (Windows only)"""
                while not reader_stop_event.is_set():
                    try:
                        if objRef.camProcess is None or objRef.camProcess.stdout is None:
                            read_queue.put(('error', Exception("camProcess or stdout is None")))
                            break

                        # Check if process has exited
                        poll_result = objRef.camProcess.poll()
                        if poll_result is not None:
                            read_queue.put(('error', Exception(f"FFMPEG process exited with code {poll_result}")))
                            break

                        bytes_to_read = objRef.width * objRef.height * 3
                        in_bytes = objRef.camProcess.stdout.read(bytes_to_read)
                        if in_bytes:
                            read_queue.put(('data', in_bytes))
                        else:
                            read_queue.put(('empty', None))
                    except Exception as e:
                        read_queue.put(('error', e))
                        break

            try:
                if is_windows:
                    # Start background reader thread for Windows
                    reader_thread = threading.Thread(target=threaded_reader, daemon=True)
                    reader_thread.start()
                else:
                    import select

                while (not objRef.stopped) and objRef.camAvailable and objRef.connected and (
                        not objRef.stopFrameUpdateThread):
                    try:
                        # Check if camProcess and stdout are valid
                        if objRef.camProcess is None or objRef.camProcess.stdout is None:
                            logBoth('logTakeNote', RTSPCam.logSource,
                                    f"In RTSPCam.{objRef.name}, camProcess or stdout is None, exiting frame thread",
                                    Logger.RISK)
                            objRef.stopFrameUpdateThread = True
                            break

                        # Periodically check if FFMPEG process is still alive
                        current_time = time.time()
                        if current_time - last_process_check >= PROCESS_CHECK_INTERVAL:
                            last_process_check = current_time
                            poll_result = objRef.camProcess.poll()
                            if poll_result is not None:
                                logBoth('logTakeAction', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, FFMPEG process exited with code {poll_result}",
                                        Logger.PROBLEM)
                                objRef.stopFrameUpdateThread = True
                                break

                            # Watchdog: check if we've received any frames recently
                            # Only activate watchdog after startup grace period OR after first frame
                            time_since_start = current_time - thread_start_time
                            time_since_last_frame = current_time - last_successful_frame_time

                            if first_frame_received:
                                # After first frame, use normal watchdog
                                if time_since_last_frame > WATCHDOG_TIMEOUT:
                                    logBoth('logTakeAction', RTSPCam.logSource,
                                            f"In RTSPCam.{objRef.name}, watchdog timeout: no frames for {time_since_last_frame:.1f}s, forcing disconnect",
                                            Logger.PROBLEM)
                                    objRef.stopFrameUpdateThread = True
                                    break
                            elif time_since_start > STARTUP_GRACE_PERIOD:
                                # Never received a frame and grace period expired
                                logBoth('logTakeAction', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, no frames received within {STARTUP_GRACE_PERIOD}s startup period, forcing disconnect",
                                        Logger.PROBLEM)
                                objRef.stopFrameUpdateThread = True
                                break

                        if is_windows:
                            # Windows: get frame from queue with timeout
                            try:
                                msg_type, msg_data = read_queue.get(timeout=READ_TIMEOUT)

                                if msg_type == 'error':
                                    logBoth('logTakeAction', RTSPCam.logSource,
                                            f"In RTSPCam.{objRef.name}, reader thread error: {msg_data}",
                                            Logger.PROBLEM)
                                    objRef.stopFrameUpdateThread = True
                                    break
                                elif msg_type == 'empty':
                                    consecutiveCount += 1
                                    if consecutiveCount > objRef.maxAllowedNoneFrameCountsInCamera:
                                        objRef.stopFrameUpdateThread = True
                                    continue
                                else:  # msg_type == 'data'
                                    in_bytes = msg_data

                            except queue.Empty:
                                # Timeout occurred - no data available
                                consecutiveCount += 1
                                logBoth('logTakeNote', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, read timeout ({consecutiveCount} consecutive)",
                                        Logger.RISK)
                                if consecutiveCount > objRef.maxAllowedNoneFrameCountsInCamera:
                                    logBoth('logTakeAction', RTSPCam.logSource,
                                            f"In RTSPCam.{objRef.name}, too many consecutive timeouts, stopping frame thread",
                                            Logger.PROBLEM)
                                    objRef.stopFrameUpdateThread = True
                                continue
                        else:
                            # Linux: use select for timeout
                            fd = objRef.camProcess.stdout.fileno()
                            ready, _, _ = select.select([fd], [], [], READ_TIMEOUT)

                            if not ready:
                                # Timeout occurred - no data available
                                consecutiveCount += 1
                                logBoth('logTakeNote', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, read timeout ({consecutiveCount} consecutive)",
                                        Logger.RISK)
                                if consecutiveCount > objRef.maxAllowedNoneFrameCountsInCamera:
                                    logBoth('logTakeAction', RTSPCam.logSource,
                                            f"In RTSPCam.{objRef.name}, too many consecutive timeouts, stopping frame thread",
                                            Logger.PROBLEM)
                                    objRef.stopFrameUpdateThread = True
                                continue

                            # Data is available, read it
                            bytes_to_read = objRef.width * objRef.height * 3
                            in_bytes = objRef.camProcess.stdout.read(bytes_to_read)

                        # Process the frame (common code for both platforms)
                        bytes_to_read = objRef.width * objRef.height * 3

                        if not in_bytes:
                            consecutiveCount += 1
                            if consecutiveCount > objRef.maxAllowedNoneFrameCountsInCamera:
                                objRef.stopFrameUpdateThread = True
                        elif len(in_bytes) != bytes_to_read:
                            # Partial read - likely stream issue
                            consecutiveCount += 1
                            logBoth('logTakeNote', RTSPCam.logSource,
                                    f"In RTSPCam.{objRef.name}, partial read: got {len(in_bytes)} bytes, expected {bytes_to_read}",
                                    Logger.RISK)
                            if consecutiveCount > objRef.maxAllowedNoneFrameCountsInCamera:
                                objRef.stopFrameUpdateThread = True
                        else:
                            # Good frame received!
                            consecutiveCount = 0
                            frameCount += 1
                            last_successful_frame_time = time.time()  # Reset watchdog
                            first_frame_received = True  # Mark that we've received at least one frame

                            frame = (
                                np
                                .frombuffer(in_bytes, np.uint8)
                                .reshape([objRef.height, objRef.width, 3])
                            )
                            if frame is not None:
                                objRef.latestCamFrame = frame
                            else:
                                objRef.latestCamFrame = None
                            if frameCount % 4000 == 0:
                                logBoth('logConsiderAction', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, got frame {frameCount}",
                                        Logger.SUCCESS)
                            if frameCount % 1000 == 0:
                                logBoth('logDebug', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, got frame {frameCount}",
                                        Logger.SUCCESS)

                    except (ValueError, OSError) as e:
                        # Handle case where file descriptor becomes invalid (process died)
                        logBoth('logTakeAction', RTSPCam.logSource,
                                f"In RTSPCam.{objRef.name}, I/O error in frame thread: {e}",
                                Logger.PROBLEM)
                        objRef.stopFrameUpdateThread = True
                        break
                    except Exception as e:
                        consecutiveCount += 1
                        logBoth('logTakeNote', RTSPCam.logSource,
                                f"In RTSPCam.{objRef.name}, exception in frame thread: {e}",
                                Logger.RISK)
                        if consecutiveCount > objRef.maxAllowedNoneFrameCountsInCamera:
                            objRef.stopFrameUpdateThread = True

            except Exception as e:
                logBoth('logTakeAction', RTSPCam.logSource,
                        f"In RTSPCam.{objRef.name}, unexpected exception in frame thread: {e}",
                        Logger.PROBLEM)
            finally:
                # Stop the reader thread on Windows
                if reader_stop_event:
                    reader_stop_event.set()

                # Cleanup ALWAYS runs
                objRef.camAvailable = False
                objRef.connected = False
                if objRef.camProcess is not None:
                    try:
                        objRef.camProcess.kill()
                        objRef.camProcess = None
                    except:
                        objRef.camProcess = None
                logBoth('logTakeNote', RTSPCam.logSource,
                        f"In RTSPCam.{objRef.name}, frame update thread exited after {frameCount} frames",
                        Logger.INFO)

        updateThread = threading.Thread(name=f"Frame update thread for camera at {self.IP}", target=updateFrame,
                                        args=(), daemon=True)
        logBoth('logTakeNote', RTSPCam.logSource,
                f"In RTSPCam.{self.name}, about to start frame update thread",
                Logger.SUCCESS)
        updateThread.start()

    def launchMonitorCameraConnectionThread(self):
        objRef = self

        def monitorAndReEstablishConnection():
            while not objRef.stopped:
                startTime = time.time()
                try:
                    if not objRef.connectionInProgress:
                        if not objRef.connected:
                            try:
                                objRef.releaseResources()
                            except Exception as e:
                                logBoth('logTakeNote', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, exception releasing resources: {e}",
                                        Logger.RISK)
                            try:
                                objRef.reconnect()
                            except Exception as e:
                                logBoth('logTakeAction', RTSPCam.logSource,
                                        f"In RTSPCam.{objRef.name}, exception in reconnect: {e}",
                                        Logger.PROBLEM)
                                # Ensure connectionInProgress is reset even if reconnect throws
                                objRef.connectionInProgress = False
                                objRef.connected = False
                                objRef.camAvailable = False
                except Exception as e:
                    logBoth('logTakeAction', RTSPCam.logSource,
                            f"In RTSPCam.{objRef.name}, unexpected exception in monitoring thread: {e}",
                            Logger.PROBLEM)
                    # Reset state to allow recovery
                    objRef.connectionInProgress = False

                endTime = time.time()
                sleepTime = 1.0 - (endTime - startTime)
                if sleepTime > 0:
                    try:
                        time.sleep(sleepTime)
                    except:
                        pass

            logBoth('logTakeNote', RTSPCam.logSource,
                    f"In RTSPCam.{objRef.name}, monitoring thread exited",
                    Logger.INFO)

        connectionMonitoringThread = threading.Thread(
            name=f"Monitoring and Re-establishing camera connection at {self.IP}",
            target=monitorAndReEstablishConnection,
            args=(),
            daemon=True
        )

        if (self.connectionAttempts == 1) or (
                (self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
            if (objRef.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0:
                logBoth('logTakeAction', RTSPCam.logSource,
                        f"RTSPCam {self.name} is NOT CONNECTED! Attempting reconnection...",
                        Logger.PROBLEM)
            logBoth('logTakeNote', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, about to start camera connection monitoring thread",
                    Logger.INFO)
        self.connectionMonitoringThreadStarted = True
        connectionMonitoringThread.start()

    def getLatestFrame(self) -> Tuple[bool, Union[None, np.ndarray]]:
        if not self.camAvailable:
            # printBoldRed(f"No frame returned because {self.camAvailable = }")
            return False, None
        if self.latestCamFrame is not None:
            frameCopy = copy.deepcopy(self.latestCamFrame)
            return True, frameCopy
        return False, None

    def isConnected(self) -> bool:
        if self.connected:
            return True
        return False

    def releaseResources(self):
        if hasattr(self,"camProcess"):
            if self.camProcess is not None:
                try:
                    self.camProcess.kill()
                except:
                    pass
            self.camProcess = None
        self.camAvailable = False
        self.connected = False
        self.stopFrameUpdateThread = True
        if (self.connectionAttempts == 1) or (
                (self.connectionAttempts % RTSPCam.LOG_CONNECTION_PROBLEM_EVERY_N_SECS) == 0):
            logBoth('logTakeNote', RTSPCam.logSource,
                    f"In RTSPCam.{self.name}, killed frame update thread",
                    Logger.INFO)
        # printBoldBlue(f"Setting {self.camAvailable = } and {self.connected = } in releaseResources()")


# TESTING RTSPCam

# ================================================================================================
# COMPREHENSIVE TESTING FOR RTSPCam
# ================================================================================================
#
# This test suite allows you to verify camera recovery under various failure scenarios:
#   1. Normal operation
#   2. Camera power off/on
#   3. Network cable disconnect/reconnect
#   4. Camera freeze/hang
#   5. Extended disconnection periods
#
# INSTRUCTIONS:
#   1. Uncomment the test section at the bottom
#   2. Run the script
#   3. Follow the on-screen prompts to test various scenarios
#   4. Press 'q' in the video window to quit
#
# ================================================================================================

def runComprehensiveTest():
    """
    Comprehensive test for RTSPCam recovery capabilities.
    Tests: power cycling, network disconnection, stream corruption recovery.
    """
    import time
    import cv2
    import threading
    from datetime import datetime

    # ==================== CONFIGURATION ====================
    CAMERA_IP = "192.168.1.64"
    CAMERA_PORT = 80
    CAMERA_UID = "admin"
    CAMERA_PWD = "Auto9753"
    CAMERA_NAME = "Test Camera 1"

    # Test settings
    STATUS_PRINT_INTERVAL = 2.0  # Print status every N seconds
    FRAME_DISPLAY_ENABLED = True  # Set False for headless testing

    # ========================================================

    class TestStatistics:
        """Track statistics during testing"""

        def __init__(self):
            self.total_frames = 0
            self.frames_since_last_report = 0
            self.connection_losses = 0
            self.connection_recoveries = 0
            self.last_frame_time = None
            self.test_start_time = None
            self.last_connected_state = False
            self.max_disconnection_duration = 0
            self.current_disconnection_start = None
            self.lock = threading.Lock()

        def record_frame(self):
            with self.lock:
                self.total_frames += 1
                self.frames_since_last_report += 1
                self.last_frame_time = time.time()

        def record_connection_change(self, connected: bool):
            with self.lock:
                if connected and not self.last_connected_state:
                    # Recovery detected
                    self.connection_recoveries += 1
                    if self.current_disconnection_start:
                        duration = time.time() - self.current_disconnection_start
                        self.max_disconnection_duration = max(self.max_disconnection_duration, duration)
                        self.current_disconnection_start = None
                elif not connected and self.last_connected_state:
                    # Disconnection detected
                    self.connection_losses += 1
                    self.current_disconnection_start = time.time()
                self.last_connected_state = connected

        def get_fps(self):
            with self.lock:
                fps = self.frames_since_last_report / STATUS_PRINT_INTERVAL
                self.frames_since_last_report = 0
                return fps

    def print_banner(text, char='='):
        width = 70
        print(char * width)
        print(f"{text:^{width}}")
        print(char * width)

    def print_status(camera, stats):
        """Print current camera and test status"""
        now = datetime.now().strftime("%H:%M:%S")
        fps = stats.get_fps()
        uptime = time.time() - stats.test_start_time if stats.test_start_time else 0

        # Connection status with color indicator
        if camera.connected and camera.camAvailable:
            conn_status = "🟢 CONNECTED"
        elif camera.connectionInProgress:
            conn_status = "🟡 CONNECTING..."
        else:
            conn_status = "🔴 DISCONNECTED"

        print(f"\n[{now}] Status Report:")
        print(f"  Connection:        {conn_status}")
        print(f"  Camera Available:  {camera.camAvailable}")
        print(f"  Connection Attempts: {camera.connectionAttempts}")
        print(f"  Frame Rate:        {fps:.1f} FPS")
        print(f"  Total Frames:      {stats.total_frames}")
        print(f"  Connection Losses: {stats.connection_losses}")
        print(f"  Recoveries:        {stats.connection_recoveries}")
        print(f"  Max Disconnect:    {stats.max_disconnection_duration:.1f}s")
        print(f"  Test Uptime:       {uptime:.0f}s")

    def print_instructions():
        """Print test instructions"""
        print("\n" + "=" * 70)
        print(" RECOVERY TEST INSTRUCTIONS")
        print("=" * 70)
        print("""
 While the test is running, try these scenarios:

 TEST 1: Power Cycle
   - Unplug camera power
   - Wait 10-30 seconds
   - Plug power back in
   - Expected: Status shows DISCONNECTED, then recovers to CONNECTED

 TEST 2: Network Disconnect  
   - Unplug network cable from camera
   - Wait 10-30 seconds
   - Plug network cable back in
   - Expected: Same as above

 TEST 3: Extended Outage
   - Disconnect camera for 2+ minutes
   - Reconnect
   - Expected: Should still recover (monitoring thread keeps trying)

 TEST 4: Rapid Power Cycling
   - Power off camera
   - Wait 5 seconds
   - Power on
   - Wait 5 seconds
   - Repeat 3-4 times
   - Expected: Should handle gracefully without crashing

 CONTROLS:
   Press 'q' in video window to quit
   Press Ctrl+C in terminal to force quit
""")
        print("=" * 70 + "\n")

    # ==================== MAIN TEST ====================

    print_banner("RTSPCam RECOVERY TEST SUITE")
    print(f"\nCamera: {CAMERA_IP}")
    print(f"Starting test at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create camera instance
    print("\n[*] Creating RTSPCam instance...")
    camera = RTSPCam(
        IP=CAMERA_IP,
        port=CAMERA_PORT,
        uid=CAMERA_UID,
        password=CAMERA_PWD,
        name=CAMERA_NAME
    )

    stats = TestStatistics()
    stats.test_start_time = time.time()
    stats.last_connected_state = camera.connected

    print(f"[*] Initial connection state: {'CONNECTED' if camera.connected else 'DISCONNECTED'}")

    print_instructions()

    input("Press ENTER to start the test...")

    print("\n[*] Test running. Monitoring camera status...\n")

    # Status printing thread
    stop_status_thread = False

    def status_printer():
        while not stop_status_thread:
            print_status(camera, stats)
            # Check for connection state changes
            stats.record_connection_change(camera.connected)
            time.sleep(STATUS_PRINT_INTERVAL)

    status_thread = threading.Thread(target=status_printer, daemon=True)
    status_thread.start()

    # Main loop
    try:
        window_name = f"RTSPCam Test - {CAMERA_IP}"
        if FRAME_DISPLAY_ENABLED:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 960, 540)

        # Create a blank/disconnected image
        disconnected_img = np.zeros((540, 960, 3), dtype=np.uint8)
        cv2.putText(disconnected_img, "DISCONNECTED", (300, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
        cv2.putText(disconnected_img, "Waiting for camera...", (280, 330),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (128, 128, 128), 2)

        connecting_img = np.zeros((540, 960, 3), dtype=np.uint8)
        cv2.putText(connecting_img, "CONNECTING...", (320, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)

        while True:
            frame_got, frame = camera.getLatestFrame()

            if frame_got and frame is not None:
                stats.record_frame()

                # Add status overlay to frame
                status_text = f"LIVE | Frames: {stats.total_frames} | Recoveries: {stats.connection_recoveries}"
                cv2.putText(frame, status_text, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Add timestamp
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                cv2.putText(frame, timestamp, (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

                display_frame = frame
            else:
                # Show appropriate status image
                if camera.connectionInProgress:
                    display_frame = connecting_img.copy()
                    cv2.putText(display_frame, f"Attempt #{camera.connectionAttempts}", (350, 330),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (128, 128, 128), 2)
                else:
                    display_frame = disconnected_img.copy()
                    if stats.current_disconnection_start:
                        disc_duration = time.time() - stats.current_disconnection_start
                        cv2.putText(display_frame, f"Disconnected for: {disc_duration:.1f}s", (300, 380),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 128, 128), 2)

            if FRAME_DISPLAY_ENABLED:
                cv2.imshow(window_name, display_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n[*] Quit requested by user")
                    break

            time.sleep(0.03)  # ~30 FPS display rate

    except KeyboardInterrupt:
        print("\n[*] Test interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\n[!] Test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        stop_status_thread = True
        time.sleep(0.5)

        print_banner("TEST SUMMARY", '-')
        print(f"""
  Test Duration:         {time.time() - stats.test_start_time:.1f} seconds
  Total Frames Received: {stats.total_frames}
  Connection Losses:     {stats.connection_losses}
  Successful Recoveries: {stats.connection_recoveries}
  Max Disconnection:     {stats.max_disconnection_duration:.1f} seconds
  Final State:           {'CONNECTED' if camera.connected else 'DISCONNECTED'}
""")

        if stats.connection_losses > 0 and stats.connection_recoveries == stats.connection_losses:
            print("  ✅ PASS: All disconnections were recovered successfully!")
        elif stats.connection_losses > stats.connection_recoveries:
            pending = stats.connection_losses - stats.connection_recoveries
            print(f"  ⚠️  WARNING: {pending} disconnection(s) not yet recovered")
        else:
            print("  ℹ️  No disconnections occurred during test")

        print("\n[*] Stopping camera...")
        camera.stop()

        if FRAME_DISPLAY_ENABLED:
            cv2.destroyAllWindows()

        print("[*] Test complete.")
        print_banner("END OF TEST", '=')


def runQuickConnectionTest():
    """
    Quick test to verify camera can connect and receive frames.
    Runs for 10 seconds and reports results.
    """
    print("\n" + "=" * 50)
    print(" QUICK CONNECTION TEST (10 seconds)")
    print("=" * 50)

    CAMERA_IP = "192.168.1.64"
    CAMERA_PORT = 80
    CAMERA_UID = "admin"
    CAMERA_PWD = "Auto9753"

    print(f"\n[*] Connecting to {CAMERA_IP}...")

    camera = RTSPCam(IP=CAMERA_IP, port=CAMERA_PORT, uid=CAMERA_UID, password=CAMERA_PWD, name="QuickTest")

    # Wait a moment for connection
    time.sleep(2)

    if not camera.connected:
        print("[!] Failed to connect within 2 seconds")
        print(f"    Connection attempts: {camera.connectionAttempts}")
        print("[*] Waiting 10 more seconds for connection...")

        for i in range(10):
            time.sleep(1)
            if camera.connected:
                print(f"[+] Connected after {i + 3} seconds!")
                break
        else:
            print("[!] Could not connect within 12 seconds")
            camera.stop()
            return False
    else:
        print("[+] Connected successfully!")

    # Count frames for 10 seconds
    print("[*] Counting frames for 10 seconds...")
    frame_count = 0
    start_time = time.time()

    while time.time() - start_time < 10:
        got_frame, frame = camera.getLatestFrame()
        if got_frame and frame is not None:
            frame_count += 1
        time.sleep(0.05)  # ~20 checks per second

    fps = frame_count / 10.0
    print(f"\n[*] Results:")
    print(f"    Frames received: {frame_count}")
    print(f"    Average FPS: {fps:.1f}")
    print(f"    Camera connected: {camera.connected}")

    camera.stop()

    if fps > 20:
        print("\n✅ PASS: Camera is working well")
        return True
    elif fps > 0:
        print("\n⚠️  WARNING: Low frame rate, possible issues")
        return True
    else:
        print("\n❌ FAIL: No frames received")
        return False


def runStressTest(duration_minutes=5):
    """
    Stress test - runs for extended period and monitors for any failures.
    """
    print("\n" + "=" * 50)
    print(f" STRESS TEST ({duration_minutes} minutes)")
    print("=" * 50)

    CAMERA_IP = "192.168.1.64"
    CAMERA_PORT = 80
    CAMERA_UID = "admin"
    CAMERA_PWD = "Auto9753"

    camera = RTSPCam(IP=CAMERA_IP, port=CAMERA_PORT, uid=CAMERA_UID, password=CAMERA_PWD, name="StressTest")

    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)

    frame_count = 0
    error_count = 0
    last_report = start_time
    report_interval = 30  # Report every 30 seconds

    print(f"[*] Running until {datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}")
    print("[*] Press Ctrl+C to stop early\n")

    try:
        while time.time() < end_time:
            try:
                got_frame, frame = camera.getLatestFrame()
                if got_frame and frame is not None:
                    frame_count += 1
            except Exception as e:
                error_count += 1
                print(f"[!] Error: {e}")

            # Periodic report
            if time.time() - last_report >= report_interval:
                elapsed = time.time() - start_time
                remaining = end_time - time.time()
                fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"[{elapsed / 60:.1f}m] Frames: {frame_count}, FPS: {fps:.1f}, "
                      f"Errors: {error_count}, Connected: {camera.connected}, "
                      f"Remaining: {remaining / 60:.1f}m")
                last_report = time.time()

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user")

    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0

    print(f"\n[*] Stress Test Results:")
    print(f"    Duration: {total_time / 60:.1f} minutes")
    print(f"    Total frames: {frame_count}")
    print(f"    Average FPS: {avg_fps:.1f}")
    print(f"    Errors: {error_count}")
    print(f"    Connection attempts: {camera.connectionAttempts}")

    camera.stop()

    if error_count == 0 and avg_fps > 20:
        print("\n✅ PASS: Stress test completed successfully")
    else:
        print("\n⚠️  Issues detected during stress test")


def testToSeeFrames():
    logBoth('logInfo', RTSPCam.logSource, "Starting", Logger.GENERAL)
    # camera = RTSPCam("192.168.1.100", 80, "admin", "abcd1234", "Camera 1")
    camera = RTSPCam("192.168.1.64", 80, "admin", "Auto9753", "Camera 1")
    logBoth('logInfo', RTSPCam.logSource, f"{camera}", Logger.GENERAL)
    startTime = time.time()
    repeats=100000
    try:
        # for i in range(repeats):
        while True:
            try:
                frameGot, actualFrame  = camera.getLatestFrame()
                if actualFrame is not None:
                    # print(actualFrame.shape)
                    cv2.imshow("Frame", actualFrame)
                    if cv2.waitKey(1) == ord('q'):
                        break
            except:
                pass
            time.sleep(0.05)
    except Exception as e:
        logBoth('logTakeAction', RTSPCam.logSource, f"{e}", Logger.PROBLEM)

    logBoth('logTakeAction', RTSPCam.logSource, "About to call camera.releaseResources()", Logger.PROBLEM)
    camera.stop()
    endTime = time.time()
    print(f"{(endTime - startTime)*1000/repeats} ms")


# ================================================================================================
# UNCOMMENT ONE OF THE FOLLOWING TO RUN THE DESIRED TEST:
# ================================================================================================

# Quick 10-second connection test
# runQuickConnectionTest()

# Comprehensive interactive test (for manual disconnect/reconnect testing)
# runComprehensiveTest()

# Extended stress test (default 5 minutes)
# runStressTest(duration_minutes=5)

# testToSeeFrames()

# ================================================================================================