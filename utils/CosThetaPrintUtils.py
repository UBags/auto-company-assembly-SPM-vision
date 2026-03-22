# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

# """
# Print utilities for coloured and formatted console output.
#
# These functions write directly to stdout/stderr and are intentionally
# independent of the Redis-based logging pipeline — they are safe to call
# before the logging infrastructure is initialised and inside the loggers
# themselves without causing circular dependencies.
# """
# from datetime import datetime
# from typing import Any
#
#
# def getCurrentTime() -> str:
#     """
#     Return the current wall-clock time as a formatted string with milliseconds.
#
#     Format: ``YYYY-MM-DD-HH-MM-SS-mmm``
#     """
#     msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
#     dt, ms = msTime.split('.')
#     ms_int = int(ms) // 1000
#     return f'{dt}-{ms_int:03}'
#
#
# def printWithTime(*args: Any) -> None:
#     """Print with a ``getCurrentTime()`` prefix (no trailing newline added)."""
#     print(f'{getCurrentTime()} : ', *args, end="")
#
#
# # ── colour / style helpers ────────────────────────────────────────────────────
# # Import CosThetaColors lazily so this module has zero mandatory dependencies.
#
# def _colors():
#     from utils.CosThetaColors import CosThetaColors
#     return CosThetaColors
#
#
# def printRed(*args: Any, includeTime: bool = True) -> None:
#     """Print in red."""
#     c = _colors()
#     print(c.CRED, end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBoldRed(*args: Any, includeTime: bool = True) -> None:
#     """Print in bold red."""
#     c = _colors()
#     print(c.CRED, c.CBOLD, sep="", end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printGreen(*args: Any, includeTime: bool = True) -> None:
#     """Print in green."""
#     c = _colors()
#     print(c.CGREEN, end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBoldGreen(*args: Any, includeTime: bool = True) -> None:
#     """Print in bold green."""
#     c = _colors()
#     print(c.CGREEN, c.CBOLD, sep="", end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBlue(*args: Any, includeTime: bool = True) -> None:
#     """Print in blue."""
#     c = _colors()
#     print(c.CBLUE, end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBoldBlue(*args: Any, includeTime: bool = True) -> None:
#     """Print in bold blue."""
#     c = _colors()
#     print(c.CBLUE, c.CBOLD, sep="", end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printYellow(*args: Any, includeTime: bool = True) -> None:
#     """Print in yellow."""
#     c = _colors()
#     print(c.CYELLOW, end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBoldYellow(*args: Any, includeTime: bool = True) -> None:
#     """Print in bold yellow."""
#     c = _colors()
#     print(c.CYELLOW, c.CBOLD, sep="", end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBold(*args: Any, includeTime: bool = True) -> None:
#     """Print in bold black."""
#     c = _colors()
#     print(c.CBLACK, c.CBOLD, sep="", end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printPlain(*args: Any, includeTime: bool = True) -> None:
#     """Print in plain black."""
#     c = _colors()
#     print(c.CBLACK, end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printLight(*args: Any, includeTime: bool = True) -> None:
#     """Print in grey (dim)."""
#     c = _colors()
#     print(c.CGREY, end="")
#     printWithTime(*args) if includeTime else print(*args, end="")
#     print(c.CEND)
#
#
# def printBoldSeparator() -> None:
#     """Print a bold separator line."""
#     c = _colors()
#     print(c.CBLACK, c.CBOLD, sep="", end="")
#     print('------------------------------------------------------------------------')
#     print(c.CEND)
#
#
# def printSeparator() -> None:
#     """Print a plain separator line."""
#     c = _colors()
#     print(c.CBLACK, end="")
#     print('------------------------------------------------------------------------')
#     print(c.CEND)
#
#
# def printInColor(message: str, messageType: int) -> None:
#     """
#     Print ``message`` in a colour determined by ``messageType``.
#
#     ``messageType`` must be a ``MessageType`` integer value:
#         1 = GENERAL  → grey
#         2 = SUCCESS  → bold green
#         3 = RISK     → bold yellow
#         4 = ISSUE    → bold red
#         5 = PROBLEM  → bold red
#
#     The MessageType import is deferred to avoid a circular import with
#     the logger infrastructure.
#     """
#     # Deferred import to break the circular dependency
#     from logutils.Logger import MessageType
#
#     dispatch = {
#         int(MessageType.GENERAL): printLight,
#         int(MessageType.SUCCESS): printBoldGreen,
#         int(MessageType.RISK):    printBoldYellow,
#         int(MessageType.ISSUE):   printBoldRed,
#         int(MessageType.PROBLEM): printBoldRed,
#     }
#     printer = dispatch.get(messageType, printBold)
#     printer(message, includeTime=False)

