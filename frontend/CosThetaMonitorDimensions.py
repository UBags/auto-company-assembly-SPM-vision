import ctypes
import subprocess
import sys
import tkinter
import os
import platform
import utils

import Xlib.display
from PySide6.QtWidgets import QApplication
from utils.CosThetaFileUtils import *
# from frontendutils.CosThetaPrintUtils import *
from Configuration import *

PYTHON_V3 = sys.version_info >= (3,0,0) and sys.version_info < (4,0,0)

monitorHeight = 560
monitorWidth = 800
monitorDimensionsFound = False
isWindows = False
isLinux = False
isMac = False
app = None

# def is_in_path(aString) -> bool:
#     paths = os.environ.get('PATH')
#     if ';' in paths:
#         paths = paths.split(';')
#     elif ':' in paths:
#         paths = paths.split(':')
#     # printPlain(paths)
#     for path in paths:
#         onlyfiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
#         for file in onlyfiles:
#             if aString in file:
#                 return True
#     return False
platformPopulated = False
def populatePlatform():
    global platformPopulated
    if not platformPopulated:
        global isMac, isWindows, isLinux
        if isMac or isWindows or isLinux:
            return
        pl = platform.system().lower()
        if 'win' in pl:
            isWindows = True
            # print(f"Platform is Windows")
        elif 'darwin' in pl:
            isMac = True
            # print(f"Platform is Mac")
        else:
            isLinux = True
            # print(f"Platform is Linux")
    platformPopulated = True

