# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
Utility class for clearing Redis queues used by the application.
"""
from typing import List, Optional

from redis import Redis

from utils.RedisUtils import getMessageCount
from Configuration import *

CosThetaConfigurator.getInstance()


class ClearQueues:
    """
    Utility class for managing and clearing Redis message queues.

    Collects all application queues from configuration and provides
    methods to clear them and report message counts.
    """

    def __init__(self) -> None:
        """Initialize ClearQueues with all configured queue names."""
        self.hostname: str = CosThetaConfigurator.getInstance().getRedisHost()
        self.port: int = CosThetaConfigurator.getInstance().getRedisPort()
        self.queues: List[str] = []
        self.redisConnection: Optional[Redis] = None
        self.clientRedisConnected: bool = False

        self._collectQueues()
        self.connectToRedis()

    def _collectQueues(self) -> None:
        """Collect all queue names from configuration."""
        config = CosThetaConfigurator.getInstance()

        # Per-station queues (stations 1 and 2)
        for i in range(1, 3):
            self.queues.extend([
                config.getRecordingQueue(i),
                config.getCameraTakePicQueue(i),
                config.getCameraHeartbeatQueue(i),
                config.getCameraRequestResultQueue(i),
                config.getCameraResultQueue(i),
                config.getActuatorHeartbeatQueue(i),
                config.getActuatorActionQueue(i),
                config.getTowerLampActionQueue(i),
                config.getBottleReleaseHeartbeatQueue(i),
                config.getSavePictureQueue(i),
            ])

        # Global queues
        self.queues.extend([
            config.getDatabaseQueue(),
            config.getMonitorAllConnectionsQueue(),
            config.getConnectionAlarmQueue(),
            config.getAllConnectionsQueue(),
            config.getStopCommandQueue(),
            config.getConsoleLoggingQueue(),
            config.getFileLoggingQueue(),
            config.getStoppedResponseQueue(),
            config.getIOHeartbeatQueue(),
            config.getDatabaseHeartbeatQueue(),
        ])

    def connectToRedis(self, forceRenew: bool = False) -> bool:
        """
        Establish Redis connection.

        Args:
            forceRenew: If True, close existing connection and create new one

        Returns:
            True if connected successfully, False otherwise
        """
        if forceRenew:
            self.redisConnection = None
            self.clientRedisConnected = False

        if not self.clientRedisConnected:
            try:
                self.redisConnection = Redis(
                    self.hostname,
                    self.port,
                    retry_on_timeout=True
                )
                self.clientRedisConnected = True
                return True
            except Exception:
                self.clientRedisConnected = False
                self.redisConnection = None
                return False

        return self.clientRedisConnected

    def clearQueues(self) -> int:
        """
        Clear all configured queues.

        Returns:
            Number of queues successfully cleared
        """
        if not self.redisConnection:
            return 0

        cleared = 0
        for queue in self.queues:
            try:
                self.redisConnection.xtrim(queue, 0)
                cleared += 1
            except Exception:
                pass

        return cleared

    def clearQueue(self, queueName: str) -> bool:
        """
        Clear a specific queue.

        Args:
            queueName: Name of the queue to clear

        Returns:
            True if cleared successfully, False otherwise
        """
        if not self.redisConnection:
            return False

        try:
            self.redisConnection.xtrim(queueName, 0)
            return True
        except Exception:
            return False

    def reportMessageCount(self) -> dict:
        """
        Get message counts for all queues.

        Returns:
            Dictionary mapping queue names to message counts
        """
        counts = {}
        for queue in self.queues:
            count = getMessageCount(self.redisConnection, queue)
            counts[queue] = count
            print(f"{count} entries in queue {queue}")
        return counts

    def getMessageCount(self, queueName: str) -> int:
        """
        Get message count for a specific queue.

        Args:
            queueName: Name of the queue

        Returns:
            Number of messages in the queue, or -1 if error
        """
        return getMessageCount(self.redisConnection, queueName)

    def getTotalMessageCount(self) -> int:
        """
        Get total message count across all queues.

        Returns:
            Total number of messages, or -1 if error
        """
        total = 0
        for queue in self.queues:
            count = getMessageCount(self.redisConnection, queue)
            if count >= 0:
                total += count
            else:
                return -1
        return total


# Convenience function for quick clearing
def clearAllQueues() -> int:
    """
    Create a ClearQueues instance and clear all queues.

    Returns:
        Number of queues cleared
    """
    cq = ClearQueues()
    return cq.clearQueues()

# Example usage (commented out):
# if __name__ == "__main__":
#     cq = ClearQueues()
#     cq.reportMessageCount()
#     cq.clearQueues()
#     cq.reportMessageCount()
