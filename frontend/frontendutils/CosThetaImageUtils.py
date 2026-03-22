# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

import re
from typing import Union

import cv2
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, QRectF, QRect, QDir
from PySide6.QtGui import QFontMetrics, QPainterPath, QColor, QPixmap, QImage, QPainter, QBrush, Qt, QPen, QFont
import cv2
import numpy as np
from numpy import ndarray
import qimage2ndarray
from PySide6 import QtGui

from frontend import CosThetaMonitorDimensions
from utils.CosThetaFileUtils import *

monitorWidth = CosThetaMonitorDimensions.monitorWidth
monitorHeight = CosThetaMonitorDimensions.monitorHeight

# def tearDown():
#     del app
#     return super().tearDown()

# Convert an opencv startingImage to QPixmap
def convertCvImage2QtImage(cv_img):
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    PIL_image = Image.fromarray(rgb_image).convert('RGB')
    # return QPixmap.fromImage(ImageQt(PIL_image))
    return ImageQt(PIL_image)


def convert_Cvimage_to_QPixmap(self, img):
    w, h, ch = img.shape
    # Convert resulting startingImage to pixmap
    if img.ndim == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    qimg = QImage(img.data, h, w, 3 * h, QImage.Format.Format_RGB888)
    qpixmap = QPixmap(qimg)
    return qpixmap