'''
def getMonitorDimensions(measurement="px"):
    """
    Tries to detect the screen resolution from the system.
    @param measurement: The measurement to describe the screen resolution in. Can be either 'px', 'inch' or 'mm'.
    @return: (screen_width,screen_height) where screen_width and screen_height are int types according to measurement.
    """
    global monitorWidth, monitorHeight, monitorDimensionsFound
    if monitorDimensionsFound:
        return
    mm_per_inch = 25.4
    px_per_inch = 72.0  # most common
    # try:  # Platforms supported by GTK3, Fx Linux/BSD
    #     import Gdk
    #     screen = Gdk.Screen.get_default()
    #     if measurement == "px":
    #         monitorWidth = screen.get_width()
    #         monitorHeight = screen.get_height()
    #     elif measurement == "inch":
    #         monitorWidth = screen.get_width_mm() / mm_per_inch
    #         monitorHeight = screen.get_height_mm() / mm_per_inch
    #     elif measurement == "mm":
    #         monitorWidth = screen.get_width_mm()
    #         monitorHeight = screen.get_height_mm()
    #     else:
    #         raise NotImplementedError("Handling %s is not implemented." % measurement)
    # except:
    try:
        # app = QApplication([])
        # screen_resolution = app.desktop().screenGeometry()
        # app = QApplication(sys.argv)
        screenSize = app.screens()[0].size()
        monitorWidth, monitorHeight = screenSize.width(), screenSize.height()
        # app.exit()
    except Exception as e:
        printPlain(e)
        try:  # Probably the most OS independent way
            root = tkinter.Tk()
            printPlain("Using tkinter / Tkinter to get screen dimensions")
            if measurement == "px":
                monitorWidth = root.winfo_screenwidth()
                monitorHeight = root.winfo_screenheight()
            elif measurement == "inch":
                monitorWidth = root.winfo_screenmmwidth() / mm_per_inch
                monitorHeight = root.winfo_screenmmheight() / mm_per_inch
            elif measurement == "mm":
                monitorWidth = root.winfo_screenmmwidth()
                monitorHeight = root.winfo_screenmmheight()
            else:
                raise NotImplementedError("Handling %s is not implemented." % measurement)
        except:
            try:  # Windows only
                # monitorWidth = GetSystemMetrics(0)
                # monitorHeight = GetSystemMetrics(1)
                if measurement == "px":
                    pass
                elif measurement == "inch":
                    monitorWidth = monitorWidth / px_per_inch
                    monitorHeight = monitorHeight / px_per_inch
                elif measurement == "mm":
                    monitorWidth = monitorWidth / mm_per_inch
                    monitorHeight = monitorHeight / mm_per_inch
                else:
                    raise NotImplementedError("Handling %s is not implemented." % measurement)
            except:
                try:  # Windows only
                    user32 = ctypes.windll.user32
                    monitorWidth = user32.GetSystemMetrics(0)
                    monitorHeight = user32.GetSystemMetrics(1)
                    if measurement == "px":
                        pass
                    elif measurement == "inch":
                        monitorWidth = monitorWidth / px_per_inch
                        monitorHeight = monitorHeight / px_per_inch
                    elif measurement == "mm":
                        monitorWidth = monitorWidth / mm_per_inch
                        monitorHeight = monitorHeight / mm_per_inch
                    else:
                        raise NotImplementedError("Handling %s is not implemented." % measurement)
                except:
                    try:  # Mac OS X only
                        import AppKit
                        for screen in AppKit.NSScreen.screens():
                            monitorWidth = screen.frame().size._width
                            monitorHeight = screen.frame().size._height
                            if measurement == "px":
                                pass
                            elif measurement == "inch":
                                monitorWidth = monitorWidth / px_per_inch
                                monitorHeight = monitorHeight / px_per_inch
                            elif measurement == "mm":
                                monitorWidth = monitorWidth / mm_per_inch
                                monitorHeight = monitorHeight / mm_per_inch
                            else:
                                raise NotImplementedError("Handling %s is not implemented." % measurement)
                            break
                    except:
                        try:  # Linux/Unix
                            resolution = Xlib.display.Display().screen().root.get_geometry()
                            monitorWidth = resolution._width
                            monitorHeight = resolution._height
                            if measurement == "px":
                                pass
                            elif measurement == "inch":
                                monitorWidth = monitorWidth / px_per_inch
                                monitorHeight = monitorHeight / px_per_inch
                            elif measurement == "mm":
                                monitorWidth = monitorWidth / mm_per_inch
                                monitorHeight = monitorHeight / mm_per_inch
                            else:
                                raise NotImplementedError("Handling %s is not implemented." % measurement)
                        except:
                            try:  # Linux/Unix
                                if not is_in_path("xrandr"):
                                    raise ImportError("Cannot read the output of xrandr, if any.")
                                else:
                                    args = ["xrandr", "-q", "-d", ":0"]
                                    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
                                    for line in iter(proc.stdout.readline, ''):
                                        if isinstance(line, bytes):
                                            line = line.decode("utf-8")
                                        if "Screen" in line:
                                            monitorWidth = int(line.split()[7])
                                            monitorHeight = int(line.split()[9][:-1])
                                            if measurement == "px":
                                                pass
                                            elif measurement == "inch":
                                                monitorWidth = monitorWidth / px_per_inch
                                                monitorHeight = monitorHeight / px_per_inch
                                            elif measurement == "mm":
                                                monitorWidth = monitorWidth / mm_per_inch
                                                monitorHeight = monitorHeight / mm_per_inch
                                            else:
                                                raise NotImplementedError(
                                                    "Handling %s is not implemented." % measurement)
                            except:
                                # Failover
                                monitorWidth = 1366
                                monitorHeight = 768
                                sys.stderr.write(
                                    "WARNING: Failed to detect screen size. Falling back to %sx%s" % monitorWidth, monitorHeight)
                                if measurement == "px":
                                    pass
                                elif measurement == "inch":
                                    monitorWidth = monitorWidth / px_per_inch
                                    monitorHeight = monitorHeight / px_per_inch
                                elif measurement == "mm":
                                    monitorWidth = monitorWidth / mm_per_inch
                                    monitorHeight = monitorHeight / mm_per_inch
                                else:
                                    raise NotImplementedError(
                                        "Handling %s is not implemented." % measurement)
    monitorDimensionsFound = True
    printBoldGreen(f"Monitor found - {monitorWidth} x {monitorHeight}")
    printBoldSeparator()
'''