"""
Print utilities for coloured and formatted console output.

These functions write directly to stdout/stderr and are intentionally
independent of the Redis-based logging pipeline — they are safe to call
before the logging infrastructure is initialised and inside the loggers
themselves without causing circular dependencies.
"""
from datetime import datetime
from typing import Any


def getCurrentTime() -> str:
    """
    Return the current wall-clock time as a formatted string with milliseconds.

    Format: ``YYYY-MM-DD-HH-MM-SS-mmm``
    """
    msTime = datetime.now().strftime('%Y-%m-%d-%H-%M-%S.%f')
    dt, ms = msTime.split('.')
    ms_int = int(ms) // 1000
    return f'{dt}-{ms_int:03}'


def printWithTime(*args: Any) -> None:
    """Print with a ``getCurrentTime()`` prefix (no trailing newline added)."""
    print(f'{getCurrentTime()} : ', *args, end="")


# ── colour / style helpers ────────────────────────────────────────────────────
# Import CosThetaColors lazily so this module has zero mandatory dependencies.

def _colors():
    from utils.CosThetaColors import CosThetaColors
    return CosThetaColors

c = _colors()

def printRed(*args: Any, includeTime: bool = True) -> None:
    """Print in red."""
    print(c.CRED, end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)


def printBoldRed(*args: Any, includeTime: bool = True) -> None:
    """Print in bold red."""
    print(c.CRED, c.CBOLD, sep="", end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printGreen(*args: Any, includeTime: bool = True) -> None:
    """Print in green."""
    print(c.CGREEN, end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printBoldGreen(*args: Any, includeTime: bool = True) -> None:
    """Print in bold green."""
    print(c.CGREEN, c.CBOLD, sep="", end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printBlue(*args: Any, includeTime: bool = True) -> None:
    """Print in blue."""
    print(c.CBLUE, end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printBoldBlue(*args: Any, includeTime: bool = True) -> None:
    """Print in bold blue."""
    print(c.CBLUE, c.CBOLD, sep="", end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printYellow(*args: Any, includeTime: bool = True) -> None:
    """Print in yellow."""
    print(c.CYELLOW, end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printBoldYellow(*args: Any, includeTime: bool = True) -> None:
    """Print in bold yellow."""
    print(c.CYELLOW, c.CBOLD, sep="", end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printBold(*args: Any, includeTime: bool = True) -> None:
    """Print in bold black."""
    print(c.CBLACK, c.CBOLD, sep="", end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printPlain(*args: Any, includeTime: bool = True) -> None:
    """Print in plain black."""
    print(c.CBLACK, end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printLight(*args: Any, includeTime: bool = True) -> None:
    """Print in grey (dim)."""
    print(c.CGREY, end="")
    printWithTime(*args) if includeTime else print(*args, end="")
    print(c.CEND)

def printBoldSeparator() -> None:
    """Print a bold separator line."""
    print(c.CBLACK, c.CBOLD, sep="", end="")
    print('------------------------------------------------------------------------')
    print(c.CEND)

def printSeparator() -> None:
    """Print a plain separator line."""
    print(c.CBLACK, end="")
    print('------------------------------------------------------------------------')
    print(c.CEND)

def printInColor(message: str, messageType: int) -> None:
    """
    Print ``message`` in a colour determined by ``messageType``.

    ``messageType`` must be a ``MessageType`` integer value:
        1 = GENERAL  → grey
        2 = SUCCESS  → bold green
        3 = RISK     → bold yellow
        4 = ISSUE    → bold red
        5 = PROBLEM  → bold red

    The MessageType import is deferred to avoid a circular import with
    the logger infrastructure.

    Colour start, message text, and reset are emitted in a single print()
    call to guarantee they are never separated by interleaved output from
    other threads or processes writing to the same terminal.
    """
    # Deferred import to break the circular dependency
    from logutils.Logger import MessageType

    c = _colors()

    dispatch = {
        int(MessageType.GENERAL): c.CGREY,
        int(MessageType.SUCCESS): c.CGREEN + c.CBOLD,
        int(MessageType.RISK):    c.CYELLOW + c.CBOLD,
        int(MessageType.ISSUE):   c.CRED + c.CBOLD,
        int(MessageType.PROBLEM): c.CRED + c.CBOLD,
    }
    colour = dispatch.get(messageType, c.CBLACK + c.CBOLD)
    print(f"{colour}{message}{c.CEND}", flush=True)
