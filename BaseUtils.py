# VERY, VERY IMPORTANT NOTE: Ensure that BaseUtils is in the project root.
# This is to ensure that getFullyQualifiedName works properly

import psutil
import os
from pathlib import Path
import inspect
import sys
from typing import Union, Optional, Dict, List, Any
from datetime import datetime
import time

# Global project root cache
_projectRoot: Optional[str] = None


# ***********************************************************
# ***** VERY, VERY IMPORTANT NOTE: *****
# Ensure that BaseUtils is in the project root.
# This is to ensure that getFullyQualifiedName works properly
# ***********************************************************


def get_project_root() -> str:
    """
    Returns the project root directory path WITHOUT trailing slash.
    Caches the result for performance.

    Returns:
        str: Absolute path to project root directory
    """
    global _projectRoot
    if _projectRoot is None:
        _projectRoot = str(Path(__file__).parent)
        _projectRoot = _projectRoot.replace("\\", "/")
    return _projectRoot


# Initialize project root on module load
get_project_root()


def getFullyQualifiedName(filePathRef: str, classRef: Optional[type] | None = None) -> str:
    """
    Get fully qualified name for a file or class.

    Args:
        filePathRef: Always pass __file__ as this parameter
        classRef: Optionally pass __class__ for class names

    Returns:
        str: Fully qualified name like 'package.module' or 'package.module.ClassName'

    Example:
        getFullyQualifiedName(__file__)  # Returns 'utils.BaseUtils'
        getFullyQualifiedName(__file__, MyClass)  # Returns 'utils.BaseUtils.MyClass'
    """
    try:
        projRoot = get_project_root()
        isClass = inspect.isclass(classRef)
        currentFilePath = filePathRef.replace('\\', '/')

        if isClass:
            currentClass = classRef.__name__
            currentFilename = inspect.getmodulename(filePathRef)
        else:
            currentClass = None
            currentFilename = inspect.getmodulename(filePathRef)

        file_name, file_extension = os.path.splitext(currentFilePath)

        # Handle case where getmodulename returns None
        if currentFilename is None:
            lastSlash = currentFilePath.rfind('/')
            temp = currentFilePath[lastSlash + 1:]
            lastDot = temp.rfind('.')
            if lastDot != -1:
                currentFilename = temp[:lastDot]
            else:
                currentFilename = temp

        # Build package path
        package = ".".join(
            "".join(
                "".join(
                    "".join(currentFilePath.split(projRoot))
                    .split(file_extension)
                )
                .replace("/", ".")
                .replace("\\", ".")
                .split('.' + currentFilename)
            ).split(".")
        )[1:]

        # Build fully qualified name
        fullyQualifiedName = (
                ((package + '.') if package else '') +
                currentFilename +
                (('.' + currentClass) if isClass else '')
        )

        return fullyQualifiedName

    except Exception as e:
        # Fallback to basic module name if something goes wrong
        return inspect.getmodulename(filePathRef) or "unknown_module"