def createImage(text="Leer", imageDimensions=((monitorWidth - 25) / 4, (monitorHeight - 25) / 4),
                fontColor: Union[QColor, Qt.GlobalColor] = QColor(64, 176, 64), replaceChar=[' ', ' '],
                backgroundColor: Union[QColor, Qt.GlobalColor] = QColor(206, 206, 206), forceUseOfFontSizeAs: int = 0):
    # printPlain(f"imageDimensions are {imageDimensions}")
    # printBoldRed(f"Create Image called")
    # To ensure better
    text = text.strip()
    if len(text) == 0:
        width = imageDimensions[0]
        height = imageDimensions[1]
        backgroundColor = backgroundColor
        image = QImage(QSize(width, height), QImage.Format.Format_BGR888)
        painter = QPainter(image)
        painter.setBrush(QBrush(backgroundColor))
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        cornerRadius = 5
        imageRect = QRectF(0, 0, imageDimensions[0], imageDimensions[1])
        painter.fillRect(imageRect, Qt.GlobalColor.black)
        imageRect.adjust(cornerRadius / 2 + 1, cornerRadius / 2 + 1, -cornerRadius / 2 - 1, -cornerRadius / 2 - 1)
        # printPlain(f"After adjustment, imageRect is {imageRect}")
        path.addRoundedRect(imageRect, cornerRadius, cornerRadius)
        painter.setPen(QPen(backgroundColor, cornerRadius))
        painter.setClipPath(path)
        painter.strokePath(path, painter.pen())
        painter.fillPath(path, painter.brush())
        painter.setPen(QPen(fontColor))
        painter.end()
        # path = "/Temp/Output"
        # imageName = text + ".png"
        # aDir = QDir(path)
        # if (aDir.mkpath(path)):
        #     startingImage.save(path + "/" + imageName)
        # else:
        #     startingImage.save(imageName)
        return image
    else:
        textSplit = re.split('[ -]', text)  # split the text at spaces and '-'
        for i in range(len(textSplit)):
            aWord = textSplit[i]
            newWord = aWord.replace('\b', ' ')
            newWord = newWord.replace(replaceChar[0], replaceChar[1])
            textSplit[i] = newWord
        text = ' '.join([str(item) for item in textSplit])
        # print(f"{textSplit = }")
        # print(f"{text = }")
        # printPlain(f"Entered with startingImage dimensions {imageDimensions}")
        width = imageDimensions[0]
        height = imageDimensions[1]
        backgroundColor = backgroundColor
        image = QImage(QSize(width, height), QImage.Format.Format_BGR888)
        # image = QImage(QSize(width, height), QImage.Format_BGR888)
        painter = QPainter(image)
        painter.setBrush(QBrush(backgroundColor))
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        cornerRadius = 5
        imageRect = QRectF(0, 0, imageDimensions[0], imageDimensions[1])
        painter.fillRect(imageRect, Qt.GlobalColor.black)
        imageRect.adjust(cornerRadius / 2 + 1, cornerRadius / 2 + 1, -cornerRadius / 2 - 1, -cornerRadius / 2 - 1)
        # printPlain(f"After adjustment, imageRect is {imageRect}")
        path.addRoundedRect(imageRect, cornerRadius, cornerRadius)
        painter.setPen(QPen(backgroundColor, cornerRadius))
        painter.setClipPath(path)
        painter.strokePath(path, painter.pen())
        painter.fillPath(path, painter.brush())
        painter.setPen(QPen(fontColor))
        # printPlain("Reached here")
        fontSize = 12
        font = QFont("Courier", fontSize)
        font.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(font)
        # printPlain(f"Reached here with text as {text}")
        nRows = len(textSplit)
        pixelGapBetweenRows = 10
        adjustedHeight = (imageRect.height() - (nRows - 1) * pixelGapBetweenRows) / nRows
        maxLength = 0
        maxWord = ' '
        for i in range(nRows):
            maxLength = max(maxLength, len(textSplit[i]))
            if maxLength == len(textSplit[i]):
                maxWord = textSplit[i]
        if maxWord == "":
            maxWord = " "
        # printBoldGreen(f"Finding dimensions for word {maxWord}")
        if forceUseOfFontSizeAs == 0:
            textRect = metrics.boundingRect(0, 0, 0, 0,
                                            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                            maxWord)
            # textRect = metrics.boundingRect(0, 0, 0, 0,
            #                                 Qt.AlignmentFlag.AlignCenter,
            #                                 maxWord)
            textWidth = textRect.width()
            textHeight = textRect.height()
            # printPlain(f"Reached here with textRect as {textRect}, width as {textWidth}, height as {textHeight}")
            # printPlain(f"Compare that with width as {metrics.lineWidth(text)}, height as {metrics.height(text)}")
            # printPlain("Reached here")
            # printPlain(textWidth, textHeight)
            reductionFactor = min(width * 1.0 / textWidth, adjustedHeight * 1.0 / textHeight) * 0.85
            # printPlain(reductionFactor)
            # reductionFactor = max(1.0, reductionFactor)
            fontSize = int(reductionFactor * fontSize)
            # printPlain(fontSize)
            font.setPointSize(fontSize)
            # print(f"For {text}, set font size as {fontSize}")
        else:
            font.setPointSize(forceUseOfFontSizeAs)
            # print(f"For {text}, set font size as {forceUseOfFontSizeAs}")
        # font = QFont("Courier", fontSize)
        # font.setWeight(QFont.Weight.Black)
        painter.setFont(font)
        # print(f"{font.weight()}, {font.family()}, {font.pointSize()}")
        metrics = QFontMetrics(font)
        wordHeight = metrics.boundingRect(0, 0, 0, 0,
                                          Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                          maxWord).height()
        # wordHeight = metrics.boundingRect(0, 0, 0, 0,
        #                                   Qt.AlignmentFlag.AlignCenter,
        #                                   maxWord).height()
        # printPlain(f"Word height is {wordHeight}")
        yCoords = []

        for i in range(nRows):
            yCoord_i = imageDimensions[1] // 2 - (nRows / 2 * wordHeight) - int(
                nRows / 2) * pixelGapBetweenRows + i * wordHeight + i * pixelGapBetweenRows
            yCoords.append(yCoord_i)
        # printPlain(f"yCoords are {yCoords}")

        for i in range(nRows):
            currentWord = textSplit[i]
            textRect = metrics.boundingRect(0, 0, 0, 0,
                                            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextExpandTabs,
                                            currentWord)
            # textRect = metrics.boundingRect(0, 0, 0, 0,
            #                                 Qt.AlignmentFlag.AlignCenter,
            #                                 currentWord)
            # printPlain(f"Now textRect is {textRect}")
            textWidth = textRect.width()
            textHeight = textRect.height()
            # printPlain(textWidth, textHeight)
            topLeftX = (imageDimensions[0] // 2 - textWidth // 2) + 1
            topLeftY = yCoords[i]
            # printPlain(f"printing {currentWord} at {topLeftX}, {topLeftY}")
            fontRect = QRect(topLeftX, topLeftY, textWidth, textHeight)
            # painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            # painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.drawText(fontRect, currentWord)
        # del painter
        # del font
        painter.end()
        # path = "/Temp/Output"
        # imageName = text + ".png"
        # aDir = QDir(path)
        # if (aDir.mkpath(path)):
        #     image.save(path + "/" + imageName)
        # else:
        #     image.save(imageName)
    return image

def createGreenImage(text="Leer", imageDimensions=(315, 180)):
    return createImage(text=text, imageDimensions=imageDimensions, fontColor=Qt.GlobalColor.darkGreen)


def createRedImage(text="Leer", imageDimensions=(315, 180)):
    return createImage(text=text, imageDimensions=imageDimensions, fontColor=Qt.GlobalColor.red)


def createBlueImage(text="Leer", imageDimensions=(315, 180)):
    return createImage(text=text, imageDimensions=imageDimensions, fontColor=Qt.GlobalColor.darkBlue)

def createImageAlternateViaCV2(
        text : str ="Sample\bImage\b and Display",
        imageDimensions=((monitorWidth - 25) / 4, (monitorHeight - 25) / 4),
        fontColor : tuple = (0, 0, 128),
        backgroundColor : tuple = (206, 206, 206),
        forceUseOfFontSizeAs : int = 0,
        replaceChar : list =('-', ' '),  # Default replacement for '-' to ' '
        margin : int = 20,
        returnPixMapImage : bool = False
):
    # Create background image with margins
    # rgbBackgroundColor = (206, 206, 206)
    # rgbBackgroundColor = (225, 220, 245),
    width = imageDimensions[0]
    height = imageDimensions[1]
    if width < 50:
        width = 50
    if height < 50:
        height = 50
    inner_width = width - 2 * margin
    inner_height = height - 2 * margin
    image = np.ones((height, width, 3), dtype=np.uint8)
    image[:] = backgroundColor[::-1]  # Convert RGB to BGR

    # Handle empty text
    text = text.strip()
    if len(text) == 0:
        if not returnPixMapImage:
            return image
        else:
            cv2_image_to_qpixmap(image)

    font_thickness : int = 1
    # Split text into lines using the new logic
    textSplit = re.split('[ -]', text)  # Split at spaces and hyphens
    for i in range(len(textSplit)):
        aWord = textSplit[i]
        newWord = aWord.replace('\b', ' ')
        newWord = newWord.replace(replaceChar[0], replaceChar[1])
        textSplit[i] = newWord
    lines = [' '.join(textSplit)]  # Join all split parts into a single line for now; adjust based on intent

    # If multi-line intent is desired, assume textSplit represents lines directly
    # For now, we'll treat textSplit as potential lines and filter out empty strings
    lines = [line for line in textSplit if line.strip()]
    n_lines = len(lines)

    font = cv2.FONT_HERSHEY_DUPLEX

    def get_text_size(text_str, font_scale):
        (text_width, text_height), baseline = cv2.getTextSize(text_str, font, font_scale, thickness=font_thickness)
        return text_width, text_height, baseline

    # Determine font scale and positioning
    if forceUseOfFontSizeAs == 0:
        # Optimize font scale for forcedFontSize > 0
        test_scale = 0.5
        maxWidth = 0
        totalHeight = 0
        for i, line in enumerate(textSplit):
            w, h, _ = get_text_size(line, test_scale)
            maxWidth = max(maxWidth, w)
            totalHeight += h
            if i > 0:
                totalHeight += 10

        widthRatio = inner_width * 1.0 / maxWidth
        heightRatio = inner_height * 1.0 / totalHeight
        minRatio = min(widthRatio, heightRatio)
        best_scale = test_scale * minRatio * 0.95
        font_scale = best_scale
    else:
        # Use a default reasonable font scale without optimization
        font_scale = forceUseOfFontSizeAs / 20.0  # Default scale, can be adjusted manually

    print(f"Font scale for {text} is {font_scale}")
    # Calculate dimensions for centering
    line_heights = []
    line_widths = []
    for line in lines:
        w, h, _ = get_text_size(line, font_scale)
        line_widths.append(w)
        line_heights.append(h)
    total_text_height = sum(line_heights) + (n_lines - 1) * 10
    max_line_width = max(line_widths)

    # Starting positions with margins
    start_y = margin + (inner_height - total_text_height) // 2
    y_current = start_y

    for i, line in enumerate(lines):
        w, h, baseline = get_text_size(line, font_scale)
        x = margin + (inner_width - w) // 2  # Center each line individually within available width
        y = int(y_current + h)
        cv2.putText(
            image,
            line,
            (x, y),
            font,
            font_scale,
            fontColor[::-1],  # BGR
            thickness=font_thickness,
            lineType=cv2.LINE_AA
        )
        y_current += h + 10  # Move to next line

    if not returnPixMapImage:
        return image
    else:
        return cv2_image_to_qpixmap(image)


def cv2_image_to_qpixmap(cv2_image : np.ndarray | None):
    """
    Convert an OpenCV image (NumPy array) to a QPixmap.

    Args:
        cv2_image (np.ndarray): OpenCV image in BGR format (height, width, 3).

    Returns:
        QPixmap: Converted QPixmap object.
    """
    # Convert BGR to RGB

    if cv2_image is None:
        return None

    rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)

    # Get image dimensions
    height, width, channel = rgb_image.shape
    bytes_per_line = 3 * width  # 3 channels (RGB)

    # Create QImage from NumPy array
    q_image = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

    # Convert QImage to QPixmap
    pixmap = QPixmap.fromImage(q_image)

    return pixmap


