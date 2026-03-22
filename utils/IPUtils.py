# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
IP/Network utilities for checking host connectivity.
"""
from icmplib import ping
from icmplib.exceptions import NameLookupError


def checkIP(hostname: str, count: int = 8, interval: float = 0.2, timeout: int = 1) -> bool:
    """
    Check if a host is reachable via ICMP ping.

    Args:
        hostname: IP address or hostname to check
        count: Number of ping packets to send
        interval: Time between packets in seconds
        timeout: Timeout for each packet in seconds

    Returns:
        True if at least one packet was received, False otherwise
    """
    if not hostname:
        return False

    try:
        host = ping(
            hostname,
            count=count,
            interval=interval,
            timeout=timeout,
            privileged=False
        )
        return host.packets_received > 0

    except NameLookupError:
        return False
    except Exception:
        return False


def isHostReachable(hostname: str) -> bool:
    """
    Alias for checkIP() with default parameters.

    Args:
        hostname: IP address or hostname to check

    Returns:
        True if host is reachable, False otherwise
    """
    return checkIP(hostname)


def checkIPWithStats(hostname: str, count: int = 8) -> dict:
    """
    Check host connectivity and return detailed statistics.

    Args:
        hostname: IP address or hostname to check
        count: Number of ping packets to send

    Returns:
        Dictionary with ping statistics:
        - 'reachable': bool
        - 'packets_sent': int
        - 'packets_received': int
        - 'packet_loss': float (percentage)
        - 'avg_rtt': float (milliseconds, or None if not reachable)
        - 'min_rtt': float (milliseconds, or None if not reachable)
        - 'max_rtt': float (milliseconds, or None if not reachable)
    """
    result = {
        'reachable': False,
        'packets_sent': 0,
        'packets_received': 0,
        'packet_loss': 100.0,
        'avg_rtt': None,
        'min_rtt': None,
        'max_rtt': None,
    }

    if not hostname:
        return result

    try:
        host = ping(
            hostname,
            count=count,
            interval=0.2,
            timeout=1,
            privileged=False
        )

        result['packets_sent'] = host.packets_sent
        result['packets_received'] = host.packets_received
        result['packet_loss'] = host.packet_loss * 100
        result['reachable'] = host.packets_received > 0

        if result['reachable']:
            result['avg_rtt'] = host.avg_rtt
            result['min_rtt'] = host.min_rtt
            result['max_rtt'] = host.max_rtt

    except NameLookupError:
        pass
    except Exception:
        pass

    return result
