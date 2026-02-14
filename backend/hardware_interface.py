"""
Vuddy Backend — Hardware Abstraction Layer.
Every hardware call goes through this module. SimHardware is the default.
The backend can always run with no serial device connected.
"""

import os

from backend.constants import ASSISTANT_STATES

HARDWARE_MODE = os.getenv("HARDWARE_MODE", "sim")


class HardwareInterface:
    """Base class for hardware interface."""

    async def set_led_state(self, state: str, color: str = None) -> None:
        """Set LED mode. state: idle|listening|thinking|speaking|error. color: optional hex."""
        raise NotImplementedError

    async def on_button_event(self, callback) -> None:
        """Register callback for button press events."""
        raise NotImplementedError


class SimHardware(HardwareInterface):
    """Default simulator. Logs to console. No real hardware needed."""

    async def set_led_state(self, state: str, color: str = None) -> None:
        print(f"[SIM-HW] LED -> state={state} color={color or 'default'}")

    async def on_button_event(self, callback) -> None:
        pass  # No button in sim mode


class ArduinoHardware(HardwareInterface):
    """Phase 2. Talks to Arduino via serial. Only used if HARDWARE_MODE=arduino."""

    def __init__(self):
        import serial

        port = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
        baud = int(os.getenv("SERIAL_BAUD", "115200"))
        self.ser = serial.Serial(port, baud, timeout=1)
        self._cmd_counter = 0

    async def set_led_state(self, state: str, color: str = None) -> None:
        import json

        self._cmd_counter += 1
        cmd_id = f"c{self._cmd_counter:03d}"
        cmd = {"t": "cmd", "id": cmd_id, "action": "set_status", "state": state}
        if color:
            cmd["color"] = color
        self.ser.write((json.dumps(cmd) + "\n").encode())
        # Wait up to 400ms for ACK, retry once, then fail-open
        self.ser.timeout = 0.4
        response = self.ser.readline().decode().strip()
        if not response:
            # Retry once
            self.ser.write((json.dumps(cmd) + "\n").encode())
            response = self.ser.readline().decode().strip()
        if response:
            try:
                ack = json.loads(response)
                if ack.get("t") == "ack" and ack.get("ok"):
                    return
            except json.JSONDecodeError:
                pass
        # Fail-open: log and continue
        print(f"[HW] Arduino ACK timeout for cmd {cmd_id}, continuing")

    async def on_button_event(self, callback) -> None:
        # In a real implementation, this would start a background reader
        # For Phase 2 implementation
        pass


def create_hardware() -> HardwareInterface:
    """Factory: create hardware interface based on env var."""
    if HARDWARE_MODE == "arduino":
        try:
            return ArduinoHardware()
        except Exception as e:
            print(f"[HW] Arduino init failed ({e}), falling back to SimHardware")
            return SimHardware()
    return SimHardware()
