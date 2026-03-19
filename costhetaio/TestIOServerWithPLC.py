"""
IOServer Test Script - For use with REAL PLC

This script tests the IOServer with actual PLC hardware by:
1. Sending QRCode/Camera server responses via Redis (including QR code strings)
2. Providing a GUI to step through the entire process
3. Requesting PLC tag values from IOServer via Redis queues
4. Properly waiting for signal steps (torque, press, etc.) to complete

Run this ALONGSIDE IOServer.py which is connected to the real PLC.

Process Steps (16 total, 29 states):
- Step 0: QR Code (States 1-2) - Vision
- Step 1: Knuckle (States 3-4) - Vision
- Step 2: Hub (States 5-6) - Vision
- Step 3: Hub + 2nd Bearing (States 7-8) - Vision
- Step 4: Nut + Plate Washer (States 9-10) - Vision
- Step 5: Tightening Torque 1 (States 11-12) - Signal (PLC sets torque value, IOServer reads it)
- Step 6: Free Rotation Done (State 13) - Signal (PLC only)
- Step 7: No Cap Bunk (States 14-15) - Vision
- Step 8: Component Press Done (State 16) - Signal (PLC only)
- Step 9: No Bunk (States 17-18) - Vision
- Step 10: Tightening Torque 2 (States 19-20) - Signal (PLC sets torque value, IOServer reads it)
- Step 11: Split Pin + Washer (States 21-22) - Vision
- Step 12: Cap (States 23-24) - Vision
- Step 13: Bunk (States 25-26) - Vision
- Step 14: Cap Press Done (State 27) - Signal (PLC only)
- Step 15: Free Rotation Torque (States 28-29) - Signal (PLC sets torque value, IOServer reads it)

Torque Step Workflow (Steps 5, 10, 15):
- State X_DONE: IOServer waits for PLC signal that torque operation is complete
- State X_VALUE: IOServer reads the torque value from PLC tags, then resets the tags
- PLC must write the torque value BETWEEN these two states

Usage:
    Terminal 1: python IOServer.py              (with real PLC connected)
    Terminal 2: python TestIOServerWithPLC.py   (this script)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import json
from redis import Redis
from utils.RedisUtils import *
from Configuration import CosThetaConfigurator
from statemachine.StateMachine import MachineState

# Redis queue names for tag request/response
PUBLISH_TAGS_QUEUE = "publishTags"
RECEIVE_TAGS_QUEUE = "receiveTags"

# Initialize Redis
testRedisConnection = Redis(
    CosThetaConfigurator.getInstance().getRedisHost(),
    CosThetaConfigurator.getInstance().getRedisPort(),
    retry_on_timeout=True
)

# Clear Redis on startup
testRedisConnection.flushdb()


class IOServerTestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IOServer Test - Real PLC (29 State Process)")
        self.root.geometry("1400x850")

        self.current_step = 0
        self.step_widgets = {}  # {step_idx: {'ok': btn, 'notok': btn, 'status': label}}
        self.tag_request_pending = False
        self.signal_monitor_active = False  # Flag to track if signal monitoring is active
        self.stop_signal_monitor = False  # Flag to stop signal monitoring thread

        # QR Code strings for LHS and RHS
        self.qr_lhs = "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"
        self.qr_rhs = "8201206$400102VA1C$11770$09.03.2025$C5211701$MEK$40cR4-B$1$SPDL ASSY-KNURH$SNPL-MAT$"

        self._build_ui()
        self._start_heartbeat()
        self._update_button_states()

    def _build_ui(self):
        # Main horizontal paned window (left 2/3, right 1/3)
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame (2/3) - Controls
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        # Right frame (1/3) - Tag display
        right_frame = ttk.LabelFrame(main_paned, text="PLC Tag Values", padding="5")
        main_paned.add(right_frame, weight=1)

        # Build left side
        self._build_controls(left_frame)

        # Build right side - Tag display
        self._build_tag_display(right_frame)

    def _build_controls(self, parent):
        # Title
        title = ttk.Label(parent, text="IOServer Test - Real PLC Mode",
                          font=("Arial", 14, "bold"))
        title.pack(pady=5)

        # Status frame
        status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5, padx=5)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=4, wrap=tk.WORD)
        self.status_text.pack(fill=tk.X)
        self._update_status("Ready. Click buttons to send responses to IOServer.")

        # Process steps frame with scrollbar
        steps_frame = ttk.LabelFrame(parent, text="Process Steps (29 States)", padding="10")
        steps_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        # Add canvas with scrollbar for steps
        canvas = tk.Canvas(steps_frame)
        scrollbar = ttk.Scrollbar(steps_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Define all steps
        self.steps = [
            ("Step 0", "QR Code", "States 1-2", "vision", 0),
            ("Step 1", "Knuckle", "States 3-4", "vision", 1),
            ("Step 2", "Hub", "States 5-6", "vision", 2),
            ("Step 3", "Hub + 2nd Bearing", "States 7-8", "vision", 3),
            ("Step 4", "Nut + Plate Washer", "States 9-10", "vision", 4),
            ("Step 5", "Tightening Torque 1", "States 11-12", "signal", 5),
            ("Step 6", "Free Rotation Done", "State 13", "signal", 6),
            ("Step 7", "No Cap Bunk", "States 14-15", "vision", 7),
            ("Step 8", "Component Press Done", "State 16", "signal", 8),
            ("Step 9", "No Bunk", "States 17-18", "vision", 9),
            ("Step 10", "Tightening Torque 2", "States 19-20", "signal", 10),
            ("Step 11", "Split Pin + Washer", "States 21-22", "vision", 11),
            ("Step 12", "Cap", "States 23-24", "vision", 12),
            ("Step 13", "Bunk", "States 25-26", "vision", 13),
            ("Step 14", "Cap Press Done", "State 27", "signal", 14),
            ("Step 15", "Free Rotation Torque", "States 28-29", "signal", 15),
        ]

        # Map step index to MachineState for camera responses
        self.vision_state_map = {
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

        # Map signal step index to the MachineState that indicates completion
        # For torque steps (5, 10, 15): IOServer goes through TWO states:
        #   1. DONE state: Waits for PLC signal that operation is complete
        #   2. VALUE state: Reads torque value from PLC, resets tags, transitions
        # Signal step is marked complete when IOServer has passed the VALUE state
        self.signal_completion_state_map = {
            5: MachineState.READ_FREE_ROTATIONS_DONE,  # Step 5 (Torque 1): States 11→12→13
            6: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_BUNK_FOR_COMPONENT_PRESS,  # Step 6: State 13→14
            8: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_NO_BUNK,  # Step 8 (Component Press): State 16→17
            10: MachineState.READ_TAKE_PICTURE_FOR_CHECKING_SPLITPIN_AND_WASHER,  # Step 10 (Torque 2): States 19→20→21
            14: MachineState.READ_FREE_ROTATION_TORQUE_1_DONE,  # Step 14 (Cap Press): State 27→28
            15: MachineState.READ_QR_CODE,  # Step 15 (Final torque): States 28→29→1
        }

        # Build step rows
        for step_name, description, states, step_type, idx in self.steps:
            row = ttk.Frame(scrollable)
            row.pack(fill=tk.X, pady=3, padx=5)

            # Step label
            label_text = f"{step_name}: {description}"
            label = ttk.Label(row, text=label_text, width=26, anchor="w")
            label.pack(side=tk.LEFT)

            # Type indicator
            type_label = ttk.Label(row, text=f"[{step_type.upper()}]", width=8)
            type_label.pack(side=tk.LEFT, padx=2)

            ok_btn = None
            notok_btn = None
            lhs_qr_btn = None
            rhs_qr_btn = None
            reject_qr_btn = None

            if step_type == "vision":
                if idx == 0:
                    # Special buttons for QR Code step
                    lhs_qr_btn = ttk.Button(row, text="Send LHS QRCode", width=16,
                                           command=lambda: self._send_qr_code("LHS"))
                    lhs_qr_btn.pack(side=tk.LEFT, padx=2)

                    rhs_qr_btn = ttk.Button(row, text="Send RHS QRCode", width=16,
                                           command=lambda: self._send_qr_code("RHS"))
                    rhs_qr_btn.pack(side=tk.LEFT, padx=2)

                    # Add a reject button for testing failures
                    reject_qr_btn = ttk.Button(row, text="Reject QR", width=10,
                                              command=lambda: self._reject_qr_code())
                    reject_qr_btn.pack(side=tk.LEFT, padx=2)
                else:
                    # OK button for other vision steps
                    ok_btn = ttk.Button(row, text="OK", width=6,
                                        command=lambda i=idx: self._send_ok(i))
                    ok_btn.pack(side=tk.LEFT, padx=2)

                    # NotOK button
                    notok_btn = ttk.Button(row, text="Not OK", width=8,
                                           command=lambda i=idx: self._send_notok(i))
                    notok_btn.pack(side=tk.LEFT, padx=2)
            else:
                # Signal steps - no response needed, add spacer
                ttk.Label(row, text="", width=44).pack(side=tk.LEFT)

            # Status label (width=50)
            status_lbl = ttk.Label(row, text="Waiting...", width=50, anchor="w", foreground="gray")
            status_lbl.pack(side=tk.LEFT, padx=5)

            # Store widget references
            self.step_widgets[idx] = {
                'ok': ok_btn,
                'notok': notok_btn,
                'lhs_qr': lhs_qr_btn,
                'rhs_qr': rhs_qr_btn,
                'reject_qr': reject_qr_btn,
                'status': status_lbl,
                'type': step_type
            }

        # Quick actions frame
        actions_frame = ttk.LabelFrame(parent, text="Quick Actions", padding="10")
        actions_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(actions_frame, text="Clear Redis",
                   command=self._clear_redis).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Run Full Cycle (All OK)",
                   command=self._run_full_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Send Next OK",
                   command=self._send_next_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Reset to Step 0",
                   command=self._reset_to_start).pack(side=tk.LEFT, padx=5)

    def _build_tag_display(self, parent):
        """Build the right panel for tag display."""
        # Button frame at top
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)

        self.get_tags_btn = ttk.Button(btn_frame, text="Get Tag Values",
                                        command=self._request_tag_values)
        self.get_tags_btn.pack(side=tk.LEFT, padx=5)

        self.tag_status_label = ttk.Label(btn_frame, text="", font=("Arial", 9))
        self.tag_status_label.pack(side=tk.LEFT, padx=10)

        # Scrolled text for tag display
        self.tag_display = scrolledtext.ScrolledText(parent, font=("Courier", 9), wrap=tk.WORD)
        self.tag_display.pack(fill=tk.BOTH, expand=True)

        # Initial message
        self._show_initial_tag_message()

    def _show_initial_tag_message(self):
        """Show initial message in tag display."""
        self.tag_display.delete(1.0, tk.END)
        msg = """Click 'Get Tag Values' to fetch current
