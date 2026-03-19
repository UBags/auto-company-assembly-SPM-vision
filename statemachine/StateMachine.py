from enum import IntEnum
from typing import *
from Configuration import *

class MachineState(IntEnum):

    INVALID_STATE = -1
    READ_QR_CODE = 1
    WRITE_QR_CODE = 2
    READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE = 3
    WRITE_RESULT_OF_CHECKING_KNUCKLE = 4
    READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING = 5
    WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING = 6
    READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING = 7
    WRITE_RESULT_OF_CHECKING_TOP_BEARING = 8
    READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER = 9
    WRITE_RESULT_OF_CHECKING_NUT_AND_PLATEWASHER = 10
    READ_TIGHTENING_TORQUE_1_DONE = 11
    READ_TIGHTENING_TORQUE_1 = 12
    READ_FREE_ROTATIONS_DONE = 13
    READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS = 14
    WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS = 15
    READ_COMPONENT_PRESS_DONE = 16
    READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK = 17
    WRITE_RESULT_OF_CHECKING_NO_BUNK = 18
    READ_TIGHTENING_TORQUE_2_DONE = 19
    READ_TIGHTENING_TORQUE_2 = 20
    READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER = 21
    WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER = 22
    READ_TAKE_PICTURE_FOR_CHECKING_CAP = 23
    WRITE_RESULT_OF_CHECKING_CAP = 24
    READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS = 25
    WRITE_RESULT_OF_CHECKING_BUNK_FOR_CAP_PRESS = 26
    READ_CAP_PRESS_DONE = 27
    READ_FREE_ROTATION_TORQUE_1_DONE = 28
    READ_FREE_ROTATION_TORQUE_1 = 29

    MAX_SECONDS_TO_WAIT_FOR_CAMERA_FEEDBACK : float = CosThetaConfigurator.getInstance().getMaxSecondsToWaitForCameraFeedback()

    @classmethod
    def getMachineStateFromString(cls, state_str: Union[str,'MachineState']) -> 'MachineState':
        """
        Convert a string representation of a MachineState to the corresponding enum member.

        Args:
            state_str: String representation, e.g., '<MachineState.READ_QR_CODE: 1>' or 'READ_QR_CODE'.

        Returns:
            MachineState: The corresponding enum member, or MachineState.INVALID_STATE if conversion fails.
        """
        # Try parsing based on integer value
        if isinstance(state_str, MachineState):
            return state_str
        try:
            # Extract integer from string like '<MachineState.READ_QR_CODE: 1>'
            state_value = int(state_str.split(':')[-1].strip('>'))
            return cls(state_value)
        except (ValueError, IndexError, KeyError):
            pass  # Proceed to name-based parsing

        # Try parsing based on enum name
        try:
            # Extract name from string like '<MachineState.READ_QR_CODE: 1>' or use directly if it's just 'READ_QR_CODE'
            if '.' in state_str:
                state_name = state_str.split('.')[1].split(':')[0]
            else:
                state_name = state_str.strip()
            return cls.__members__[state_name]
        except (KeyError, IndexError):
            pass  # Return INVALID_STATE

        return cls.INVALID_STATE

    @classmethod
    def getMachineStateAsInt(cls, givenState: Union[str,'MachineState']) -> int:
        """
        Return the integer value of a given MachineState enum member.

        Args:
            givenState: A MachineState enum member.

        Returns:
            int: The integer value of the given MachineState.
        """
        if isinstance(givenState, str):
            return cls.getMachineStateAsInt(cls.getMachineStateFromString(givenState))

        return givenState.value

