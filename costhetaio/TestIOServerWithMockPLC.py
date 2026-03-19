"""
Test IOServer with MockPLC - Tests the REAL IOServer.py using MockPLC

This script:
1. Starts the REAL IOServer with mockInstance=True
2. Provides a GUI to trigger PLC signals and send responses (including QR codes)
3. Actually tests your IOServer.py code (not a reimplementation)

Usage:
    python TestIOServerWithMockPLC.py

Prerequisites:
    - MockPLC.py must be in the same directory as IOServer.py
    - IOServer.py must have the mockInstance parameter added to __init__
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import sys

# Import the REAL IOServer and MockPLC
from IOServer import IOServer
from MockPLC import get_mock_plc, MockPLC
from redis import Redis
from utils.RedisUtils import *
from Configuration import CosThetaConfigurator
from statemachine.StateMachine import MachineState


class TestIOServerGUI:
    """GUI for testing the real IOServer with MockPLC."""

    def __init__(self, root, io_server: IOServer):
        self.root = root
        self.io = io_server
        self.plc = get_mock_plc()  # Get the same MockPLC instance used by IOServer

        # Redis connection for sending responses
        self.redis = Redis(
            CosThetaConfigurator.getInstance().getRedisHost(),
            CosThetaConfigurator.getInstance().getRedisPort(),
            retry_on_timeout=True
        )

        self.root.title("Test REAL IOServer with MockPLC")
        self.root.geometry("1200x900")

        # Torque values
        self.torque1 = tk.DoubleVar(value=50.0)
        self.torque2 = tk.DoubleVar(value=55.0)
        self.torque3 = tk.DoubleVar(value=45.0)

        # QR Code strings for LHS and RHS
        self.qr_lhs = "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"
        self.qr_rhs = "8201206$400102VA1C$11770$09.03.2025$C5211701$MEK$40cR4-B$1$SPDL ASSY-KNURH$SNPL-MAT$"

        # Store button and label references
        self.step_widgets = {}

        self._build_ui()
        self._start_monitor()
        self._start_heartbeat()

    def _get_current_step_from_io(self):
        """Determine current step from IOServer's machine state."""
        state = self.io.machineState.getCurrentState()
        state_str = str(state)

        state_to_step = {
            'READ_QR_CODE': 0, 'WRITE_QR_CODE': 0,
            'READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE': 1, 'WRITE_RESULT_OF_CHECKING_KNUCKLE': 1,
            'READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING': 2,
            'WRITE_RESULT_OF_CHECKING_HUB_AND_BOTTOM_BEARING': 2,
            'READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING': 3, 'WRITE_RESULT_OF_CHECKING_TOP_BEARING': 3,
            'READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER': 4, 'WRITE_RESULT_OF_CHECKING_NUT_AND_PLATEWASHER': 4,
            'READ_TIGHTENING_TORQUE_1_DONE': 5, 'READ_TIGHTENING_TORQUE_1': 5,
            'READ_FREE_ROTATIONS_DONE': 6,
            'READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS': 7,
            'WRITE_RESULT_OF_CHECKING_BUNK_FOR_COMPONENT_PRESS': 7,
            'READ_COMPONENT_PRESS_DONE': 8,
            'READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK': 9, 'WRITE_RESULT_OF_CHECKING_NO_BUNK': 9,
            'READ_TIGHTENING_TORQUE_2_DONE': 10, 'READ_TIGHTENING_TORQUE_2': 10,
            'READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER': 11,
            'WRITE_RESULT_OF_CHECKING_SPLITPIN_AND_WASHER': 11,
            'READ_TAKE_PICTURE_FOR_CHECKING_CAP': 12, 'WRITE_RESULT_OF_CHECKING_CAP': 12,
            'READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS': 13, 'WRITE_RESULT_OF_CHECKING_BUNK_FOR_CAP_PRESS': 13,
            'READ_CAP_PRESS_DONE': 14,
            'READ_FREE_ROTATION_TORQUE_1_DONE': 15, 'READ_FREE_ROTATION_TORQUE_1': 15,
        }

        for state_name, step in state_to_step.items():
            if state_name in state_str:
                return step
        return 0

    def _update_button_states(self):
        """Enable/disable buttons based on current step."""
        current = self._get_current_step_from_io()

        for step_idx, widgets in self.step_widgets.items():
            if step_idx < current:
                # Completed steps - disable all buttons
                if step_idx == 0:
                    if widgets['lhs_qr']:
                        widgets['lhs_qr'].config(state='disabled')
                    if widgets['rhs_qr']:
                        widgets['rhs_qr'].config(state='disabled')
                    if widgets['reject_qr']:
                        widgets['reject_qr'].config(state='disabled')
                else:
                    if widgets['trigger']:
                        widgets['trigger'].config(state='disabled')
                    if widgets['ok']:
                        widgets['ok'].config(state='disabled')
                    if widgets['notok']:
                        widgets['notok'].config(state='disabled')
                widgets['status'].config(text="✓ Completed", foreground="green")
            elif step_idx == current:
                # Current step - enable buttons
                if step_idx == 0:
                    if widgets['lhs_qr']:
                        widgets['lhs_qr'].config(state='normal')
                    if widgets['rhs_qr']:
                        widgets['rhs_qr'].config(state='normal')
                    if widgets['reject_qr']:
                        widgets['reject_qr'].config(state='normal')
                else:
                    if widgets['trigger']:
                        widgets['trigger'].config(state='normal')
                    if widgets['ok']:
                        widgets['ok'].config(state='normal')
                    if widgets['notok']:
                        widgets['notok'].config(state='normal')
                if "Completed" in widgets['status'].cget("text") or "Waiting" in widgets['status'].cget("text"):
                    widgets['status'].config(text="◄ Current Step", foreground="blue")
            else:
                # Future steps - disable all buttons
                if step_idx == 0:
                    if widgets['lhs_qr']:
                        widgets['lhs_qr'].config(state='disabled')
                    if widgets['rhs_qr']:
                        widgets['rhs_qr'].config(state='disabled')
                    if widgets['reject_qr']:
                        widgets['reject_qr'].config(state='disabled')
                else:
                    if widgets['trigger']:
                        widgets['trigger'].config(state='disabled')
                    if widgets['ok']:
                        widgets['ok'].config(state='disabled')
                    if widgets['notok']:
                        widgets['notok'].config(state='disabled')
                widgets['status'].config(text="Waiting...", foreground="gray")

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Controls
        ctrl_tab = ttk.Frame(notebook)
        notebook.add(ctrl_tab, text="Controls")
        self._build_controls(ctrl_tab)

        # Tab 2: Tag Monitor
        monitor_tab = ttk.Frame(notebook)
        notebook.add(monitor_tab, text="PLC Tag Monitor")
        self._build_monitor(monitor_tab)

        # Tab 3: IOServer Info
        info_tab = ttk.Frame(notebook)
        notebook.add(info_tab, text="IOServer Info")
        self._build_info(info_tab)

    def _build_controls(self, parent):
        # Info banner
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(info_frame, text="⚡ Testing REAL IOServer.py with MockPLC ⚡",
                  font=("Arial", 11, "bold"), foreground="darkgreen").pack()

        # Status
        status_frame = ttk.LabelFrame(parent, text="Current State", padding="10")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self.state_label = ttk.Label(status_frame, text="Loading...", font=("Arial", 12, "bold"))
        self.state_label.pack()

        self.status_label = ttk.Label(status_frame, text="Ready", font=("Arial", 10))
        self.status_label.pack()

        # Steps
        steps_frame = ttk.LabelFrame(parent, text="Process Steps", padding="5")
        steps_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        canvas = tk.Canvas(steps_frame, height=350)
        scrollbar = ttk.Scrollbar(steps_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Vision state mapping
        self.vision_states = {
            0: None,  # QR Code - special handling
            1: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_KNUCKLE,
            2: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_HUB_AND_BOTTOM_BEARING,
            3: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_TOP_BEARING,
            4: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NUT_AND_PLATEWASHER,
            7: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS,
            9: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK,
            11: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER,
            12: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_CAP,
            13: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_CAP_PRESS,
        }

        steps = [
            (0, "Step 0: QR Code", IOServer.PLC_PC_CheckQRCode, "qrcode", "vision"),
            (1, "Step 1: Knuckle", IOServer.PLC_PC_CheckKnuckle, "trigger", "vision"),
            (2, "Step 2: Hub", IOServer.PLC_PC_CheckHub, "trigger", "vision"),
            (3, "Step 3: Hub + 2nd Bearing", IOServer.PLC_PC_CheckHubAndSecondBearing, "trigger", "vision"),
            (4, "Step 4: Nut + Plate Washer", IOServer.PLC_PC_CheckNutAndPlateWasher, "trigger", "vision"),
            (5, "Step 5: Tightening Torque 1", "torque1", "torque", "torque"),
            (6, "Step 6: Free Rotation Done", IOServer.PLC_PC_Station3RotationDone, "trigger", "signal"),
            (7, "Step 7: No Cap Bunk", IOServer.PLC_PC_CheckNoCapBunk, "trigger", "vision"),
            (8, "Step 8: Component Press Done", IOServer.PLC_PC_ComponentPressDone, "trigger", "signal"),
            (9, "Step 9: No k", IOServer.PLC_PC_CheckNoBunk, "trigger", "vision"),
            (10, "Step 10: Tightening Torque 2", "torque2", "torque", "torque"),
            (11, "Step 11: Split Pin + Washer", IOServer.PLC_PC_CheckSplitPinAndWasher, "trigger", "vision"),
            (12, "Step 12: Cap", IOServer.PLC_PC_CheckCap, "trigger", "vision"),
            (13, "Step 13: Bunk", IOServer.PLC_PC_CheckBunk, "trigger", "vision"),
            (14, "Step 14: Cap Press Done", IOServer.PLC_PC_CapPressDone, "trigger", "signal"),
            (15, "Step 15: Free Rotation Torque", "torque3", "torque", "torque"),
        ]

        for idx, label, tag, trig_type, step_type in steps:
            frame = ttk.Frame(scrollable)
            frame.pack(fill=tk.X, pady=2, padx=5)

            ttk.Label(frame, text=label, width=28, anchor="w").pack(side=tk.LEFT)

            trigger_btn = None
            ok_btn = None
            notok_btn = None
            lhs_qr_btn = None
            rhs_qr_btn = None
            reject_qr_btn = None

            if step_type == "vision":
                if idx == 0:
                    # Special buttons for QR Code step
                    lhs_qr_btn = ttk.Button(frame, text="Send LHS QRCode", width=15,
                                           command=lambda: self._send_qr_code("LHS"))
                    lhs_qr_btn.pack(side=tk.LEFT, padx=2)

                    rhs_qr_btn = ttk.Button(frame, text="Send RHS QRCode", width=15,
                                           command=lambda: self._send_qr_code("RHS"))
                    rhs_qr_btn.pack(side=tk.LEFT, padx=2)

                    reject_qr_btn = ttk.Button(frame, text="Reject QR", width=10,
                                              command=lambda: self._reject_qr_code())
                    reject_qr_btn.pack(side=tk.LEFT, padx=2)
                else:
                    # Trigger button for other vision steps
                    trigger_btn = ttk.Button(frame, text="Trigger", width=8,
                                            command=lambda t=tag, st=trig_type, i=idx: self._trigger(t, st, i))
                    trigger_btn.pack(side=tk.LEFT, padx=2)

                    ok_btn = ttk.Button(frame, text="OK", width=6,
                                       command=lambda i=idx: self._send_ok(i))
                    ok_btn.pack(side=tk.LEFT, padx=2)

                    notok_btn = ttk.Button(frame, text="Not OK", width=6,
                                          command=lambda i=idx: self._send_notok(i))
                    notok_btn.pack(side=tk.LEFT, padx=2)
            elif step_type == "torque":
                trigger_btn = ttk.Button(frame, text="Trigger", width=8,
                                        command=lambda t=tag, st=trig_type, i=idx: self._trigger(t, st, i))
                trigger_btn.pack(side=tk.LEFT, padx=2)

                if idx == 5:
                    var = self.torque1
                elif idx == 10:
                    var = self.torque2
                else:
                    var = self.torque3
                ttk.Entry(frame, textvariable=var, width=6).pack(side=tk.LEFT, padx=2)
                ttk.Label(frame, text="Nm").pack(side=tk.LEFT)
            else:  # signal
                trigger_btn = ttk.Button(frame, text="Trigger", width=8,
                                        command=lambda t=tag, st=trig_type, i=idx: self._trigger(t, st, i))
                trigger_btn.pack(side=tk.LEFT, padx=2)
                ttk.Label(frame, text="", width=14).pack(side=tk.LEFT)

            status_lbl = ttk.Label(frame, text="Waiting...", width=30, anchor="w", foreground="gray")
            status_lbl.pack(side=tk.LEFT, padx=5)

            self.step_widgets[idx] = {
                'trigger': trigger_btn,
                'ok': ok_btn,
                'notok': notok_btn,
                'lhs_qr': lhs_qr_btn,
                'rhs_qr': rhs_qr_btn,
                'reject_qr': reject_qr_btn,
                'status': status_lbl,
                'type': step_type
            }

        # Control buttons
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=10)

        ttk.Button(ctrl_frame, text="Reset All", command=self._reset).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Print Tags", command=self._print_tags).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Auto Cycle (All OK)", command=self._auto_cycle).pack(side=tk.LEFT, padx=5)

    def _build_monitor(self, parent):
        self.tag_text = scrolledtext.ScrolledText(parent, font=("Courier", 9))
        self.tag_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_info(self, parent):
        info_text = scrolledtext.ScrolledText(parent, font=("Courier", 9), wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        info = "IOServer Configuration\n"
        info += "=" * 70 + "\n\n"
        info += f"PLC IP: {IOServer.PLC_IP}\n"
        info += f"Using MockPLC: True\n\n"

        info += "Tag Names (Step 0: QR Code)\n"
        info += "-" * 70 + "\n"
        info += f"  PLC_PC_CheckQRCode:           {IOServer.PLC_PC_CheckQRCode}\n"
        info += f"  PC_PLC_QRCodeCheckOK:         {IOServer.PC_PLC_QRCodeCheckOK}\n"
        info += f"  PC_PLC_QRCodeCheckDone:       {IOServer.PC_PLC_QRCodeCheckDone}\n\n"

        info += "Rotation Setting Tags (Written by IOServer after QR Code)\n"
        info += "-" * 70 + "\n"
        info += f"  PC_PLC_NoOfRotation1CCW:      {IOServer.PC_PLC_NoOfRotation1CCW}\n"
        info += f"  PC_PLC_NoOfRotation1CW:       {IOServer.PC_PLC_NoOfRotation1CW}\n"
        info += f"  PC_PLC_NoOfRotation2CCW:      {IOServer.PC_PLC_NoOfRotation2CCW}\n"
        info += f"  PC_PLC_NoOfRotation2CW:       {IOServer.PC_PLC_NoOfRotation2CW}\n"
        info += f"  PC_PLC_LH_RH_Selection:       {IOServer.PC_PLC_LH_RH_Selection}\n"
        info += f"  PC_PLC_RotationUnitRPM:       {IOServer.PC_PLC_RotationUnitRPM}\n\n"

        info += "Tag Names (Other Steps)\n"
        info += "-" * 70 + "\n"
        info += f"  PLC_PC_CheckKnuckle:          {IOServer.PLC_PC_CheckKnuckle}\n"
        info += f"  PLC_PC_CheckHub:              {IOServer.PLC_PC_CheckHub}\n"
        info += f"  PLC_PC_CheckHubAndSecondBearing: {IOServer.PLC_PC_CheckHubAndSecondBearing}\n"
        info += f"  PLC_PC_CheckNutAndPlateWasher: {IOServer.PLC_PC_CheckNutAndPlateWasher}\n"
        info += f"  PLC_PC_Station2TorqueValueSet: {IOServer.PLC_PC_Station2TorqueValueSet}\n"
        info += f"  PLC_PC_Station2TorqueValue:   {IOServer.PLC_PC_Station2TorqueValue}\n"
        info += f"  PLC_PC_Station3RotationDone:  {IOServer.PLC_PC_Station3RotationDone}\n"
        info += f"  PLC_PC_CheckNoCapBunk:        {IOServer.PLC_PC_CheckNoCapBunk}\n"
        info += f"  PLC_PC_ComponentPressDone:    {IOServer.PLC_PC_ComponentPressDone}\n"
        info += f"  PLC_PC_CheckNoBung:           {IOServer.PLC_PC_CheckNoBunk}\n"
        info += f"  PLC_PC_CheckSplitPinAndWasher: {IOServer.PLC_PC_CheckSplitPinAndWasher}\n"
        info += f"  PLC_PC_CheckCap:              {IOServer.PLC_PC_CheckCap}\n"
        info += f"  PLC_PC_CheckBung:             {IOServer.PLC_PC_CheckBunk}\n"
        info += f"  PLC_PC_CapPressDone:          {IOServer.PLC_PC_CapPressDone}\n"
        info += f"  PLC_PC_Station3TorqueValueSet: {IOServer.PLC_PC_Station3TorqueValueSet}\n"
        info += f"  PLC_PC_Station3TorqueValue:   {IOServer.PLC_PC_Station3TorqueValue}\n"

        info_text.insert(tk.END, info)
        info_text.config(state='disabled')

    def _trigger(self, tag, step_type, step_idx):
        """Trigger a PLC tag via MockPLC to move IOServer from READ to WRITE state."""
        widgets = self.step_widgets[step_idx]

        if step_type == "torque":
            if tag == "torque1":
                self.plc.set_tag(IOServer.PLC_PC_Station2TorqueValue, self.torque1.get())
                self.plc.set_tag(IOServer.PLC_PC_Station2TorqueValueSet, True)
                widgets['status'].config(text=f"Triggered: Set torque={self.torque1.get()} Nm", foreground="orange")
            elif tag == "torque2":
                self.plc.set_tag(IOServer.PLC_PC_Station2TorqueValueSet, False)
                time.sleep(0.05)
                self.plc.set_tag(IOServer.PLC_PC_Station2TorqueValue, self.torque2.get())
                self.plc.set_tag(IOServer.PLC_PC_Station2TorqueValueSet, True)
                widgets['status'].config(text=f"Triggered: Set torque={self.torque2.get()} Nm", foreground="orange")
            elif tag == "torque3":
                self.plc.set_tag(IOServer.PLC_PC_Station3TorqueValue, self.torque3.get())
                self.plc.set_tag(IOServer.PLC_PC_Station3TorqueValueSet, True)
                widgets['status'].config(text=f"Triggered: Set torque={self.torque3.get()} Nm", foreground="orange")
        else:
            # Set PLC tag to trigger IOServer transition from READ to WRITE state
            self.plc.set_tag(tag, True)
            widgets['status'].config(text=f"Triggered: {tag}=True → Now click OK or Not OK", foreground="orange")

        self.status_label.config(text=f"Step {step_idx}: Triggered - IOServer moved to WRITE state")

    def _send_qr_code(self, qr_type: str):
        """Send QR code to IOServer mimicking QRCodeServer."""
        widgets = self.step_widgets[0]

        # First trigger the PLC tag
        self.plc.set_tag(IOServer.PLC_PC_CheckQRCode, True)

        # Select the appropriate QR code based on type
        qr_code = self.qr_lhs if qr_type == "LHS" else self.qr_rhs

        # Send to IOServer via Redis
        sendDataFromQRCodeServerToIOServer(self.redis, qrCodeStatus=ok, qrCode=qr_code)

        # Reset the trigger tag after successful send
        time.sleep(0.1)
        self.plc.set_tag(IOServer.PLC_PC_CheckQRCode, False)

        # Update status
        widgets['status'].config(text=f"Sent {qr_type} QR code → IOServer processing...", foreground="green")
        self.status_label.config(text=f"Step 0: Sent {qr_type} QR code")

    def _reject_qr_code(self):
        """Send QR code rejection to IOServer mimicking QRCodeServer failure."""
        widgets = self.step_widgets[0]

        # First trigger the PLC tag
        self.plc.set_tag(IOServer.PLC_PC_CheckQRCode, True)

        # Send rejection to IOServer via Redis
        sendDataFromQRCodeServerToIOServer(self.redis, qrCodeStatus=notok, qrCode="")

        # Reset the trigger tag so IOServer doesn't immediately re-trigger
        time.sleep(0.1)
        self.plc.set_tag(IOServer.PLC_PC_CheckQRCode, False)

        # Update status
        widgets['status'].config(text="QR rejected → Tag reset, ready to retry", foreground="red")
        self.status_label.config(text="Step 0: QR code rejected")

    def _send_ok(self, idx):
        widgets = self.step_widgets[idx]

        if idx == 0:
            # QR Code step has dedicated buttons now, this shouldn't be called
            self.status_label.config(text="Use 'Send LHS QRCode' or 'Send RHS QRCode' buttons for QR code")
            return
        elif idx in self.vision_states:
            # Send OK response via Redis - IOServer will write PC_PLC_*CheckOK=True and PC_PLC_*CheckDone=True
            sendDataFromCameraServerToIOServer(self.redis, result=ok,
                                               currentMachineState=self.vision_states[idx])

            # Reset the trigger tag to False after successful completion
            tag_map = {
                1: IOServer.PLC_PC_CheckKnuckle,
                2: IOServer.PLC_PC_CheckHub,
                3: IOServer.PLC_PC_CheckHubAndSecondBearing,
                4: IOServer.PLC_PC_CheckNutAndPlateWasher,
                7: IOServer.PLC_PC_CheckNoCapBunk,
                9: IOServer.PLC_PC_CheckNoBunk,
                11: IOServer.PLC_PC_CheckSplitPinAndWasher,
                12: IOServer.PLC_PC_CheckCap,
                13: IOServer.PLC_PC_CheckBunk,
            }

            if idx in tag_map:
                # Small delay to ensure IOServer processes the OK first
                time.sleep(0.1)
                self.plc.set_tag(tag_map[idx], False)

            widgets['status'].config(text="OK sent → IOServer writes OK=True, Done=True", foreground="green")

        self.status_label.config(text=f"Step {idx}: OK sent - IOServer will write result tags and advance")

    def _send_notok(self, idx):
        widgets = self.step_widgets[idx]

        if idx == 0:
            # QR Code step has dedicated buttons now, this shouldn't be called
            self.status_label.config(text="Use 'Reject QR' button to reject QR code")
            return
        elif idx in self.vision_states:
            # Send NotOK response via Redis - IOServer will write PC_PLC_*CheckOK=False and PC_PLC_*CheckDone=True
            sendDataFromCameraServerToIOServer(self.redis, result=notok,
                                               currentMachineState=self.vision_states[idx])

            # CRITICAL: Reset the trigger tag to False so IOServer doesn't immediately re-trigger
            # when it goes back to READ state
            tag_map = {
                1: IOServer.PLC_PC_CheckKnuckle,
                2: IOServer.PLC_PC_CheckHub,
                3: IOServer.PLC_PC_CheckHubAndSecondBearing,
                4: IOServer.PLC_PC_CheckNutAndPlateWasher,
                7: IOServer.PLC_PC_CheckNoCapBunk,
                9: IOServer.PLC_PC_CheckNoBunk,
                11: IOServer.PLC_PC_CheckSplitPinAndWasher,
                12: IOServer.PLC_PC_CheckCap,
                13: IOServer.PLC_PC_CheckBunk,
            }

            if idx in tag_map:
                # Small delay to ensure IOServer processes the NotOK first
                time.sleep(0.1)
                self.plc.set_tag(tag_map[idx], False)

            widgets['status'].config(text="NotOK sent → Tag reset, ready to retry", foreground="red")

        self.status_label.config(text=f"Step {idx}: NotOK sent - IOServer will write result tags and retry")

    def _reset(self):
        self.plc.reset_all_tags()
        self.redis.flushdb()

        for idx, widgets in self.step_widgets.items():
            widgets['status'].config(text="Waiting...", foreground="gray")

        self._update_button_states()
        self.status_label.config(text="Reset complete - all MockPLC tags reset to defaults")

    def _print_tags(self):
        self.plc.print_tags()
        self.status_label.config(text="Tag values printed to console")

    def _auto_cycle(self):
        """Run complete cycle automatically with LHS QR code."""

        def cycle():
            steps = [
                (IOServer.PLC_PC_CheckQRCode, "qrcode", 0),
                (IOServer.PLC_PC_CheckKnuckle, "vision", 1),
                (IOServer.PLC_PC_CheckHub, "vision", 2),
                (IOServer.PLC_PC_CheckHubAndSecondBearing, "vision", 3),
                (IOServer.PLC_PC_CheckNutAndPlateWasher, "vision", 4),
                ("torque1", "torque", 5),
                (IOServer.PLC_PC_Station3RotationDone, "signal", 6),
                (IOServer.PLC_PC_CheckNoCapBunk, "vision", 7),
                (IOServer.PLC_PC_ComponentPressDone, "signal", 8),
                (IOServer.PLC_PC_CheckNoBunk, "vision", 9),
                ("torque2", "torque", 10),
                (IOServer.PLC_PC_CheckSplitPinAndWasher, "vision", 11),
                (IOServer.PLC_PC_CheckCap, "vision", 12),
                (IOServer.PLC_PC_CheckBunk, "vision", 13),
                (IOServer.PLC_PC_CapPressDone, "signal", 14),
                ("torque3", "torque", 15),
            ]

            for tag, step_type, idx in steps:
                self.root.after(0, lambda i=idx: self.status_label.config(text=f"Auto: Running Step {i}"))

                if step_type == "qrcode":
                    # Send LHS QR code
                    self._send_qr_code("LHS")
                elif step_type == "vision":
                    self._trigger(tag, step_type, idx)
                    time.sleep(0.5)
                    self._send_ok(idx)
                else:
                    # torque or signal
                    self._trigger(tag, step_type, idx)

                time.sleep(1.5)
                self.root.after(0, self._update_button_states)

            self.root.after(0, lambda: self.status_label.config(text="Auto cycle complete! All 16 steps done."))

        threading.Thread(target=cycle, daemon=True).start()

    def _start_monitor(self):
        def monitor():
            while True:
                try:
                    state = self.io.machineState.getCurrentState()
                    self.state_label.config(text=f"State: {state}")

                    self.root.after(0, self._update_button_states)

                    tags = self.plc.get_all_tags()
                    text = "MockPLC Tag Values (used by REAL IOServer):\n"
                    text += "=" * 70 + "\n"

                    # Group tags by category
                    qr_tags = {}
                    rotation_tags = {}
                    other_tags = {}

                    for tag, value in sorted(tags.items()):
                        if "QRCode" in tag:
                            qr_tags[tag] = value
                        elif "Rotation" in tag or "LH_RH_Selection" in tag or "RPM" in tag:
                            rotation_tags[tag] = value
                        else:
                            other_tags[tag] = value

                    if qr_tags:
                        text += "\nQR Code Tags:\n"
                        for tag, value in qr_tags.items():
                            text += f"  {tag}: {value}\n"

                    if rotation_tags:
                        text += "\nRotation Settings (written by IOServer):\n"
                        for tag, value in rotation_tags.items():
                            text += f"  {tag}: {value}\n"

                    if other_tags:
                        text += "\nOther Tags:\n"
                        for tag, value in other_tags.items():
                            text += f"  {tag}: {value}\n"

                    self.tag_text.delete(1.0, tk.END)
                    self.tag_text.insert(tk.END, text)
                except Exception as e:
                    print(f"Monitor error: {e}")
                time.sleep(0.5)

        threading.Thread(target=monitor, daemon=True).start()

    def _start_heartbeat(self):
        def hb():
            while True:
                try:
                    sendCombinedHeartbeatFromHeartbeatServerToIOServer(self.redis, ALIVE)
                except:
                    pass
                time.sleep(1)

        threading.Thread(target=hb, daemon=True).start()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Test REAL IOServer with MockPLC")
    print("=" * 70)
    print()
    print("This script tests your ACTUAL IOServer.py code using a MockPLC.")
    print("The MockPLC simulates all PLC tag read/write operations in memory.")
    print()
    print("Starting IOServer with mockInstance=True...")
    print()

    try:
        # Start the REAL IOServer with MockPLC
        io = IOServer(mockInstance=True)

        print()
        print("IOServer started successfully with MockPLC!")
        print("Starting GUI...")
        print()

        # Start GUI
        root = tk.Tk()
        app = TestIOServerGUI(root, io)
        root.mainloop()

    except Exception as e:
        print(f"\nError starting IOServer: {e}")
        print("\nMake sure you have:")
        print("  1. Added 'mockInstance' parameter to IOServer.__init__()")
        print("  2. Modified connectPLC() to use MockPLC when mockInstance=True")
        print("  3. MockPLC.py is in the same directory as IOServer.py")
        sys.exit(1)