PLC tag values from IOServer.

Requirements:
• IOServer must be running
• IOServer must be connected to PLC
• IOServer must have the tag request
  listener thread running

The tags will be grouped by process
step for easy reading.
"""
        self.tag_display.insert(tk.END, msg)

    def _request_tag_values(self):
        """Request tag values from IOServer via Redis queue."""
        if self.tag_request_pending:
            return

        self.tag_request_pending = True
        self.get_tags_btn.config(state='disabled')
        self.tag_status_label.config(text="Requesting...", foreground="orange")

        def fetch_tags():
            try:
                # Send request
                testRedisConnection.lpush(PUBLISH_TAGS_QUEUE, "getTagValues")

                # Wait for response with timeout
                response = testRedisConnection.brpop(RECEIVE_TAGS_QUEUE, timeout=5)

                if response:
                    _, data = response
                    tags = json.loads(data)

                    # Update display on main thread
                    self.root.after(0, lambda: self._display_tags(tags))
                    self.root.after(0, lambda: self.tag_status_label.config(
                        text=f"Updated: {time.strftime('%H:%M:%S')}", foreground="green"))

                    # Also print to terminal
                    self._print_tags_to_terminal(tags)
                else:
                    self.root.after(0, lambda: self.tag_status_label.config(
                        text="Timeout - no response", foreground="red"))

            except Exception as e:
                self.root.after(0, lambda: self.tag_status_label.config(
                    text=f"Error: {str(e)[:30]}", foreground="red"))
            finally:
                self.tag_request_pending = False
                self.root.after(0, lambda: self.get_tags_btn.config(state='normal'))

        thread = threading.Thread(target=fetch_tags, daemon=True)
        thread.start()

    def _display_tags(self, tags: dict):
        """Display tag values in the right panel, grouped by state."""
        text = self._format_tags_grouped(tags)
        self.tag_display.delete(1.0, tk.END)
        self.tag_display.insert(tk.END, text)

    def _format_tags_grouped(self, tags: dict) -> str:
        """Format tags grouped by state for display."""
        lines = []
        lines.append("PLC TAG VALUES")
        lines.append("═" * 40)
        lines.append(f"Fetched: {time.strftime('%H:%M:%S')}")

        # Show current machine state if available
        if "_currentMachineState" in tags:
            state_str = tags["_currentMachineState"]
            # Shorten state name for display
            short_state = state_str.replace("MachineState.", "")
            lines.append(f"State: {short_state}")

        lines.append("═" * 40)
        lines.append("")

        # Group definitions with partial tag name matches
        groups = [
            ("Step 0: QR Code", ["CheckQRCode", "QRCodeCheckOK", "QRCodeCheckDone"]),
            ("Rotation Settings", ["NoOfRotation1CCW", "NoOfRotation1CW", "NoOfRotation2CCW", "NoOfRotation2CW", "LH_RH_Selection", "RotationUnitRPM"]),
            ("Step 1: Knuckle", ["CheckKnuckle", "KnuckleCheckOK", "KnuckleCheckDone"]),
            ("Step 2: Hub", ["CheckHub", "HubCheckOK", "HubCheckDone"]),
            ("Step 3: Hub+2nd Bearing", ["CheckHubAndSecond", "HubAndSecondBearingCheckOK", "HubAndSecondBearingCheckDone"]),
            ("Step 4: Nut+Plate Washer", ["CheckNutAndPlate", "NutAndPlateWasherCheckOK", "NutAndPlateWasherCheckDone"]),
            ("Step 5 & 10: Station2 Torque", ["Station2TorqueValueSet", "Station2TorqueValue"]),
            ("Step 6: Free Rotation", ["Station3RotationDone"]),
            ("Step 7: No Cap Bunk", ["CheckNoCapBung", "NoCapBungCheckOK", "NoCapBungCheckDone"]),
            ("Step 8: Component Press", ["ComponentPressDone"]),
            ("Step 9: No Bung", ["CheckNoBung", "NoBungCheckOK", "NoBungCheckDone"]),
            ("Step 11: Split Pin+Washer", ["CheckSplitPin", "SplitPinAndWasherCheckOK", "SplitPinAndWasherCheckDone"]),
            ("Step 12: Cap", ["CheckCap", "CapCheckOK", "CapCheckDone"]),
            ("Step 13: Bung", ["CheckBunk", "BungCheckOK", "BungCheckDone"]),
            ("Step 14: Cap Press", ["CapPressDone"]),
            ("Step 15: Station3 Torque", ["Station3TorqueValueSet", "Station3TorqueValue"]),
            ("System", ["EmergencyAbort", "WatchTag"]),
        ]

        for group_name, patterns in groups:
            lines.append(f"▶ {group_name}")
            lines.append("─" * 38)

            found_any = False
            for full_tag, value in sorted(tags.items()):
                if full_tag.startswith("_"):
                    continue  # Skip internal keys
                for pattern in patterns:
                    if pattern in full_tag:
                        found_any = True
                        # Format value
                        if isinstance(value, bool):
                            val_str = "TRUE ●" if value else "False ○"
                        elif isinstance(value, float):
                            val_str = f"{value:.2f}"
                        elif value is None:
                            val_str = "None"
                        else:
                            val_str = str(value)

                        # Shorten tag name for display
                        short_tag = full_tag.split(".")[-1] if "." in full_tag else full_tag
                        # Further shorten if needed
                        if len(short_tag) > 30:
                            short_tag = "..." + short_tag[-27:]
                        lines.append(f"  {short_tag}:")
                        lines.append(f"    {val_str}")
                        break

            if not found_any:
                lines.append("  (no data)")
            lines.append("")

        return "\n".join(lines)

    def _print_tags_to_terminal(self, tags: dict):
        """Print all PLC tag values to terminal."""
        print("\n" + "=" * 70)
        print("PLC TAG VALUES (from IOServer)")
        print("=" * 70)

        if "_currentMachineState" in tags:
            print(f"Current State: {tags['_currentMachineState']}")
            print("-" * 70)

        # Print grouped
        groups = [
            ("Step 0: QR Code", ["QRCode"]),
            ("Rotation Settings", ["Rotation", "LH_RH", "RPM"]),
            ("Step 1: Knuckle", ["Knuckle"]),
            ("Step 2: Hub", ["CheckHub", "HubCheck"]),
            ("Step 3: Hub+2nd Bearing", ["HubAndSecondBearing"]),
            ("Step 4: Nut+Plate Washer", ["NutAndPlateWasher"]),
            ("Step 5 & 10: Station2 Torque", ["Station2Torque"]),
            ("Step 6: Free Rotation", ["Station3RotationDone"]),
            ("Step 7: No Cap Bung", ["NoCapBung"]),
            ("Step 8: Component Press", ["ComponentPressDone"]),
            ("Step 9: No Bung", ["NoBung"]),
            ("Step 11: Split Pin+Washer", ["SplitPinAndWasher"]),
            ("Step 12: Cap", ["CheckCap", "CapCheck"]),
            ("Step 13: Bung", ["CheckBunk", "BungCheck"]),
            ("Step 14: Cap Press", ["CapPressDone"]),
            ("Step 15: Station3 Torque", ["Station3Torque"]),
            ("System", ["Emergency", "Watch"]),
        ]

        for group_name, patterns in groups:
            print(f"\n▶ {group_name}")
            print("-" * 50)
            for tag, value in sorted(tags.items()):
                if tag.startswith("_"):
                    continue
                for pattern in patterns:
                    if pattern in tag:
                        if isinstance(value, bool):
                            val_str = "TRUE ●" if value else "False ○"
                        elif isinstance(value, float):
                            val_str = f"{value:.2f}"
                        else:
                            val_str = str(value)
                        short_tag = tag.split(".")[-1] if "." in tag else tag
                        print(f"  {short_tag}: {val_str}")
                        break

        print("\n" + "=" * 70)

    def _update_status(self, message):
        """Update the status text area."""
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)

    def _update_button_states(self):
        """Enable/disable buttons based on current step."""
        for idx, widgets in self.step_widgets.items():
            if widgets['type'] == "vision":
                if idx == self.current_step and not self.signal_monitor_active:
                    # Enable buttons for current vision step (only if not waiting for signals)
                    if idx == 0:
                        # Enable QR code buttons for step 0
                        if widgets['lhs_qr']:
                            widgets['lhs_qr'].config(state='normal')
                        if widgets['rhs_qr']:
                            widgets['rhs_qr'].config(state='normal')
                        if widgets['reject_qr']:
                            widgets['reject_qr'].config(state='normal')
                    else:
                        # Enable OK/NotOK buttons for other vision steps
                        if widgets['ok']:
                            widgets['ok'].config(state='normal')
                        if widgets['notok']:
                            widgets['notok'].config(state='normal')
                else:
                    # Disable buttons for other steps
                    if idx == 0:
                        if widgets['lhs_qr']:
                            widgets['lhs_qr'].config(state='disabled')
                        if widgets['rhs_qr']:
                            widgets['rhs_qr'].config(state='disabled')
                        if widgets['reject_qr']:
                            widgets['reject_qr'].config(state='disabled')
                    else:
                        if widgets['ok']:
                            widgets['ok'].config(state='disabled')
                        if widgets['notok']:
                            widgets['notok'].config(state='disabled')

    def _start_heartbeat(self):
        """Send heartbeat to keep IOServer happy."""

        def heartbeat():
            while True:
                try:
                    sendCombinedHeartbeatFromHeartbeatServerToIOServer(testRedisConnection, ALIVE)
                except:
                    pass
                time.sleep(1)

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()

    def _get_ioserver_current_state(self) -> MachineState:
        """Request current machine state from IOServer via Redis."""
        try:
            # Send request
            testRedisConnection.lpush(PUBLISH_TAGS_QUEUE, "getTagValues")

            # Wait for response with timeout
            response = testRedisConnection.brpop(RECEIVE_TAGS_QUEUE, timeout=3)

            if response:
                _, data = response
                tags = json.loads(data)

                if "_currentMachineState" in tags:
                    state_str = tags["_currentMachineState"]
                    # Parse the state string to get the MachineState enum
                    # Format is like "MachineState.READ_QR_CODE" or just the enum name
                    state_name = state_str.replace("MachineState.", "")
                    try:
                        return MachineState[state_name]
                    except KeyError:
                        pass
        except Exception as e:
            self._update_status(f"Error getting IOServer state: {e}")

        return MachineState.INVALID_STATE

    def _monitor_signal_steps(self, start_step_idx: int):
        """
        Monitor IOServer state and update GUI when signal steps complete.
        This runs in a background thread.
        """
        self.signal_monitor_active = True
        self.stop_signal_monitor = False

        current_signal_step = start_step_idx

        while current_signal_step < len(self.steps) and not self.stop_signal_monitor:
            step_name, description, states, step_type, idx = self.steps[current_signal_step]

            if step_type != "signal":
                # Reached a vision step, stop monitoring
                break

            # Update GUI to show waiting
            self.root.after(0, lambda i=current_signal_step: self.step_widgets[i]['status'].config(
                text="⏳ Waiting for PLC...", foreground="orange"))

            # Get the completion state for this signal step
            completion_state = self.signal_completion_state_map.get(current_signal_step)

            if completion_state is None:
                # Unknown signal step, just mark as done and continue
                self.root.after(0, lambda i=current_signal_step: self.step_widgets[i]['status'].config(
                    text="✓ Signal step (PLC handled)", foreground="green"))
                current_signal_step += 1
                continue

            # Poll IOServer state until we reach or pass the completion state
            self.root.after(0, lambda sn=step_name, desc=description: self._update_status(
                f"Waiting for {sn}: {desc}..."))

            while not self.stop_signal_monitor:
                current_io_state = self._get_ioserver_current_state()

                if current_io_state == MachineState.INVALID_STATE:
                    # Couldn't get state, wait and retry
                    time.sleep(0.5)
                    continue

                current_io_state_int = MachineState.getMachineStateAsInt(current_io_state)
                completion_state_int = MachineState.getMachineStateAsInt(completion_state)

                # Special handling for cycle wrap-around (Step 15 -> Step 0)
                if current_signal_step == 15:
                    # Cycle complete when we're back at READ_QR_CODE (state 1)
                    if current_io_state == MachineState.READ_QR_CODE:
                        break
                else:
                    # Normal case: signal step complete when IOServer state >= completion state
                    if current_io_state_int >= completion_state_int:
                        break

                # Update status with current IOServer state (less frequently to reduce spam)
                # self.root.after(0, lambda s=current_io_state: self._update_status(
                #     f"IOServer at state: {s.name}"))

                time.sleep(0.5)  # Poll every 500ms

            if self.stop_signal_monitor:
                break

            # Signal step complete - capture values for lambda
            completed_step = current_signal_step
            completed_name = step_name
            self.root.after(0, lambda i=completed_step: self.step_widgets[i]['status'].config(
                text="✓ Complete (PLC done)", foreground="green"))
            self.root.after(0, lambda sn=completed_name: self._update_status(f"{sn} completed!"))

            current_signal_step += 1

        # Update current_step and enable next vision step
        self.current_step = current_signal_step
        self.signal_monitor_active = False

        # Update button states on main thread
        self.root.after(0, self._update_button_states)

        if current_signal_step < len(self.steps):
            next_step = self.steps[current_signal_step]
            self.root.after(0, lambda ns=next_step: self._update_status(
                f"Ready for {ns[0]}: {ns[1]}"))

    def _send_qr_code(self, qr_type: str):
        """Send QR code to IOServer mimicking QRCodeServer."""
        widgets = self.step_widgets[0]

        # Select the appropriate QR code based on type
        qr_code = self.qr_lhs if qr_type == "LHS" else self.qr_rhs

        # Send to IOServer
        sendDataFromQRCodeServerToIOServer(testRedisConnection, qrCodeStatus=ok, qrCode=qr_code)

        # Update status
        widgets['status'].config(text=f"Sent {qr_type} QR code → IOServer processing...", foreground="green")
        self._update_status(f"Step 0: QR Code - Sent {qr_type} QR code: {qr_code[:50]}...")

        # Move to next step
        next_step_idx = 1

        # Check if next step(s) are signal steps
        if next_step_idx < len(self.steps) and self.steps[next_step_idx][3] == "signal":
            # Start background thread to monitor signal steps
            self.current_step = next_step_idx
            self._update_button_states()  # Disable all buttons while waiting

            monitor_thread = threading.Thread(
                target=self._monitor_signal_steps,
                args=(next_step_idx,),
                daemon=True
            )
            monitor_thread.start()
        else:
            # Next step is a vision step, just advance
            self.current_step = next_step_idx
            self._update_button_states()

    def _reject_qr_code(self):
        """Send QR code rejection to IOServer mimicking QRCodeServer failure."""
        widgets = self.step_widgets[0]

        # Send rejection to IOServer
        sendDataFromQRCodeServerToIOServer(testRedisConnection, qrCodeStatus=notok, qrCode="")

        # Update status
        widgets['status'].config(text="QR code rejected → IOServer will retry", foreground="red")
        self._update_status("Step 0: QR Code - Rejection sent, IOServer will stay at this step")

        # Don't advance step - stay at step 0

    def _send_ok(self, step_idx):
        """Send OK response for a vision step."""
        step_name, description, _, step_type, _ = self.steps[step_idx]
        widgets = self.step_widgets[step_idx]

        if step_type != "vision":
            self._update_status(f"{step_name} is a signal step - no response needed")
            return

        if step_idx == 0:
            # QR Code step has dedicated buttons now, this shouldn't be called
            self._update_status("Use 'Send LHS QRCode' or 'Send RHS QRCode' buttons for QR code")
            return

        # Camera vision check
        state = self.vision_state_map.get(step_idx)
        if state:
            sendDataFromCameraServerToIOServer(testRedisConnection, result=ok,
                                               currentMachineState=state)
        widgets['status'].config(text="OK sent → Moving to next step", foreground="green")
        self._update_status(f"{step_name}: {description} - OK sent")

        # Move to next step
        next_step_idx = step_idx + 1

        # Check if next step(s) are signal steps
        if next_step_idx < len(self.steps) and self.steps[next_step_idx][3] == "signal":
            # Start background thread to monitor signal steps
            self.current_step = next_step_idx
            self._update_button_states()  # Disable all buttons while waiting

            monitor_thread = threading.Thread(
                target=self._monitor_signal_steps,
                args=(next_step_idx,),
                daemon=True
            )
            monitor_thread.start()
        else:
            # Next step is a vision step, just advance
            self.current_step = next_step_idx
            self._update_button_states()

    def _send_notok(self, step_idx):
        """Send NotOK response for a vision step."""
        step_name, description, _, step_type, _ = self.steps[step_idx]
        widgets = self.step_widgets[step_idx]

        if step_type != "vision":
            self._update_status(f"{step_name} is a signal step - no response needed")
            return

        if step_idx == 0:
            # QR Code step has dedicated buttons now, this shouldn't be called
            self._update_status("Use 'Send LHS QRCode' or 'Send RHS QRCode' buttons for QR code")
            return

        # Camera vision check
        state = self.vision_state_map.get(step_idx)
        if state:
            sendDataFromCameraServerToIOServer(testRedisConnection, result=notok,
                                               currentMachineState=state)
        widgets['status'].config(text="NotOK sent → Staying at this step", foreground="red")
        self._update_status(f"{step_name}: {description} - NotOK sent (will retry)")

    def _send_next_ok(self):
        """Send OK for the next vision step in sequence."""
        if self.signal_monitor_active:
            self._update_status("Waiting for signal steps to complete...")
            return

        # Find next vision step
        while self.current_step < len(self.steps):
            _, _, _, step_type, _ = self.steps[self.current_step]
            if step_type == "vision":
                self._send_ok(self.current_step)
                return
            self.current_step += 1
            self._update_button_states()

        # Cycle complete, reset
        self._reset_to_start()
        self._update_status("Cycle complete! Reset to Step 0")

    def _clear_redis(self):
        self.stop_signal_monitor = True  # Stop any active monitoring
        time.sleep(0.2)  # Give monitor thread time to stop
        testRedisConnection.flushdb()
        self._reset_to_start()
        self._show_initial_tag_message()
        self.tag_status_label.config(text="")
        self._update_status("Redis cleared - ready for new cycle")

    def _reset_to_start(self):
        """Reset tracking to Step 0."""
        self.stop_signal_monitor = True  # Stop any active monitoring
        self.signal_monitor_active = False
        self.current_step = 0
        for idx, widgets in self.step_widgets.items():
            widgets['status'].config(text="Waiting...", foreground="gray")
        self._update_button_states()
        self._update_status("Reset to Step 0 - Ready")

    def _run_full_cycle(self):
        """Run through all vision steps with OK responses."""
        if self.signal_monitor_active:
            self._update_status("Cannot run full cycle while waiting for signal steps")
            return

        def cycle():
            vision_steps = [
                (0, "QR Code", "qr"),
                (1, "Knuckle", "vision"),
                (2, "Hub", "vision"),
                (3, "Hub + 2nd Bearing", "vision"),
                (4, "Nut + Plate Washer", "vision"),
                (7, "No Cap Bung", "vision"),
                (9, "No Bung", "vision"),
                (11, "Split Pin + Washer", "vision"),
                (12, "Cap", "vision"),
                (13, "Bung", "vision"),
            ]

            for idx, name, step_category in vision_steps:
                # Wait if signal monitoring is active
                while self.signal_monitor_active:
                    time.sleep(0.5)

                self._update_status(f"Sending response for: {name}...")

                if step_category == "qr":
                    # Send LHS QR code for auto cycle
                    self.root.after(0, lambda: self._send_qr_code("LHS"))
                else:
                    self.root.after(0, lambda i=idx: self._send_ok(i))

                # Wait for this step and any signal steps to complete
                time.sleep(1.0)
                while self.signal_monitor_active:
                    time.sleep(0.5)

            self._update_status("Full cycle complete! All OK responses sent.")

        thread = threading.Thread(target=cycle, daemon=True)
        thread.start()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("IOServer Test Script - Real PLC Mode")
    print("=" * 60)
    print("\nThis script works WITH IOServer connected to real PLC.")
    print("It sends OK/NotOK responses and properly waits for signal steps.")
    print("\nSignal steps (torque, press, etc.) are handled by PLC hardware.")
    print("The script will poll IOServer state and wait for them to complete.\n")

    root = tk.Tk()
    app = IOServerTestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()