class MachineStateMachine:
    def __init__(self):
        self.currentState: MachineState = MachineState.READ_QR_CODE
        self._instructions: Dict[MachineState, str] = {
            MachineState.READ_QR_CODE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=1),
            MachineState.WRITE_QR_CODE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=2),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=3),
            MachineState.WRITE_RESULT_OF_CHECKING_KNUCKLE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=4),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=5),
            MachineState.WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=6),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=7),
            MachineState.WRITE_RESULT_OF_CHECKING_TOP_BEARING: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=8),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=9),
            MachineState.WRITE_RESULT_OF_CHECKING_NUT_AND_PLATEWASHER: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=10),
            MachineState.READ_TIGHTENING_TORQUE_1_DONE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=11),
            MachineState.READ_TIGHTENING_TORQUE_1: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=12),
            MachineState.READ_FREE_ROTATIONS_DONE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=13),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=14),
            MachineState.WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=15),
            MachineState.READ_COMPONENT_PRESS_DONE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=16),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=17),
            MachineState.WRITE_RESULT_OF_CHECKING_NO_BUNK: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=18),
            MachineState.READ_TIGHTENING_TORQUE_2_DONE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=19),
            MachineState.READ_TIGHTENING_TORQUE_2: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=20),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=21),
            MachineState.WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=22),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=23),
            MachineState.WRITE_RESULT_OF_CHECKING_CAP: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=24),
            MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=25),
            MachineState.WRITE_RESULT_OF_CHECKING_BUNK_FOR_CAP_PRESS: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=26),
            MachineState.READ_CAP_PRESS_DONE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=27),
            MachineState.READ_FREE_ROTATION_TORQUE_1_DONE: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=28),
            MachineState.READ_FREE_ROTATION_TORQUE_1: CosThetaConfigurator.getInstance().getInstructionForState(stateNumber=29)
        }

    def incrementState(self, stateJumps : int = 1) -> None:
        # """Increment the current state, wrapping around to READ_QR_CODE if at the end."""
        # if self.currentState == MachineState.READ_QR_CODE:
        #     self.currentState = MachineState(self.currentState + 2)
        # else:
        #     self.currentState = MachineState(self.currentState + 1)
        newState = self.currentState + stateJumps
        if newState > MachineState.READ_FREE_ROTATION_TORQUE_1:
            self.currentState = MachineState.READ_QR_CODE
        else:
            self.currentState = MachineState(self.currentState + stateJumps)

    def decrementState(self, stateJumps : int = 1) -> None:
        # """Increment the current state, wrapping around to READ_QR_CODE if at the end."""
        # if self.currentState == MachineState.READ_QR_CODE:
        #     self.currentState = MachineState(self.currentState + 2)
        # else:
        #     self.currentState = MachineState(self.currentState + 1)
        newState = self.currentState - stateJumps
        if newState < MachineState.READ_QR_CODE:
            self.currentState = MachineState.READ_QR_CODE
        else:
            self.currentState = MachineState(self.currentState - stateJumps)

    def getCurrentState(self) -> MachineState:
        """Return the current state."""
        return self.currentState

    def setCurrentState(self, newState: Union[int, MachineState]) -> None:
        """Set the current state, ensuring it's valid."""
        if isinstance(newState, MachineState):
            if not (MachineState.READ_QR_CODE <= newState <= MachineState.READ_FREE_ROTATION_TORQUE_1):
                newState = MachineState.READ_QR_CODE
            self.currentState = newState
        else:
            if not (MachineState.READ_QR_CODE <= newState <= MachineState.READ_FREE_ROTATION_TORQUE_1):
                newState = MachineState.READ_QR_CODE
            self.currentState = MachineState(newState)

    def goToFirstState(self) -> None:
        """Set the state to READ_QR_CODE."""
        self.setCurrentState(MachineState.READ_QR_CODE)

    def goToLastState(self) -> None:
        """Set the state to READ_FREE_ROTATION_TORQUE_1."""
        self.setCurrentState(MachineState.READ_FREE_ROTATION_TORQUE_1)

    def getCurrentInstruction(self) -> str:
        """Return the instruction for the current state."""
        return self._instructions.get(self.currentState, "No available Instruction")

    def getLongestInstruction(self) -> str:
        longestInstruction : str = ""
        for key in self._instructions:
            value : str = str(self._instructions[key])
            if len(value) > len(longestInstruction):
                longestInstruction = value
        return longestInstruction