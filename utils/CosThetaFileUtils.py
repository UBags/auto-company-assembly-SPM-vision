# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
File system utilities for file operations, directory management, and image saving.
"""
import os
import os.path
import shutil
from datetime import datetime
from io import StringIO
from typing import List, Optional, Union

import cv2
import numpy as np

from BaseUtils import get_project_root, getCurrentTime
from utils.CosThetaColors import CosThetaColors

# Allowed extensions for file saving
ALLOWED_EXTENSIONS = {"jpg", "png", "log", "txt"}


def printWithTime(*args) -> None:
    """Print with timestamp prefix."""
    currentTime = f'{getCurrentTime()} : '
    print(currentTime, *args, end="")


def printBoldRed(*args, includeTime: bool = True) -> None:
    """Print text in bold red."""
    print(CosThetaColors.CRED, end="")
    print(CosThetaColors.CBOLD, end="")
    if includeTime:
        printWithTime(*args)
    else:
        print(*args, end="")
    print(CosThetaColors.CEND)


def printBoldGreen(*args, includeTime: bool = True) -> None:
    """Print text in bold green."""
    print(CosThetaColors.CGREEN, end="")
    print(CosThetaColors.CBOLD, end="")
    if includeTime:
        printWithTime(*args)
    else:
        print(*args, end="")
    print(CosThetaColors.CEND)


def is_in_path(aString: str) -> bool:
    """
    Check if a string (program name) exists in the system PATH.

    Args:
        aString: The program name to search for

    Returns:
        True if found in PATH, False otherwise
    """
    paths = os.environ.get('PATH', '')
    if ';' in paths:
        paths_list = paths.split(';')
    elif ':' in paths:
        paths_list = paths.split(':')
    else:
        paths_list = [paths]

    for path in paths_list:
        try:
            onlyfiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            for file in onlyfiles:
                if aString in file:
                    return True
        except (OSError, PermissionError):
            continue
    return False


def listFiles(directory: str) -> List[str]:
    """
    List all files in a directory (not subdirectories).

    Args:
        directory: Path to directory

    Returns:
        List of filenames
    """
    response = []
    try:
        for path in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, path)):
                response.append(path)
    except (OSError, PermissionError):
        pass
    return response


def listFilesInDirectory(directory: str) -> List[str]:
    """Alias for listFiles()."""
    return listFiles(directory=directory)


def getAllFilesInDirectory(directory: str) -> List[str]:
    """Alias for listFiles()."""
    return listFiles(directory=directory)


def moveFile(sourceDirectory: str, destinationDirectory: str, file: str) -> bool:
    """
    Move a file from source to destination directory.

    Args:
        sourceDirectory: Source directory path
        destinationDirectory: Destination directory path
        file: Filename to move

    Returns:
        True if successful, False otherwise
    """
    src_path = os.path.join(sourceDirectory, file)
    dst_path = os.path.join(destinationDirectory, file)
    try:
        shutil.move(src_path, dst_path)
        return True
    except Exception:
        return False


def renameAndMoveFile(sourcePath: str, destinationPath: str) -> bool:
    """
    Move and optionally rename a file.

    Args:
        sourcePath: Full path to source file
        destinationPath: Full path to destination (including new filename)

    Returns:
        True if successful, False otherwise
    """
    targetDirectory = os.path.split(os.path.abspath(destinationPath))[0].replace('\\', '/')
    createDirectory(f"{targetDirectory}/")
    try:
        shutil.move(sourcePath, destinationPath)
        return True
    except Exception as e:
        printBoldRed(e)
        return False


def forceMoveFile(sourceDirectory: str, destinationDirectory: str, file: str) -> bool:
    """
    Move a file, creating destination directory if needed and overwriting if exists.

    Args:
        sourceDirectory: Source directory path
        destinationDirectory: Destination directory path
        file: Filename to move

    Returns:
        True if successful, False otherwise
    """
    createDirectory(destinationDirectory)
    src_path = os.path.join(sourceDirectory, file)
    dst_path = os.path.join(destinationDirectory, file)

    try:
        shutil.move(src_path, dst_path)
        return True
    except Exception:
        # Try removing destination and moving again
        try:
            os.remove(dst_path)
            shutil.move(src_path, dst_path)
            return True
        except Exception:
            return False


def moveFiles(sourceDirectory: str, destinationDirectory: str, files: List[str]) -> None:
    """Move multiple files."""
    for f in files:
        moveFile(sourceDirectory, destinationDirectory, f)


def forceMoveFiles(sourceDirectory: str, destinationDirectory: str, files: List[str]) -> None:
    """Force move multiple files."""
    for f in files:
        forceMoveFile(sourceDirectory, destinationDirectory, f)


def archiveFile(sourceDirectory: str, file: str) -> None:
    """
    Move a file to an 'archive' subdirectory.

    Args:
        sourceDirectory: Directory containing the file
        file: Filename to archive
    """
    destinationDirectory = os.path.join(sourceDirectory, 'archive')
    try:
        os.makedirs(destinationDirectory, exist_ok=True)
    except Exception:
        pass
    moveFile(sourceDirectory, destinationDirectory, file)


def forceArchiveFile(sourceDirectory: str, file: str) -> None:
    """Force archive a file (overwrite if exists)."""
    destinationDirectory = os.path.join(sourceDirectory, 'archive')
    try:
        os.makedirs(destinationDirectory, exist_ok=True)
    except Exception:
        pass
    forceMoveFile(sourceDirectory, destinationDirectory, file)


def archiveFiles(sourceDirectory: str, files: List[str]) -> None:
    """Archive multiple files."""
    destinationDirectory = os.path.join(sourceDirectory, 'archive')
    try:
        os.makedirs(destinationDirectory, exist_ok=True)
    except Exception:
        pass
    moveFiles(sourceDirectory, destinationDirectory, files)


def forceArchiveFiles(sourceDirectory: str, files: List[str]) -> None:
    """Force archive multiple files."""
    destinationDirectory = os.path.join(sourceDirectory, 'archive')
    try:
        os.makedirs(destinationDirectory, exist_ok=True)
    except Exception:
        pass
    forceMoveFiles(sourceDirectory, destinationDirectory, files)


def getFileNameForSaving(
    extension: str = 'png',
    useExtension: bool = True,
    useNanoSec: bool = False
) -> str:
    """
    Generate a timestamp-based filename for saving.

    Args:
        extension: File extension (must be in ALLOWED_EXTENSIONS)
        useExtension: Whether to include extension in filename
        useNanoSec: Whether to use microseconds instead of milliseconds

    Returns:
        Generated filename string
    """
    if extension not in ALLOWED_EXTENSIONS:
        extension = 'png'

    msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
    dt, ms = msTime.split('.')

    if useNanoSec:
        saveFile = f'{dt}-{int(ms)}'
    else:
        saveFile = f'{dt}-{int(ms) // 1000}'

    if useExtension:
        saveFile = f"{saveFile}.{extension}"

    return saveFile


def saveFile(img: Optional[np.ndarray], directory: str = "") -> bool:
    """
    Save an image to a directory with auto-generated filename.

    Args:
        img: NumPy array image to save
        directory: Directory path (relative to project root or absolute)

    Returns:
        True if successful, False otherwise
    """
    if img is None:
        return False

    if directory.startswith("/"):
        saveFolder = directory
    else:
        saveFolder = f"{get_project_root()}/{directory}"

    try:
        os.makedirs(os.path.dirname(saveFolder + '/sample.jpg'), exist_ok=True)
    except Exception:
        pass

    saveFileName = f"{saveFolder}/{getFileNameForSaving()}"

    try:
        cv2.imwrite(saveFileName, img)
        return True
    except Exception:
        return False


def saveFileWithFullPath(img: Optional[np.ndarray], filePath: str = "") -> bool:
    """
    Save an image to a specific file path.

    Args:
        img: NumPy array image to save
        filePath: Full path including filename

    Returns:
        True if successful, False otherwise
    """
    if img is None or not isinstance(img, np.ndarray):
        return False

    if not filePath:
        return False

    saveDir = os.path.split(filePath)[0]
    try:
        os.makedirs(saveDir, exist_ok=True)
    except Exception as e:
        printBoldRed(f"Could not make directory because of {e}")
        return False

    try:
        cv2.imwrite(filePath, img)
        return True
    except Exception as e1:
        printBoldRed(f"Could not save image because of {e1}")
        return False


def createDirectory(sourceDirectory: str) -> bool:
    """
    Create a directory (and parent directories if needed).

    Args:
        sourceDirectory: Path to create. Should end with '/' for directories,
                        or be a path to a file (directory will be created).

    Returns:
        True if successful, False otherwise
    """
    if not sourceDirectory:
        return False

    try:
        if sourceDirectory.endswith("/"):
            targetDirectory = sourceDirectory[:-1]
            os.makedirs(targetDirectory, exist_ok=True)
            return True

        parts = os.path.split(sourceDirectory)
        destinationDirectory = parts[0]

        if not destinationDirectory.startswith("/") and ":/" not in destinationDirectory:
            destinationDirectory = get_project_root() + "/" + destinationDirectory

        if not destinationDirectory.endswith("/"):
            destinationDirectory += "/"

        # If the second part has no extension, treat it as a directory
        if "." not in parts[1]:
            destinationDirectory = destinationDirectory + parts[1] + "/"

        os.makedirs(destinationDirectory, exist_ok=True)
        return True

    except Exception as e:
        printBoldRed(e)
        return False


def write_stringio_to_csv(stringio: StringIO, file_path: str) -> bool:
    """
    Write the contents of a StringIO object containing CSV data to a file.

    Args:
        stringio: StringIO object with CSV data
        file_path: Path to the output CSV file

    Returns:
        True if writing succeeds, False otherwise

    Raises:
        ValueError: If inputs are invalid
        IOError: If file writing fails
    """
    # Validate inputs
    if not isinstance(stringio, StringIO):
        raise ValueError("Input must be a StringIO object")
    if not file_path or not isinstance(file_path, str):
        raise ValueError("File path must be a non-empty string")

    try:
        # Ensure directory exists
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Get StringIO content
        csv_content = stringio.getvalue()

        # Write to file with UTF-8 encoding
        with open(file_path, mode='w', encoding='utf-8', newline='') as f:
            f.write(csv_content)

        print(f"Successfully wrote CSV to {file_path}")
        return True

    except (IOError, OSError) as e:
        print(f"File error: {e}")
        raise IOError(f"Failed to write CSV to {file_path}: {e}")
    except ValueError as e:
        print(f"Input error: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise Exception(f"Unexpected error: {e}")
