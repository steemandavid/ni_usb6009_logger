"""Output writers, moved verbatim from the original cli.py."""
import csv
from pathlib import Path


class BaseWriter:
    def write_header(self, header): ...
    def write_row(self, row): ...
    def flush(self): ...
    def close(self): ...


class CSVWriter(BaseWriter):
    def __init__(self, path: Path):
        self._f = path.open("w", newline="")
        self._writer = csv.writer(self._f)
    def write_header(self, header): self._writer.writerow(header); self._f.flush()
    def write_row(self, row): self._writer.writerow(row)
    def flush(self): self._f.flush()
    def close(self):
        if self._f.closed:
            return
        try: self._f.flush()
        finally: self._f.close()


class XLSXWriter(BaseWriter):
    def __init__(self, path: Path, sheet_name="DAQ"):
        try:
            from openpyxl import Workbook
        except ImportError:
            print("Excel output requires 'openpyxl'. Install with: pip install openpyxl")
            raise
        self._path = path
        self._wb = Workbook(write_only=True)
        self._ws = self._wb.create_sheet(title=sheet_name)
        self._save_attempted = False
        if len(self._wb._sheets) > 1 and self._wb._sheets[0].title != sheet_name:
            self._wb.remove(self._wb._sheets[0])
    def write_header(self, header): self._ws.append(header)
    def write_row(self, row): self._ws.append(row)
    def flush(self): pass
    def close(self):
        # The flag is set *before* saving: session.py calls close() twice (once
        # on the happy path, once from its finally). Retrying a failed save
        # would raise a second time and mask the original exception.
        if self._save_attempted:
            return
        self._save_attempted = True
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._wb.save(str(self._path))


class TeeWriter(BaseWriter):
    """Write every row to a main writer and a flush-every-chunk recovery CSV.

    The recovery sink must be a CSVWriter: XLSX only reaches disk in close(),
    which makes it useless as the crash copy.
    """

    def __init__(self, main: BaseWriter, recovery: CSVWriter):
        self.main = main
        self.recovery = recovery

    def write_header(self, header):
        self.main.write_header(header)
        self.recovery.write_header(header)

    def write_row(self, row):
        self.main.write_row(row)
        self.recovery.write_row(row)

    def flush(self):
        self.main.flush()
        self.recovery.flush()

    def close(self):
        # The recovery copy must reach disk even when the main writer's close
        # fails — a failing XLSX save is exactly when the crash copy matters.
        try:
            self.main.close()
        finally:
            self.recovery.close()


def make_writer(path: Path, fmt: str, sheet_name: str = "DAQ") -> BaseWriter:
    if fmt == "xlsx":
        return XLSXWriter(path, sheet_name=sheet_name)
    return CSVWriter(path)