def getMonitorDimensions(measurement="px"):
    """
    Tries to detect the screen resolution from the system.
    @param measurement: The measurement to describe the screen resolution in. Can be either 'px', 'inch' or 'mm'.
    @return: (screen_width,screen_height) where screen_width and screen_height are int types according to measurement.
    """
    global monitorWidth, monitorHeight, monitorDimensionsFound
    if monitorDimensionsFound:
        return
    mm_per_inch = 25.4
    px_per_inch = 72.0  # most common

    try:
        try:
            if isLinux:
                # printBoldBlue("Trying to find dimensions of monitor in Linux environment")
                try:  # Linux/Unix
                    resolution = Xlib.display.Display().screen().root.get_geometry()
                    monitorWidth = resolution._width
                    monitorHeight = resolution._height
                    if measurement == "px":
                        pass
                    elif measurement == "inch":
                        monitorWidth = monitorWidth / px_per_inch
                        monitorHeight = monitorHeight / px_per_inch
                    elif measurement == "mm":
                        monitorWidth = monitorWidth / mm_per_inch
                        monitorHeight = monitorHeight / mm_per_inch
                    else:
                        raise NotImplementedError("Handling %s is not implemented." % measurement)
                    monitorDimensionsFound = True
                except Exception as e:
                    # printBoldRed(e)
                    try:  # Linux/Unix
                        # printBoldBlue("Trying to find dimensions of monitor in Linux environment through xrandr")
                        if not is_in_path("xrandr"):
                            raise ImportError("Cannot read the output of xrandr, if any.")
                        else:
                            args = ["xrandr", "-q", "-d", ":0"]
                            proc = subprocess.Popen(args, stdout=subprocess.PIPE)
                            for line in iter(proc.stdout.readline, ''):
                                if isinstance(line, bytes):
                                    line = line.decode("utf-8")
                                if "Screen" in line:
                                    # printBoldGreen(line)
                                    monitorWidth = int(line.split()[7])
                                    monitorHeight = int(line.split()[9][:-1])
                                    if measurement == "px":
                                        pass
                                    elif measurement == "inch":
                                        monitorWidth = monitorWidth / px_per_inch
                                        monitorHeight = monitorHeight / px_per_inch
                                    elif measurement == "mm":
                                        monitorWidth = monitorWidth / mm_per_inch
                                        monitorHeight = monitorHeight / mm_per_inch
                                    else:
                                        raise NotImplementedError(
                                            "Handling %s is not implemented." % measurement)
                                    monitorDimensionsFound = True
                                    break
                    except Exception as e:
                        # printBoldRed(e)
                        raise NotImplementedError(
                            "Handling %s is not implemented." % measurement)
            if isWindows:
                # printBoldBlue("Trying to find dimensions of monitor in Windows environment")
                import win32api
                try:  # Windows only
                    monitorWidth = win32api.GetSystemMetrics(0)
                    monitorHeight = win32api.GetSystemMetrics(1)
                    if measurement == "px":
                        pass
                    elif measurement == "inch":
                        monitorWidth = monitorWidth / px_per_inch
                        monitorHeight = monitorHeight / px_per_inch
                    elif measurement == "mm":
                        monitorWidth = monitorWidth / mm_per_inch
                        monitorHeight = monitorHeight / mm_per_inch
                    else:
                        raise NotImplementedError("Handling %s is not implemented." % measurement)
                    monitorDimensionsFound = True
                except Exception as e:
                    # printBoldRed(e)
                    try:  # Windows only
                        user32 = ctypes.windll.user32
                        monitorWidth = user32.GetSystemMetrics(0)
                        monitorHeight = user32.GetSystemMetrics(1)
                        if measurement == "px":
                            pass
                        elif measurement == "inch":
                            monitorWidth = monitorWidth / px_per_inch
                            monitorHeight = monitorHeight / px_per_inch
                        elif measurement == "mm":
                            monitorWidth = monitorWidth / mm_per_inch
                            monitorHeight = monitorHeight / mm_per_inch
                        else:
                            raise NotImplementedError("Handling %s is not implemented." % measurement)
                        monitorDimensionsFound = True
                    except Exception as e:
                        # printBoldRed(e)
                        raise NotImplementedError("Handling %s is not implemented." % measurement)
            if isMac:
                # printBoldBlue("Trying to find dimensions of monitor in Mac environment")
                try:  # Mac OS X only
                    import AppKit
                    for screen in AppKit.NSScreen.screens():
                        monitorWidth = screen.frame().size._width
                        monitorHeight = screen.frame().size._height
                        if measurement == "px":
                            pass
                        elif measurement == "inch":
                            monitorWidth = monitorWidth / px_per_inch
                            monitorHeight = monitorHeight / px_per_inch
                        elif measurement == "mm":
                            monitorWidth = monitorWidth / mm_per_inch
                            monitorHeight = monitorHeight / mm_per_inch
                        else:
                            raise NotImplementedError("Handling %s is not implemented." % measurement)
                        monitorDimensionsFound = True
                        break
                except Exception as e:
                    # printBoldRed(e)
                    raise NotImplementedError("Handling %s is not implemented." % measurement)
            monitorDimensionsFound = True
        except Exception as e:
            # printBoldRed(e)
            try:  # Probably the most OS independent way
                root = tkinter.Tk()
                # printBoldBlue("Using tkinter / Tkinter to get screen dimensions")
                if measurement == "px":
                    monitorWidth = root.winfo_screenwidth()
                    monitorHeight = root.winfo_screenheight()
                elif measurement == "inch":
                    monitorWidth = root.winfo_screenmmwidth() / mm_per_inch
                    monitorHeight = root.winfo_screenmmheight() / mm_per_inch
                elif measurement == "mm":
                    monitorWidth = root.winfo_screenmmwidth()
                    monitorHeight = root.winfo_screenmmheight()
                else:
                    raise NotImplementedError("Handling %s is not implemented." % measurement)
                monitorDimensionsFound = True
            except Exception as e:
                # printBoldRed(e)
                raise NotImplementedError("Handling %s is not implemented." % measurement)
    except Exception as e:
        # printBoldRed(e)
        try:
            # app = QApplication([])
            # screen_resolution = app.desktop().screenGeometry()
            # app = QApplication(sys.argv)
            # printBoldBlue("Trying to get monitor dimensions through app instance")
            screenSize = app.screens()[0].size()
            monitorWidth, monitorHeight = screenSize.width(), screenSize.height()
            monitorDimensionsFound = True
            # app.exit()
        except Exception as e:
            # printPlain(e)
            # Failover
            monitorWidth = 1366
            monitorHeight = 768
            sys.stderr.write(
                "WARNING: Failed to detect screen size. Falling back to %sx%s" % monitorWidth,
                monitorHeight)
            if measurement == "px":
                pass
            elif measurement == "inch":
                monitorWidth = monitorWidth / px_per_inch
                monitorHeight = monitorHeight / px_per_inch
            elif measurement == "mm":
                monitorWidth = monitorWidth / mm_per_inch
                monitorHeight = monitorHeight / mm_per_inch
            monitorDimensionsFound = False
    if CosThetaConfigurator.getInstance().getReportMonitorFound():
        print(f"Monitor found : {monitorDimensionsFound}; Monitor dimensions - {monitorWidth} x {monitorHeight}; monitorDimensionsFound = {monitorDimensionsFound}")
    # printBoldSeparator()

def populateMonitorDimensions():
    try:
        getMonitorDimensions()
    except:
        print(f"No monitor found - exiting")
        # printBoldSeparator()
        sys.exit(1)

linuxAccomodatingFactor = 0.9

def getMonitorWidth():
    return int(monitorWidth)

def getMonitorHeight():
    if isLinux:
        return int(monitorHeight * linuxAccomodatingFactor)
    else:
        return int(monitorHeight)

def getAppInstance():
    global app
    if app is None:
        if not QApplication.instance():
            # print("App instance created")
            app = QApplication(sys.argv)
            populatePlatform()
            getMonitorDimensions()
            # app.setQuitOnLastWindowClosed(False)
        else:
            # printBoldRed("App instance already exists")
            app = QApplication.instance()
            populatePlatform()
            getMonitorDimensions()
    return app

# app = getAppInstance()