def getPixmapImage(image : QImage | QPixmap | ndarray | str):
    if isinstance(image, QImage):
        return QPixmap.fromImage(image)
    if isinstance(image, QPixmap):
        return image
    if isinstance(image, str):
        if os.path.exists(image):
            return QPixmap(image)  # filename
        else:
            pixmap = QPixmap(10, 10)
            pixmap.fill(QColor("white"))
            return pixmap
    if isinstance(image, ndarray):
        try:
            imageData = image.data
        except Exception:
            try:
                imageData = image.tobytes()
            except:
                try:
                    imageData = np.require(image, np.uint8, 'C')
                except:
                    imageData = image

        height, width, channel = image.shape
        bytesPerLine = 3 * width
        img = QImage(imageData, width, height, bytesPerLine, QImage.Format.Format_BGR888)
        # img = QImage(startingImage, startingImage.shape[0], startingImage.shape[1], QImage.Format_BGR888)
        # return QPixmap.fromImage(qimage2ndarray.array2qimage(startingImage))
        return QPixmap.fromImage(img)
    return None

def resize_pixmap(pixmap : QPixmap, width : int, height : int, keepAspectRatio : bool = False):
    """Resizes a QPixmap to a specific width and height, optionally preserving aspect ratio."""
    if keepAspectRatio:
        return pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    else:
        return pixmap.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