def getCurrentTime() -> str:
    """
    Get current timestamp in YYYY-MM-DD-HH-MM-SS-mmm format.

    Returns:
        str: Formatted timestamp with milliseconds

    Example:
        '2024-01-15-14-30-45-123'
    """
    msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
    dt, ms = msTime.split('.')
    ms = "{:03d}".format(int(ms) // 1000)
    currentTime = f'{dt}-{ms}'
    return currentTime


def getDatetimeFromString(timeStr: str) -> datetime:
    """
    Convert time string in YYYY-MM-DD-HH-MM-SS-mmm format to datetime object.

    Args:
        timeStr: Time string in format 'YYYY-MM-DD-HH-MM-SS-mmm'

    Returns:
        datetime: Parsed datetime object

    Raises:
        ValueError: If string format is invalid
    """
    try:
        times = timeStr.strip().split("-")
        if len(times) < 7:
            raise ValueError(f"Invalid time string format: {timeStr}")

        newTime = f"{times[1]}/{times[2]}/{times[0]} {times[3]}:{times[4]}:{times[5]}.{times[6]}"
        datetime_object = datetime.strptime(newTime, '%m/%d/%Y %H:%M:%S.%f')
        return datetime_object
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse time string '{timeStr}': {e}")


def getTimeDotTimeFromString(timeStr: str) -> float:
    """
    Convert time string in YYYY-MM-DD-HH-MM-SS-mmm format to Unix timestamp.

    Args:
        timeStr: Time string in format 'YYYY-MM-DD-HH-MM-SS-mmm'

    Returns:
        float: Unix timestamp

    Raises:
        ValueError: If string format is invalid
    """
    try:
        times = timeStr.strip().split("-")
        if len(times) < 7:
            raise ValueError(f"Invalid time string format: {timeStr}")

        # Normalize milliseconds to 6 digits
        millis = times[6]
        millisLength = len(millis)
        if millisLength > 6:
            millis = millis[:6]
        elif millisLength < 6:
            millis = millis + '0' * (6 - millisLength)

        newTime = f"{times[1]}/{times[2]}/{times[0]} {times[3]}:{times[4]}:{times[5]}.{int(round(int(millis), 0))}"
        datetime_object = datetime.strptime(newTime, '%m/%d/%Y %H:%M:%S.%f')
        return datetime_object.timestamp()
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse time string '{timeStr}': {e}")


def getYMDHMSmFormatFromTimeDotTime(timeStr: Union[str, float]) -> str:
    """
    Convert Unix timestamp to YYYY-MM-DD-HH-MM-SS-mmm format.

    Args:
        timeStr: Unix timestamp as string or float

    Returns:
        str: Formatted time string or original input if conversion fails
    """
    try:
        if isinstance(timeStr, float):
            timeStr = str(timeStr)

        parts = timeStr.strip().split(".")
        t = float(parts[0])
        firstPart = time.localtime(t)
        firstPart = time.strftime("%Y-%m-%d-%H-%M-%S", firstPart)

        # Handle microseconds/milliseconds part
        microseconds = parts[1] if len(parts) > 1 else "0"
        finalString = f"{firstPart}-{microseconds}"

        return finalString
    except Exception as e:
        # Return original string if conversion fails
        return str(timeStr)


# def getPostgresDatetimeFromString(timeStr: str) -> str:
#     """
#     Convert YYYY-MM-DD-HH-MM-SS-mmm format to PostgreSQL datetime format.
#
#     Args:
#         timeStr: Time string in format 'YYYY-MM-DD-HH-MM-SS-mmm'
#
#     Returns:
#         str: PostgreSQL datetime format 'DD-MM-YYYY HH:MM:SS'
#     """
#     try:
#         # Remove last 4 characters (milliseconds)
#         timeStr = timeStr[:-4]
#         times = timeStr.strip().split("-")
#
#         if len(times) < 6:
#             raise ValueError(f"Invalid time string format: {timeStr}")
#
#         newTime = f"{times[2]}-{times[1]}-{times[0]} {times[3]}:{times[4]}:{times[5]}"
#         return newTime
#     except (ValueError, IndexError) as e:
#         raise ValueError(f"Failed to convert to PostgreSQL format '{timeStr}': {e}")

def getPostgresDatetimeFromString(timeStr: str) -> str:
    """
    Convert YYYY-MM-DD-HH-MM-SS-mmm format to PostgreSQL YYYY-MM-DD HH:MM:SS format.

    Args:
        timeStr: Time string in format 'YYYY-MM-DD-HH-MM-SS-mmm'

    Returns:
        str: PostgreSQL datetime format 'YYYY-MM-DD HH:MM:SS'
    """
    try:
        # Split by hyphen and validate
        parts = timeStr.strip().split("-")
        if len(parts) < 6:
            raise ValueError(f"Invalid time string format: {timeStr}")

        # Extract components (ignore milliseconds if present)
        year = parts[0]
        month = parts[1]
        day = parts[2]
        hour = parts[3]
        minute = parts[4]
        second = parts[5]

        # Build standard PostgreSQL format: YYYY-MM-DD HH:MM:SS
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to convert to PostgreSQL format '{timeStr}': {e}")

def getCurrentTimeInMS() -> float:
    """
    Get current Unix timestamp in seconds (with fractional part for milliseconds).

    Returns:
        float: Current Unix timestamp
    """
    return time.time()


def process_memory() -> int:
    """
    Get current process memory usage in bytes.

    Returns:
        int: Memory usage in bytes (RSS - Resident Set Size)
    """
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        return mem_info.rss
    except Exception as e:
        # Return 0 if unable to get memory info
        return 0


def profile(func):
    """
    Decorator to profile memory usage of a function.

    Usage:
        @profile
        def my_function():
            # function code

    Prints memory consumed by the function to stdout.
    """

    def wrapper(*args, **kwargs):
        mem_before = process_memory()
        result = func(*args, **kwargs)
        mem_after = process_memory()
        print(f"{func.__name__}: consumed memory: {mem_after - mem_before:,} bytes "
              f"(before: {mem_before:,}, after: {mem_after:,})")
        return result

    return wrapper


def getCommandLineArgumentsForPythonProcesses() -> List[str]:
    """
    Extract command line arguments for Python processes.
    Skips the python executable and script name.

    Returns:
        List[str]: List of command line arguments, empty list if none found
    """
    try:
        startingArgument = -1

        # Find where python executable is in argv
        for idx, argument in enumerate(sys.argv):
            if "python" in argument.lower():
                startingArgument = idx + 1
                break

        # Try to skip script name if present
        try:
            _ = sys.argv[startingArgument + 1]
            startingArgument = startingArgument + 1
        except (IndexError, TypeError):
            startingArgument = -1

        if startingArgument == -1:
            return []

        arguments = sys.argv[startingArgument:]
        return arguments
    except Exception:
        return []


def getCommandLineArgumentsAsDictionary() -> Dict[str, str]:
    """
    Parse command line arguments into a dictionary.
    Expected format: key=value

    Returns:
        Dict[str, str]: Dictionary of arguments with keys and values lowercased

    Example:
        python script.py Mode=Test Debug=True
        Returns: {'mode': 'test', 'debug': 'true'}
    """
    try:
        startingArgument = -1
        argDict = {}

        # Find where python.exe is in argv
        for idx, argument in enumerate(sys.argv):
            if "python.exe" in argument.lower():
                startingArgument = idx + 1
                break

        if startingArgument == -1:
            startingArgument = 0

        # Try to skip script name if present
        try:
            _ = sys.argv[startingArgument + 1]
            startingArgument = startingArgument + 1
        except (IndexError, TypeError):
            startingArgument = -1

        if startingArgument == -1:
            return argDict

        arguments = sys.argv[startingArgument:]

        # Parse key=value pairs
        for argument in arguments:
            parts = argument.split("=")
            try:
                key = parts[0].strip().lower()
                value = parts[1].strip().lower()
                argDict[key] = value
            except (IndexError, AttributeError):
                # Skip malformed arguments
                pass

        return argDict
    except Exception:
        return {}


def getGeneralLoggingMessage(source: str, message: str) -> str:
    """
    Create a formatted logging message with timestamp, source, function name, and line number.

    Args:
        source: Source identifier (usually from getFullyQualifiedName)
        message: The log message

    Returns:
        str: Formatted log message

    Example:
        'YYYY-MM-DD-HH-MM-SS.mmm: source.function_name:123->message'
    """
    try:
        currentFrame = inspect.currentframe()
        func_name = ""
        lno = ""

        # Try to get caller frame information
        try:
            callerFrame = currentFrame.f_back.f_back.f_back
            co = callerFrame.f_code
            func_name = co.co_name
            lno = callerFrame.f_lineno
        except (AttributeError, TypeError):
            try:
                callerFrame = currentFrame.f_back.f_back
                co = callerFrame.f_code
                func_name = co.co_name
                lno = callerFrame.f_lineno
            except (AttributeError, TypeError):
                try:
                    callerFrame = currentFrame.f_back
                    co = callerFrame.f_code
                    func_name = co.co_name
                    lno = callerFrame.f_lineno
                except (AttributeError, TypeError):
                    pass

        # Format timestamp
        msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
        dt, ms = msTime.split('.')
        ms = int(ms) // 1000
        currentTime = f'{dt}.{ms:03}'

        # Build message
        sourceStr = source.strip() if source is not None else ""
        sourceSuffix = "." if source is not None else ""
        messageToBeLogged = f'{currentTime}: {sourceStr}{sourceSuffix}{func_name.strip()}:{lno}->{message}'

        return messageToBeLogged
    except Exception as e:
        # Fallback to basic message if something goes wrong
        return f"{datetime.now()}: {message}"


def getTodaysDateAsString() -> str:
    """
    Get today's date as DD-MM-YYYY string.

    Returns:
        str: Today's date in format 'DD-MM-YYYY'

    Example:
        '15-01-2024'
    """
    return datetime.now().strftime("%d-%m-%Y")


def countNonNoneValues(inputDict: Optional[Dict[Any, Any]]) -> int:
    """
    Count the number of non-None values in a dictionary.

    Args:
        inputDict: Dictionary to count values in

    Returns:
        int: Count of non-None values, 0 if inputDict is None
    """
    if inputDict is None:
        return 0

    count = 0
    for key, value in inputDict.items():
        if value is not None:
            count += 1

    return count


def convertToPostgresTimestamp(timeStr: Union[str, float]) -> str:
    """
    Convert various time formats to PostgreSQL timestamp format.

    Args:
        timeStr: Unix timestamp (float/string) or formatted time string

    Returns:
        str: PostgreSQL format 'YYYY-MM-DD HH:MM:SS'

    Raises:
        ValueError: If format cannot be determined
    """
    try:
        # Try to parse as Unix timestamp
        try:
            ts = float(timeStr)
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            pass

        # Check if already in PostgreSQL format (YYYY-MM-DD HH:MM:SS)
        timeStr = str(timeStr).strip()
        if ' ' in timeStr and ':' in timeStr and '-' in timeStr:
            # Validate it has the right structure
            date_part, time_part = timeStr.split(' ', 1)
            if len(date_part.split('-')) == 3 and len(time_part.split(':')) == 3:
                return timeStr

        # Try custom format: YYYY-MM-DD-HH-MM-SS-microseconds
        if '-' in timeStr and ' ' not in timeStr:
            parts = timeStr.split("-")
            if len(parts) >= 6:
                year, month, day, hour, minute, second = parts[:6]
                return f"{year}-{month}-{day} {hour}:{minute}:{second}"

        raise ValueError(f"Unknown datetime format: {timeStr}")

    except Exception as e:
        raise ValueError(f"Failed to convert '{timeStr}' to PostgreSQL format: {e}")

import numpy as np
import cv2
def saveImage(image : np.ndarray, stage : str | None = None):
    dirToSave = "C:/RHS_Images"
    if image is not None:
        if stage is None:
            os.makedirs(f"{dirToSave}", exist_ok=True)
        else:
            os.makedirs(f"{dirToSave}/{stage}", exist_ok=True)
        cv2.imwrite(f"{dirToSave}/{stage}/{time.time()}.png", image)

# Module self-test (only runs when module is executed directly)
if __name__ == '__main__':
    # Test basic functions
    print(f"Project root: {get_project_root()}")
#     print(f"Current time: {getCurrentTime()}")
#     print(f"Today's date: {getTodaysDateAsString()}")
#     print(f"Fully qualified name: {getFullyQualifiedName(__file__)}")
#
#     # Test command line arguments
#     args = getCommandLineArgumentsAsDictionary()
#     print(f"Command line arguments: {args}")
#
#     # Test logging message
#     testMsg = getGeneralLoggingMessage(getFullyQualifiedName(__file__), "Test message")
#     print(f"Log message: {testMsg}")