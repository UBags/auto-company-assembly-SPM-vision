# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
ANSI escape codes for terminal text formatting and colors.
"""


class CosThetaColors:
    """
    Collection of ANSI escape codes for terminal text styling.

    Usage:
        print(f"{CosThetaColors.CRED}Red text{CosThetaColors.CEND}")
        print(f"{CosThetaColors.CBOLD}{CosThetaColors.CGREEN}Bold green{CosThetaColors.CEND}")
    """

    # Text styles
    CEND: str = '\33[0m'  # Reset all attributes
    CBOLD: str = '\33[1m'  # Bold/bright
    CITALIC: str = '\33[3m'  # Italic
    CURL: str = '\33[4m'  # Underline
    CBLINK: str = '\33[5m'  # Slow blink
    CBLINK2: str = '\33[6m'  # Fast blink
    CSELECTED: str = '\33[7m'  # Reverse video

    # Standard foreground colors
    CBLACK: str = '\33[30m'
    CRED: str = '\33[31m'
    CGREEN: str = '\33[32m'
    CYELLOW: str = '\33[33m'
    CBLUE: str = '\33[34m'
    CVIOLET: str = '\33[35m'
    CBEIGE: str = '\33[36m'  # Cyan
    CWHITE: str = '\33[37m'

    # Standard background colors
    CBLACKBG: str = '\33[40m'
    CREDBG: str = '\33[41m'
    CGREENBG: str = '\33[42m'
    CYELLOWBG: str = '\33[43m'
    CBLUEBG: str = '\33[44m'
    CVIOLETBG: str = '\33[45m'
    CBEIGEBG: str = '\33[46m'
    CWHITEBG: str = '\33[47m'

    # Bright/high-intensity foreground colors
    CGREY: str = '\33[90m'
    CRED2: str = '\33[91m'
    CGREEN2: str = '\33[92m'
    CYELLOW2: str = '\33[93m'
    CBLUE2: str = '\33[94m'
    CVIOLET2: str = '\33[95m'
    CBEIGE2: str = '\33[96m'
    CWHITE2: str = '\33[97m'

    # Bright/high-intensity background colors
    CGREYBG: str = '\33[100m'
    CREDBG2: str = '\33[101m'
    CGREENBG2: str = '\33[102m'
    CYELLOWBG2: str = '\33[103m'
    CBLUEBG2: str = '\33[104m'
    CVIOLETBG2: str = '\33[105m'
    CBEIGEBG2: str = '\33[106m'
    CWHITEBG2: str = '\33[107m'
