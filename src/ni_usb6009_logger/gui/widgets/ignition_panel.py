"""Ignition safety panel: state LEDs, ARM confirmation, hold-to-fire, ABORT.

The panel is a dumb view: the core session owns every hardware failsafe
(leak inhibit, continuity check, fire-confirm). This widget only
- asks for confirmation before starting the armed sequence,
- requires a deliberate 2-second hold on FIRE before granting permission,
- offers ABORT at every moment (which also forces the DO lines LOW via the
  core's finally path).
"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ni_usb6009_logger.core.events import SessionState

HOLD_SECONDS = 2.0


class _Led(QLabel):
    def __init__(self, label):
        super().__init__(f"● {label}")
        self.set_state("off")

    def set_state(self, state):  # off | ok | warn | bad
        colors = {"off": "#9e9e9e", "ok": "#2ca02c", "warn": "#ff7f0e", "bad": "#d62728"}
        self.setStyleSheet(f"color: {colors[state]}; font-weight: bold;")


class IgnitionPanel(QWidget):
    fire_permission_requested = Signal()
    abort_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        # -- status LEDs ----------------------------------------------------
        status = QGroupBox("Safety status")
        grid = QGridLayout(status)
        self.led_do = _Led("DO lines LOW")
        self.led_continuity = _Led("Continuity")
        self.led_leak = _Led("No leak current")
        self.led_fire = _Led("Igniter relay")
        grid.addWidget(self.led_do, 0, 0)
        grid.addWidget(self.led_continuity, 0, 1)
        grid.addWidget(self.led_leak, 1, 0)
        grid.addWidget(self.led_fire, 1, 1)
        self.arm_status = QLabel("Idle")
        grid.addWidget(self.arm_status, 2, 0, 1, 2)
        lay.addWidget(status)

        # -- hold-to-fire progress -----------------------------------------
        self.hold_progress = QProgressBar()
        self.hold_progress.setRange(0, 100)
        self.hold_progress.setValue(0)
        self.hold_progress.setFormat("hold FIRE for 2 s to ignite")
        lay.addWidget(self.hold_progress)

        # -- buttons ---------------------------------------------------------
        btns = QVBoxLayout()
        self.arm_btn = QPushButton("ARM")
        self.arm_btn.setMinimumHeight(60)
        self.arm_btn.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.arm_btn.clicked.connect(self._confirm_arm)

        self.fire_btn = QPushButton("FIRE")
        self.fire_btn.setMinimumHeight(60)
        self.fire_btn.setEnabled(False)
        self.fire_btn.setStyleSheet(
            "font-size: 16pt; font-weight: bold; background-color: #d62728; color: white;")
        self.fire_btn.pressed.connect(self._hold_start)
        self.fire_btn.released.connect(self._hold_cancel)

        self.abort_btn = QPushButton("ABORT")
        self.abort_btn.setMinimumHeight(44)
        self.abort_btn.setStyleSheet("font-size: 13pt; font-weight: bold;")
        self.abort_btn.clicked.connect(self.abort_requested.emit)

        btns.addWidget(self.arm_btn)
        btns.addWidget(self.fire_btn)
        btns.addWidget(self.abort_btn)
        lay.addLayout(btns)
        lay.addStretch(1)

        self._hold_timer = QTimer(self)
        self._hold_timer.setInterval(50)
        self._hold_timer.timeout.connect(self._hold_tick)
        self._held = False
        self._session_active = False
        self._last_state = None
        self.interactive = True  # False (CI/offscreen): auto-confirm dialogs

    # ------------------------------------------------------------- arming
    def _confirm_arm(self):
        if self._session_active:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Arm ignition?")
        box.setText(
            "The buzzer will now sound as a warning while the system checks\n"
            "the igniter. The relay stays OFF during this check.\n\n"
            "The test starts logging immediately after the check passes.\n"
            "FIRE only becomes available after stabilization, and needs a\n"
            "2-second hold. ABORT is available at any time.")
        ok = box.addButton("Arm — sound buzzer", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        if not self.interactive:
            box.deleteLater()
            result = ok
        else:
            box.exec()
            result = box.clickedButton()
        if result is ok:
            self._session_active = True
            self.arm_btn.setText("ARMED")
            self.arm_btn.setEnabled(False)
            self.arm_confirmed.emit()

    arm_confirmed = Signal()

    # ---------------------------------------------------------- hold to fire
    def _hold_start(self):
        if self._held:
            return
        self._hold_timer.start()

    def _hold_cancel(self):
        self._hold_timer.stop()
        if not self._held:
            self.hold_progress.setValue(0)

    def _hold_tick(self):
        if self._held:
            return
        value = self.hold_progress.value() + (50 / (HOLD_SECONDS * 1000)) * 100
        self.hold_progress.setValue(int(min(value, 100)))
        if value >= 100:
            self._held = True
            self._hold_timer.stop()
            self.hold_progress.setFormat("FIRE PERMISSION GRANTED")
            self.fire_permission_requested.emit()

    # ------------------------------------------------------------- states
    def reset(self):
        self._hold_timer.stop()
        self._held = False
        self._session_active = False
        self._last_state = None
        self.hold_progress.setValue(0)
        self.hold_progress.setFormat("hold FIRE for 2 s to ignite")
        self.arm_status.setText("Idle")
        self.led_do.set_state("ok")
        self.led_continuity.set_state("off")
        self.led_leak.set_state("off")
        self.led_fire.set_state("off")
        self.arm_btn.setText("ARM")
        self.arm_btn.setEnabled(True)
        self.fire_btn.setEnabled(False)

    def set_session_state(self, state: SessionState):
        self._last_state = state
        if state == SessionState.STARTING:
            self.arm_status.setText("Preparing (DO lines forced LOW)…")
            self.led_do.set_state("ok")
        elif state == SessionState.ARMING:
            self.arm_status.setText("ARMING — buzzer sounding, checking igniter…")
            self.led_continuity.set_state("warn")
        elif state == SessionState.LOGGING:
            self.arm_status.setText("Logging… waiting for stabilization before FIRE")
            self.led_do.set_state("off")
            self.led_fire.set_state("off")
        elif state == SessionState.FIRE_PENDING:
            self.arm_status.setText("STABILIZED — FIRE available (hold 2 s)")
            self.fire_btn.setEnabled(True)
        elif state == SessionState.FIRED:
            self.arm_status.setText("FIRING — relay ON")
            self.led_fire.set_state("bad")
            self.fire_btn.setEnabled(False)
            self._hold_timer.stop()
        elif state == SessionState.INHIBITED:
            self.arm_status.setText("INHIBITED by safety failsafe — see log")
            self.led_fire.set_state("bad")
            self.fire_btn.setEnabled(False)
        elif state in (SessionState.DONE, SessionState.ABORTED, SessionState.ERROR):
            self.arm_status.setText({SessionState.DONE: "Done — DO lines LOW",
                                     SessionState.ABORTED: "Aborted — DO lines LOW",
                                     SessionState.ERROR: "Error — DO lines LOW"}.get(
                                        state, "Ended — DO lines LOW"))
            self.led_do.set_state("ok")
            self.led_fire.set_state("off")
            self.fire_btn.setEnabled(False)

    def set_arming(self, remaining: float, current_ma):
        if current_ma is None:
            self.arm_status.setText(f"ARMING — {remaining:5.1f}s remaining")
        else:
            self.arm_status.setText(
                f"ARMING — {remaining:5.1f}s | igniter current {current_ma:7.2f} mA")
            self.led_continuity.set_state("ok" if current_ma >= 0.2 else "warn")
            self.led_leak.set_state("warn" if current_ma >= 5.0 else "ok")
