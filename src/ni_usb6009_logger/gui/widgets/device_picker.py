"""Device combo: auto-scan for DAQs, editable so a name can be typed manually."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from ni_usb6009_logger.core import daq


class DevicePicker(QWidget):
    devices_changed = Signal(list)  # [(name, product_type)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setToolTip("DAQ device name as shown in NI MAX (auto-detected)")
        refresh = QPushButton("Refresh")
        refresh.setToolTip("Rescan for connected DAQ devices")
        refresh.clicked.connect(self.rescan)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.combo, 1)
        lay.addWidget(refresh)

    def rescan(self):
        devices = daq.enumerate_devices()
        current = self.current_device()
        self.combo.blockSignals(True)
        self.combo.clear()
        for name, product in devices:
            self.combo.addItem(f"{name} — {product}", userData=name)
        if current:
            index = self._index_of(current)
            if index >= 0:
                self.combo.setCurrentIndex(index)
            elif self.combo.isEditable():
                self.combo.setEditText(current)  # typed name, device not seen (yet)
        self.combo.blockSignals(False)
        self.devices_changed.emit(devices)
        return devices

    def _index_of(self, name: str) -> int:
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == name:
                return i
        return -1

    def current_device(self) -> str:
        text = self.combo.currentText()
        return text.split(" — ")[0].strip() if text else ""
