# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
QR Code parsing utilities for extracting model and tonnage information.
"""
import copy
from typing import Tuple, Dict, Optional

from Configuration import *

CosThetaConfigurator.getInstance()

# Get QR code pattern mappings from configuration
_partMappings: Dict[str, str] = CosThetaConfigurator.getQRCodePartMappingPatterns()

UNKNOWN: str = "UNKNOWN"


def getModel_LHSRHS_AndTonnage(qrCode: Optional[str]) -> Tuple[str, str, str]:
    """
    Extract model name, LHS/RHS designation, and tonnage from a QR code.

    The QR code is matched against configured prefix patterns to determine
    the component information.

    Args:
        qrCode: The QR code string to parse

    Returns:
        Tuple of (modelName, lhs_rhs, tonnage).
        Returns (UNKNOWN, UNKNOWN, UNKNOWN) if QR code is invalid or not matched.

    Example:
        >>> getModel_LHSRHS_AndTonnage("ABC123456")
        ('ModelX', 'LHS', '5T')
    """
    if not qrCode:
        return (UNKNOWN, UNKNOWN, UNKNOWN)

    copyOfQRCode = copy.deepcopy(qrCode)

    for key, value in _partMappings.items():
        if copyOfQRCode.startswith(key):
            try:
                tempValue: str = str(value)
                partsOfTempValue = tempValue.split("-")

                if len(partsOfTempValue) < 3:
                    continue

                model: str = f"{partsOfTempValue[0].strip()}-{partsOfTempValue[1].strip()}"
                modelParts = model.strip().split('-')

                modelName = modelParts[0] if len(modelParts) > 0 else UNKNOWN
                lhs_rhs = modelParts[1] if len(modelParts) > 1 else UNKNOWN
                tonnage: str = partsOfTempValue[2].strip()

                return (modelName, lhs_rhs, tonnage)

            except (IndexError, AttributeError, ValueError):
                continue

    return (UNKNOWN, UNKNOWN, UNKNOWN)


def parseQRCode(qrCode: Optional[str]) -> Dict[str, str]:
    """
    Parse a QR code and return component information as a dictionary.

    Args:
        qrCode: The QR code string to parse

    Returns:
        Dictionary with keys: 'model', 'side', 'tonnage', 'valid'
    """
    model, side, tonnage = getModel_LHSRHS_AndTonnage(qrCode)

    return {
        'model': model,
        'side': side,
        'tonnage': tonnage,
        'valid': model != UNKNOWN and side != UNKNOWN and tonnage != UNKNOWN
    }


def isValidQRCode(qrCode: Optional[str]) -> bool:
    """
    Check if a QR code is valid (matches a known pattern).

    Args:
        qrCode: The QR code string to validate

    Returns:
        True if QR code matches a known pattern, False otherwise
    """
    model, side, tonnage = getModel_LHSRHS_AndTonnage(qrCode)
    return model != UNKNOWN and side != UNKNOWN and tonnage != UNKNOWN


def refreshPartMappings() -> None:
    """
    Refresh the part mappings from configuration.

    Call this if the configuration has been updated and you need
    to reload the QR code pattern mappings.
    """
    global _partMappings
    _partMappings = CosThetaConfigurator.getQRCodePartMappingPatterns()