def convertQImageToNumpy(incomingImage):
    """  Converts a QImage into an opencv MAT format  """

    # incomingImage = incomingImage.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    incomingImage = incomingImage.convertToFormat(QtGui.QImage.Format.Format_RGB32)

    width = incomingImage.width()
    height = incomingImage.height()

    ptr = incomingImage.constBits()
    arr = np.array(ptr).reshape(height, width, 4)  # Copies the data
    return arr


def convertNDArrayToPixmap(ndarray):
    # Assumption is that incoming ndarray is in RGB32 format
    h, w = ndarray.shape[:2]
    qimg_format = QImage.Format.Format_BGR888 if len(ndarray.shape) == 3 else QImage.Format.Format_Indexed8
    qimg = QImage(ndarray.flatten(), w, h, qimg_format)
    # qimg = QImage(ndarray.data, h, w, 3 * h, QImage.Format_BGR888)
    qpixmap = QPixmap(qimg)
    return qpixmap

# if __name__ == '__main__':
#     win = ControlBar()
#     win.show()
#     win.raise_()
#     sys.exit(app.exec())

def showImageWithRGBValues(window_name: str, image : np.ndarray, numberOfStitchedImagesInXDirection : int = 1, numberOfStitchedImagesInYDirection : int = 1):
    """Displays an image and shows RGB values on mouse hover."""
    if image is None:
        # print("Error: Could not load image.")
        return

    shape_len = len(image.shape)
    width = image.shape[1]
    height = image.shape[0]

    eachImageWidth = image.shape[1] // numberOfStitchedImagesInXDirection
    eachImageHeight = image.shape[0] // numberOfStitchedImagesInYDirection
    # print(width, height)

    def mouse_callback(event, x, y, flags, param):
        x1 = x % eachImageWidth
        y1 = y % eachImageHeight
        # print(x1, y1)
        if event == cv2.EVENT_MOUSEMOVE:
            if 0 <= x < width and 0 <= y < height:
                if shape_len == 3:
                    b, g, r = image[y, x]  # Get RGB values at (x,y)
                    rgb_str = f"[{width}, {height}] - [{x1}, {y1}] - RGB: ({r}, {g}, {b})"
                    cv2.setWindowTitle(winname=window_name, title=rgb_str)  # Update window title
                elif shape_len == 2:
                    gray_value = image[y, x]  # Get pixel values at (x,y)
                    rgb_str = f"[{width}, {height}] - [{x1}, {y1}] - {gray_value}"  # Corrected formatting here
                    cv2.setWindowTitle(winname=window_name, title=rgb_str)  # Update window title

    cv2.namedWindow(winname=window_name)
    cv2.imshow(winname=window_name, mat=image)
    cv2.setMouseCallback(window_name, mouse_callback)

