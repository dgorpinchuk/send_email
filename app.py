"""PySide6 desktop UI for HTML email campaigns."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QSpinBox, QTextBrowser,
    QVBoxLayout, QWidget,
)

from core import profiles
from core.recipients import load, validate
from core.smtp_sender import send_email
from core.template_engine import render, validate_columns, variables_in


class SendWorker(QObject):
    progress = Signal(int, int, str, bool, str)
    finished = Signal(int, int, bool)

    def __init__(self, smtp: dict, rows: list[dict[str, str]], subject: str,
                 sender_name: str, template: str, delay_ms: int = 0):
        super().__init__()
        self.smtp, self.rows = smtp, rows
        self.subject, self.sender_name, self.template = subject, sender_name, template
        self.delay_ms = delay_ms
        self.stop_requested = False

    @Slot()
    def run(self):
        import time
        ok_count = fail_count = 0
        stopped = False
        for index, row in enumerate(self.rows, 1):
            if self.stop_requested:
                stopped = True
                break
            recipient = row.get("email", "")
            try:
                body = render(self.template, row)
                ok, error = send_email(
                    self.smtp["server"], int(self.smtp["port"]), self.smtp["username"],
                    self.smtp["password"], self.smtp["username"], recipient,
                    self.subject, body, self.sender_name,
                )
            except Exception as exc:
                ok, error = False, str(exc)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
            self.progress.emit(index, len(self.rows), recipient, ok, error or "")
            if self.delay_ms:
                time.sleep(self.delay_ms / 1000)
        self.finished.emit(ok_count, fail_count, stopped)


class ProfileDialog(QDialog):
    def __init__(self, parent=None, name=""):
        super().__init__(parent)
        self.setWindowTitle("SMTP profile")
        self.name = QLineEdit(name)
        layout = QFormLayout(self)
        layout.addRow("Profile name", self.name)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def profile_name(self):
        return self.name.text().strip()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SMTP Mail Sender")
        self.resize(1000, 780)
        self.rows: list[dict[str, str]] = []
        self.columns: list[str] = []
        self.template_text = ""
        self.thread = None
        self.worker = None
        self._profile_loading = False
        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        smtp_box = QGroupBox("SMTP profile")
        smtp_grid = QGridLayout(smtp_box)
        self.profile_combo = QComboBox()
        # Use both signals so selecting an item with the mouse/keyboard always
        # causes the saved profile values to be loaded into the fields.
        self.profile_combo.currentIndexChanged.connect(self._profile_index_changed)
        self.profile_combo.activated.connect(self._profile_activated)
        new_profile = QPushButton("New")
        save_profile = QPushButton("Save")
        delete_profile = QPushButton("Delete")
        new_profile.clicked.connect(self.new_profile)
        save_profile.clicked.connect(self.save_profile)
        delete_profile.clicked.connect(self.delete_profile)
        smtp_grid.addWidget(QLabel("Profile"), 0, 0)
        smtp_grid.addWidget(self.profile_combo, 0, 1, 1, 3)
        smtp_grid.addWidget(new_profile, 0, 4)
        smtp_grid.addWidget(save_profile, 0, 5)
        smtp_grid.addWidget(delete_profile, 0, 6)
        self.username = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.server = QLineEdit()
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(465)
        for row, label, widget in [(1, "Username", self.username), (2, "Password", self.password), (3, "Server", self.server), (4, "Port", self.port)]:
            smtp_grid.addWidget(QLabel(label), row, 0)
            smtp_grid.addWidget(widget, row, 1, 1, 6)
        root.addWidget(smtp_box)

        mail_box = QGroupBox("Message")
        form = QGridLayout(mail_box)
        self.sender_name = QLineEdit()
        self.subject = QLineEdit()
        self.html_path = QLineEdit(); self.html_path.setReadOnly(True)
        choose_html = QPushButton("Choose…")
        edit_html = QPushButton("Edit in default editor")
        choose_html.clicked.connect(self.choose_html)
        edit_html.clicked.connect(self.edit_html)
        form.addWidget(QLabel("Sender name"), 0, 0); form.addWidget(self.sender_name, 0, 1, 1, 4)
        form.addWidget(QLabel("Subject"), 1, 0); form.addWidget(self.subject, 1, 1, 1, 4)
        form.addWidget(QLabel("HTML template"), 2, 0); form.addWidget(self.html_path, 2, 1, 1, 2)
        form.addWidget(choose_html, 2, 3); form.addWidget(edit_html, 2, 4)
        root.addWidget(mail_box)

        data_box = QGroupBox("Recipients")
        data = QGridLayout(data_box)
        self.data_path = QLineEdit(); self.data_path.setReadOnly(True)
        choose_data = QPushButton("Choose…"); choose_data.clicked.connect(self.choose_data)
        self.dedupe = QCheckBox("Remove duplicates"); self.dedupe.setChecked(True)
        self.dedupe.stateChanged.connect(lambda: self._read_data() if self.data_path.text() else None)
        data.addWidget(QLabel("Database"), 0, 0); data.addWidget(self.data_path, 0, 1, 1, 2); data.addWidget(choose_data, 0, 3); data.addWidget(self.dedupe, 0, 4)
        self.stats = QLabel("No recipient file selected")
        data.addWidget(self.stats, 1, 0, 1, 5)
        root.addWidget(data_box)

        settings = QHBoxLayout()
        settings.addWidget(QLabel("Delay between emails (ms):"))
        self.delay = QSpinBox(); self.delay.setRange(0, 60000); self.delay.setValue(0); self.delay.setSingleStep(100)
        settings.addWidget(self.delay); settings.addStretch()
        root.addLayout(settings)

        actions = QHBoxLayout()
        self.preview_btn = QPushButton("Preview"); self.preview_btn.clicked.connect(self.preview)
        self.test_address = QLineEdit(); self.test_address.setPlaceholderText("Test recipient")
        self.test_btn = QPushButton("Send test email"); self.test_btn.clicked.connect(self.send_test)
        self.send_btn = QPushButton("START CAMPAIGN"); self.send_btn.clicked.connect(self.start_campaign)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False); self.stop_btn.clicked.connect(self.stop_campaign)
        actions.addWidget(self.preview_btn); actions.addWidget(self.test_address); actions.addWidget(self.test_btn); actions.addStretch(); actions.addWidget(self.stop_btn); actions.addWidget(self.send_btn)
        root.addLayout(actions)

        progress_box = QGroupBox("Progress")
        progress = QVBoxLayout(progress_box)
        self.progress = QProgressBar(); self.progress.setValue(0)
        self.current = QLabel("Ready")
        self.log = QListWidget()
        progress.addWidget(self.progress); progress.addWidget(self.current); progress.addWidget(self.log)
        root.addWidget(progress_box, 1)

        self.setCentralWidget(central)
        menu = self.menuBar().addMenu("Help")
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.information(self, "SMTP Mail Sender", "PySide6 email campaign tool"))
        menu.addAction(about)

    def _load_profiles(self, select_name: str | None = None):
        names = profiles.names()
        current = select_name if select_name is not None else self.profile_combo.currentText()
        self._profile_loading = True
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        if current and current in names:
            self.profile_combo.setCurrentText(current)
        elif names:
            self.profile_combo.setCurrentIndex(0)
        else:
            self._clear_profile_fields()
        self.profile_combo.blockSignals(False)
        self._profile_loading = False

        # Signals were blocked while rebuilding the combo, so explicitly load
        # the selected profile afterwards. This also handles the initial launch.
        selected = self.profile_combo.currentText().strip()
        if selected:
            self.load_profile(selected)

    def _profile_index_changed(self, index: int):
        if self._profile_loading or index < 0:
            return
        self.load_profile(self.profile_combo.itemText(index))

    def _profile_activated(self, index: int):
        if self._profile_loading or index < 0:
            return
        self.load_profile(self.profile_combo.itemText(index))

    def load_profile(self, name: str):
        name = name.strip()
        if not name:
            self._clear_profile_fields()
            return
        try:
            profile = profiles.get(name)
            self.username.setText(str(profile.get("username", "")))
            self.password.setText(str(profile.get("password", "")))
            self.server.setText(str(profile.get("server", "")))
            try:
                self.port.setValue(int(profile.get("port", 465)))
            except (TypeError, ValueError):
                self.port.setValue(465)
        except Exception as exc:
            self._clear_profile_fields()
            QMessageBox.warning(self, "Profile error", f"Cannot load profile '{name}': {exc}")

    def _clear_profile_fields(self):
        self.username.clear()
        self.password.clear()
        self.server.clear()
        self.port.setValue(465)

    def new_profile(self):
        dialog = ProfileDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.profile_name():
            name = dialog.profile_name()
            if name in profiles.names():
                QMessageBox.warning(self, "Profile exists", "Choose a different profile name.")
                return
            profiles.save(name, {"username": "", "password": "", "server": "", "port": 465})
            self._load_profiles(name)
            self.username.setFocus()

    def save_profile(self):
        name = self.profile_combo.currentText().strip()
        if not name:
            self.new_profile()
            name = self.profile_combo.currentText().strip()
        if not name:
            return
        try:
            profiles.save(name, {"username": self.username.text().strip(), "password": self.password.text(), "server": self.server.text().strip(), "port": self.port.value()})
            self._load_profiles(name)
            QMessageBox.information(self, "Saved", f"Profile '{name}' saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))

    def delete_profile(self):
        name = self.profile_combo.currentText().strip()
        if name and QMessageBox.question(self, "Delete profile", f"Delete '{name}'?") == QMessageBox.Yes:
            profiles.remove(name)
            self._load_profiles()

    def choose_html(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose HTML template", "", "HTML files (*.html *.htm);;All files (*)")
        if path:
            self.html_path.setText(path); self._read_template()

    def _read_template(self):
        path = self.html_path.text()
        if path and Path(path).exists():
            self.template_text = Path(path).read_text(encoding="utf-8-sig")
            self._update_stats()

    def edit_html(self):
        path = self.html_path.text()
        if not path:
            self.choose_html(); path = self.html_path.text()
        if not path: return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["start", "", path], shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            QMessageBox.warning(self, "Cannot open editor", str(exc))

    def choose_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose recipient database", "", "Recipient files (*.txt *.csv *.xlsx);;All files (*)")
        if path:
            self.data_path.setText(path); self._read_data()

    def _read_data(self):
        try:
            self.rows, self.columns = load(self.data_path.text(), self.dedupe.isChecked())
            self._update_stats()
        except Exception as exc:
            self.rows, self.columns = [], []
            QMessageBox.critical(self, "Recipient file error", str(exc))

    def _update_stats(self):
        if not self.data_path.text(): return
        if self.rows:
            valid, invalid = validate(self.rows)
            vars_ = variables_in(self.template_text)
            missing = validate_columns(self.template_text, self.columns) if vars_ else []
            text = f"{len(self.rows)} rows · {len(valid)} valid · {len(invalid)} invalid"
            if vars_: text += f" · variables: {', '.join(vars_)}"
            if missing: text += f" · MISSING COLUMNS: {', '.join(missing)}"
            self.stats.setText(text)

    def _ensure_ready(self, test=False):
        self._read_template()
        if not self.template_text: raise ValueError("Choose an HTML template")
        if not self.username.text().strip() or not self.password.text() or not self.server.text().strip(): raise ValueError("Complete SMTP settings")
        if not self.subject.text().strip(): raise ValueError("Subject cannot be empty")
        if test: return
        if not self.rows: self._read_data()
        if not self.rows: raise ValueError("Choose a recipient database")
        missing = validate_columns(self.template_text, self.columns)
        if missing: raise ValueError("Missing columns: " + ", ".join(missing))
        valid, invalid = validate(self.rows)
        if invalid: raise ValueError(f"There are {len(invalid)} invalid recipient rows")
        if not valid: raise ValueError("No valid recipients found")

    def preview(self):
        try:
            self._ensure_ready()
            body = render(self.template_text, self.rows[0])
            dialog = QDialog(self); dialog.setWindowTitle("Email preview"); dialog.resize(900, 700)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f"Subject: {self.subject.text()}\nTo: {self.rows[0]['email']}"))
            browser = QTextBrowser(); browser.setHtml(body); layout.addWidget(browser)
            dialog.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Cannot preview", str(exc))

    def send_test(self):
        try:
            self._ensure_ready(test=True)
            address = self.test_address.text().strip()
            if not address: raise ValueError("Enter a test recipient")
            row = self.rows[0] if self.rows else {"email": address}
            body = render(self.template_text, row)
            ok, error = send_email(self.server.text().strip(), self.port.value(), self.username.text().strip(), self.password.text(), self.username.text().strip(), address, self.subject.text().strip(), body, self.sender_name.text().strip() or self.username.text().strip())
            if ok: QMessageBox.information(self, "Test sent", f"Test email sent to {address}.")
            else: raise RuntimeError(error)
        except Exception as exc:
            QMessageBox.critical(self, "Test failed", str(exc))

    def start_campaign(self):
        try:
            self._ensure_ready()
            valid, _ = validate(self.rows)
            if QMessageBox.question(self, "Start campaign", f"Send {len(valid)} emails now?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
            smtp = {"username": self.username.text().strip(), "password": self.password.text(), "server": self.server.text().strip(), "port": self.port.value()}
            self.thread = QThread()
            self.worker = SendWorker(smtp, valid, self.subject.text().strip(), self.sender_name.text().strip() or smtp["username"], self.template_text, self.delay.value())
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.progress.connect(self.on_progress)
            self.worker.finished.connect(self.on_finished)
            self.thread.start()
            self.send_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.preview_btn.setEnabled(False); self.test_btn.setEnabled(False)
            self.log.clear(); self.progress.setValue(0); self.current.setText("Starting…")
        except Exception as exc:
            QMessageBox.warning(self, "Cannot start", str(exc))

    def stop_campaign(self):
        if self.worker: self.worker.stop_requested = True
        self.stop_btn.setEnabled(False)

    @Slot(int, int, str, bool, str)
    def on_progress(self, current, total, recipient, ok, error):
        self.progress.setMaximum(total); self.progress.setValue(current); self.current.setText(f"{current} / {total}: {recipient}")
        self.log.addItem(f"✓ {recipient}" if ok else f"✗ {recipient}: {error}")
        self.log.scrollToBottom()

    @Slot(int, int, bool)
    def on_finished(self, ok, failed, stopped):
        self.send_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.preview_btn.setEnabled(True); self.test_btn.setEnabled(True)
        if self.thread:
            self.thread.quit(); self.thread.wait(); self.thread = self.worker = None
        status = "stopped" if stopped else "finished"
        QMessageBox.information(self, "Campaign " + status, f"Successful: {ok}\nErrors: {failed}" + ("\nCampaign was stopped." if stopped else ""))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow(); window.show()
    sys.exit(app.exec())
