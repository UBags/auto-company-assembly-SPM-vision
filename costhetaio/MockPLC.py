"""
MockPLC - A mock PLC class that mimics pycomm3's LogixDriver interface.

This allows testing IOServer without actual PLC hardware.
The MockPLC stores all tag values in memory and provides the same
read/write interface as LogixDriver.

Usage:
    from IOServer import IOServer
    io = IOServer(mockInstance=True)  # Uses MockPLC instead of real PLC
"""

import threading
from typing import Any, Dict, Optional, Union
from Configuration import CosThetaConfigurator


class MockTagResult:
    """Mimics the result object returned by LogixDriver.read()"""

    def __init__(self, tag: str, value: Any):
        self.tag = tag
        self.value = value
        self.error = None

    def __repr__(self):
        return f"MockTagResult(tag='{self.tag}', value={self.value})"


class MockPLC:
    """
    Mock PLC class that mimics pycomm3's LogixDriver interface.

    Provides:
    - open() / close() methods
    - connected property
    - read(tag) -> returns MockTagResult with .value
    - write(tag, value)

    All tag values are stored in an in-memory dictionary.
    Thread-safe for concurrent read/write operations.
    """

    # Singleton instance for shared state across reads/writes
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Ensure single instance so reads and writes share same tag state."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, ip_address: str = "MockPLC"):
        """Initialize MockPLC (only runs once due to singleton)."""
        if self._initialized:
            return

        self._initialized = True
        self.ip_address = ip_address
        self._connected = False
        self._tags: Dict[str, Any] = {}
        self._tag_lock = threading.Lock()

        # Initialize all tags with default values
        self._initialize_tags()

        print(f"[MockPLC] Initialized with {len(self._tags)} tags")

    def _initialize_tags(self):
        """Initialize all PLC tags with default values based on Configuration."""
        config = CosThetaConfigurator.getInstance()

        # Default tag values - all bools False, all floats 0.0, watch tag = 1234
        default_tags = {
            # QR Code (Step 0)
            config.getPlcPcCheckQRCodeTagName(): False,
            config.getPcPlcQRCodeOKTagName(): False,
            config.getPcPlcQRCodeDoneTagName(): False,

            # Knuckle (Step 1)
            config.getPlcPcCheckKnuckleTagName(): False,
            config.getPcPlcKnuckleCheckOKTagName(): False,
            config.getPcPlcKnuckleCheckDoneTagName(): False,

            # Hub (Step 2)
            config.getPlcPcCheckHubTagName(): False,
            config.getPcPlcHubCheckOKTagName(): False,
            config.getPcPlcHubCheckDoneTagName(): False,

            # Hub and Second Bearing (Step 3)
            config.getPlcPcCheckHubAndSecondBearingTagName(): False,
            config.getPcPlcHubAndSecondBearingCheckOKTagName(): False,
            config.getPcPlcHubAndSecondBearingCheckDoneTagName(): False,

            # Nut and Plate Washer (Step 4)
            config.getPlcPcCheckNutAndPlateWasherTagName(): False,
            config.getPcPlcNutAndPlateWasherOKTagName(): False,
            config.getPcPlcNutAndPlateWasherDoneTagName(): False,

            # Station 2 Torque (Step 5 and 10)
            config.getPlcPcStation2TorqueValueSetTagName(): False,
            config.getPlcPcStation2TorqueValueTagName(): 0.0,

            # Station 3 Rotation Done (Step 6)
            config.getPlcPcStation3RotationDoneTagName(): False,

            # No Cap Bung (Step 7)
            config.getPlcPcCheckNoCapBunkTagName(): False,
            config.getPcPlcNoCapBunkCheckOKTagName(): False,
            config.getPcPlcNoCapBunkCheckDoneTagName(): False,

            # Component Press Done (Step 8)
            config.getPlcPcComponentPressDoneTagName(): False,

            # No Bung (Step 9)
            config.getPlcPcCheckNoBunkTagName(): False,
            config.getPcPlcNoBunkCheckOKTagName(): False,
            config.getPcPlcNoBunkCheckDoneTagName(): False,

            # Split Pin and Washer (Step 11)
            config.getPlcPcCheckSplitPinAndWasherTagName(): False,
            config.getPcPlcSplitPinAndWasherCheckOKTagName(): False,
            config.getPcPlcSplitPinAndWasherCheckDoneTagName(): False,

            # Cap (Step 12)
            config.getPlcPcCheckCapTagName(): False,
            config.getPcPlcCapCheckOKTagName(): False,
            config.getPcPlcCapCheckDoneTagName(): False,

            # Bung (Step 13)
            config.getPlcPcCheckBunkTagName(): False,
            config.getPcPlcBunkCheckOKTagName(): False,
            config.getPcPlcBunkCheckDoneTagName(): False,

            # Cap Press Done (Step 14)
            config.getPlcPcCapPressDoneTagName(): False,

            # Station 3 Torque (Step 15)
            config.getPlcPcStation3TorqueValueSetTagName(): False,
            config.getPlcPcStation3TorqueValueTagName(): 0.0,

            # System tags
            config.getPlcPcEmergencyAbortTagName(): False,
            config.getPlcPcWatchTagName(): 1234,  # Watch tag value expected by IOServer
            config.getPcPlcConnectionStatusTagName(): False,
        }

        with self._tag_lock:
            self._tags = default_tags.copy()

    @property
    def connected(self) -> bool:
        """Return connection status (mimics LogixDriver.connected)."""
        return self._connected

    def open(self) -> bool:
        """Open connection to MockPLC (mimics LogixDriver.open)."""
        self._connected = True
        print(f"[MockPLC] Connection opened")
        return True

    def close(self) -> bool:
        """Close connection to MockPLC (mimics LogixDriver.close)."""
        self._connected = False
        print(f"[MockPLC] Connection closed")
        return True

    def read(self, tag: str) -> MockTagResult:
        """
        Read a tag value (mimics LogixDriver.read).

        Args:
            tag: Tag name to read

        Returns:
            MockTagResult with .value property
        """
        with self._tag_lock:
            if tag in self._tags:
                value = self._tags[tag]
            else:
                # Unknown tag - return None (LogixDriver behavior)
                print(f"[MockPLC] Warning: Reading unknown tag '{tag}'")
                value = None

            return MockTagResult(tag, value)

    def write(self, tag: str, value: Any) -> bool:
        """
        Write a value to a tag (mimics LogixDriver.write).

        Args:
            tag: Tag name to write
            value: Value to write

        Returns:
            True if successful
        """
        with self._tag_lock:
            self._tags[tag] = value
            return True

    # ==================== Helper Methods for Testing ====================

    def get_tag(self, tag: str) -> Any:
        """Get a tag value directly (for testing)."""
        with self._tag_lock:
            return self._tags.get(tag)

    def set_tag(self, tag: str, value: Any):
        """Set a tag value directly (for testing/simulation)."""
        with self._tag_lock:
            self._tags[tag] = value

    def get_all_tags(self) -> Dict[str, Any]:
        """Get all tag values (for debugging)."""
        with self._tag_lock:
            return self._tags.copy()

    def reset_all_tags(self):
        """Reset all tags to default values."""
        self._initialize_tags()
        print(f"[MockPLC] All tags reset to defaults")

    def print_tags(self):
        """Print all tag values (for debugging)."""
        with self._tag_lock:
            print("\n[MockPLC] Current Tag Values:")
            print("=" * 60)
            for tag, value in sorted(self._tags.items()):
                print(f"  {tag}: {value}")
            print("=" * 60)


# =============================================================================
# Utility function to get the singleton MockPLC instance
# =============================================================================

def get_mock_plc() -> MockPLC:
    """Get the singleton MockPLC instance."""
    return MockPLC()


# =============================================================================
# Test code - runs when MockPLC.py is executed directly
# =============================================================================

if __name__ == "__main__":
    print("Testing MockPLC...")

    plc = MockPLC()
    plc.open()

    print(f"\nConnected: {plc.connected}")

    # Test read
    result = plc.read("PLC_PC_CheckQRCode")
    print(f"Read PLC_PC_CheckQRCode: {result.value}")

    # Test write
    plc.write("PLC_PC_CheckQRCode", True)
    result = plc.read("PLC_PC_CheckQRCode")
    print(f"After write, PLC_PC_CheckQRCode: {result.value}")

    # Print all tags
    plc.print_tags()

    plc.close()
    print(f"\nConnected after close: {plc.connected}")