def create_elliptical_kernel(rows, cols):
    """Creates an elliptical kernel using a circular kernel and a mask.

    Args:
        rows: The number of rows in the kernel.
        cols: The number of columns in the kernel.

    Returns:
        The elliptical kernel (NumPy array), or None if an error occurs.  Returns None if rows or cols are not positive integers.
    """
    if not isinstance(rows, int) or not isinstance(cols, int) or rows <=0 or cols <= 0:
        print("Error: rows and cols must be positive integers.")
        return None

    center_row, center_col = rows // 2, cols // 2
    radius = min(center_row, center_col) # Radius is half the smaller dimension

    # Create a circular kernel
    circular_kernel = np.zeros((rows, cols), dtype=np.uint8)
    for i in range(rows):
        for j in range(cols):
            if (i - center_row)**2 + (j - center_col)**2 <= radius**2:
                circular_kernel[i, j] = 1


    # Create an elliptical mask (adjust eccentricity as needed)
    elliptical_mask = np.zeros((rows, cols), dtype=np.uint8)
    for i in range(rows):
        for j in range(cols):
            #Adjust eccentricity here
            if ( (i - center_row)**2 / (radius**2) ) + ( (j - center_col)**2 / ( (radius * 0.5)**2 ) ) <= 1: #Eccentricity = 0.5
                elliptical_mask[i,j] = 1


    # Apply the mask to the circular kernel
    elliptical_kernel = circular_kernel * elliptical_mask

    return elliptical_kernel

# image = cv2.imread("C:/Temp/TrialImages/Left Disc/2024-12-05-18-49-56-765.png")  #replace with your image path
# showImageWithRGBValues("My Image Window", image)  # window_name is explicitly passed
# cv2.waitKey(0)
# cv2.destroyAllWindows()
