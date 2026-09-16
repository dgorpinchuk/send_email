"""PySide6 desktop UI for HTML email campaigns."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout, QWidget, QHeaderView,
)

from core import history, profiles
from core.campaign import Campaign, DeliveryResult
from core.recipients import count_duplicates, load, validate
from core.smtp_sender import test_connection
from core.template_engine import render, validate_columns, variables_in


class SendWorker(QObject):
    progress = Signal(int, int, str, bool, str)
    finished = Signal(int, int, bool)
    failed = Signal(str)

    def __init__(self, campaign: Campaign):
        super().__init__()
        self.campaign = campaign
        self.stop_requested = False

    @Slot()
    def run(self):
        try:
            ok, failed, stopped = self.campaign.run(
                on_progress=self._on_progress,
                should_stop=lambda: self.stop_requested,
            )
            self.finished.emit(ok, failed, stopped)
        except Exception as exc:
            self.failed.emit(str(exc))
            self.finished.emit(0, 0, False)

    def _on_progress(self, result: DeliveryResult):
        self.progress.emit(result.index, result.total, result.recipient, result.success, result.error)


class ProfileDialog(QDialog):
    """Dialog used for both creating and editing an SMTP profile."""

    def __init__(self, parent=None, profile_name: str = "", profile: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("New SMTP profile" if not profile_name else "Edit SMTP profile")
        self.setMinimumWidth(520)
        profile = profile or {}
        self.name = QLineEdit(profile_name)
        self.username = QLineEdit(str(profile.get("username", "")))
        self.password = QLineEdit(str(profile.get("password", "")))
        self.password.setEchoMode(QLineEdit.Password)
        self.server = QLineEdit(str(profile.get("server", "")))
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(int(profile.get("port", 465) or 465))
        layout = QFormLayout(self)
        layout.addRow("Profile name", self.name); layout.addRow("Username", self.username)
        layout.addRow("Password", self.password); layout.addRow("Server", self.server); layout.addRow("Port", self.port)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject); layout.addRow(buttons)
        self.name.setFocus()

    def _save(self):
        checks = ((self.profile_name(), "Profile name cannot be empty.", self.name),
                  (self.username.text().strip(), "Username cannot be empty.", self.username),
                  (self.server.text().strip(), "Server cannot be empty.", self.server))
        for value, message, field in checks:
            if not value:
                QMessageBox.warning(self, "Invalid profile", message); field.setFocus(); return
        self.accept()

    def profile_name(self) -> str: return self.name.text().strip()

    def profile_data(self) -> dict:
        return {"username": self.username.text().strip(), "password": self.password.text(),
                "server": self.server.text().strip(), "port": self.port.value()}


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Campaign history"); self.resize(950, 600)
        root = QVBoxLayout(self); self.items = QListWidget(); self.details = QTextBrowser(); self.open_log_btn = QPushButton("Open log file")
        self.open_log_btn.setEnabled(False); root.addWidget(self.items, 1); root.addWidget(self.details, 1); root.addWidget(self.open_log_btn)
        self.items.currentItemChanged.connect(self._show_details); self.open_log_btn.clicked.connect(self._open_log)
        self._history = history.list_history()
        for entry in self._history:
            text = f"{entry.get('started_at', '')} · {entry.get('status', 'unknown')} · {entry.get('subject', '')}"
            item = QListWidgetItem(text); item.setData(0x0100, entry); self.items.addItem(item)
        if self.items.count(): self.items.setCurrentRow(0)
        else: self.details.setText("No campaigns yet.")

    def _show_details(self, item, _previous):
        if not item: self.open_log_btn.setEnabled(False); return
        entry = item.data(0x0100)
        self.details.setPlainText(
            f"Status: {entry.get('status', '')}\nStarted: {entry.get('started_at', '')}\n"
            f"Finished: {entry.get('finished_at') or '—'}\nProfile: {entry.get('profile', '')}\n"
            f"Sender: {entry.get('sender', '')}\nSubject: {entry.get('subject', '')}\n"
            f"Template: {entry.get('template', '')}\nRecipients: {entry.get('recipient_file', '')}\n\n"
            f"Total: {entry.get('total', 0)}\nSuccessful: {entry.get('successful', 0)}\nErrors: {entry.get('failed', 0)}\n\n"
            f"Log: {entry.get('log_file', '')}"
        ); self.open_log_btn.setEnabled(bool(entry.get("log_file")))

    def _open_log(self):
        item = self.items.currentItem()
        if not item: return
        path = item.data(0x0100).get("log_file", "")
        if not path: return
        try:
            if sys.platform == "win32": subprocess.Popen(["start", "", path], shell=True)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except OSError as exc: QMessageBox.warning(self, "Cannot open log", str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("SMTP Mail Sender"); self.resize(1100, 900)
        self.rows: list[dict[str, str]] = []; self.columns: list[str] = []; self.template_text = ""
        self.duplicate_count = 0; self.thread = None; self.worker = None; self.history_entry = None
        self._profile_loading = False; self._build_ui(); self._load_profiles()

    def _build_ui(self):
        central = QWidget(); root = QVBoxLayout(central)
        smtp_box = QGroupBox("SMTP profile"); smtp_grid = QGridLayout(smtp_box)
        self.profile_combo = QComboBox(); self.profile_combo.setMinimumWidth(300); self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        buttons = [("New", self.new_profile), ("Edit", self.edit_profile), ("Delete", self.delete_profile), ("Test SMTP", self.test_smtp)]
        smtp_grid.addWidget(QLabel("Profile"), 0, 0); smtp_grid.addWidget(self.profile_combo, 0, 1)
        for column, (text, slot) in enumerate(buttons, 2):
            button = QPushButton(text); button.clicked.connect(slot); smtp_grid.addWidget(button, 0, column)
        smtp_grid.setColumnStretch(1, 1); self.profile_summary = QLabel("No SMTP profile selected"); smtp_grid.addWidget(self.profile_summary, 1, 1, 1, 5); root.addWidget(smtp_box)

        mail_box = QGroupBox("Message"); form = QGridLayout(mail_box)
        self.sender_name = QLineEdit(); self.subject = QLineEdit(); self.html_path = QLineEdit(); self.html_path.setReadOnly(True)
        choose_html = QPushButton("Choose…"); edit_html = QPushButton("Edit in default editor"); choose_html.clicked.connect(self.choose_html); edit_html.clicked.connect(self.edit_html)
        form.addWidget(QLabel("Sender name"), 0, 0); form.addWidget(self.sender_name, 0, 1, 1, 4); form.addWidget(QLabel("Subject"), 1, 0); form.addWidget(self.subject, 1, 1, 1, 4); form.addWidget(QLabel("HTML template"), 2, 0); form.addWidget(self.html_path, 2, 1, 1, 2); form.addWidget(choose_html, 2, 3); form.addWidget(edit_html, 2, 4); root.addWidget(mail_box)

        data_box = QGroupBox("Recipients"); data = QVBoxLayout(data_box); controls = QHBoxLayout()
        self.data_path = QLineEdit(); self.data_path.setReadOnly(True); choose_data = QPushButton("Choose…"); choose_data.clicked.connect(self.choose_data); self.dedupe = QCheckBox("Remove duplicates"); self.dedupe.setChecked(True); self.dedupe.stateChanged.connect(lambda: self._read_data() if self.data_path.text() else None)
        controls.addWidget(self.data_path, 1); controls.addWidget(choose_data); controls.addWidget(self.dedupe); data.addLayout(controls); self.stats = QLabel("No recipient file selected"); data.addWidget(self.stats)
        self.recipient_table = QTableWidget(0, 0); self.recipient_table.setAlternatingRowColors(True); self.recipient_table.setEditTriggers(QTableWidget.NoEditTriggers); self.recipient_table.setSelectionBehavior(QTableWidget.SelectRows); self.recipient_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.recipient_table.horizontalHeader().setStretchLastSection(True); data.addWidget(self.recipient_table, 1); root.addWidget(data_box, 1)

        settings = QHBoxLayout(); settings.addWidget(QLabel("Delay between emails (ms):")); self.delay = QSpinBox(); self.delay.setRange(0, 60000); self.delay.setValue(0); self.delay.setSingleStep(100); settings.addWidget(self.delay); settings.addStretch(); root.addLayout(settings)
        actions = QHBoxLayout(); self.preview_btn = QPushButton("Preview"); self.preview_btn.clicked.connect(self.preview); self.test_address = QLineEdit(); self.test_address.setPlaceholderText("Test recipient"); self.test_btn = QPushButton("Send test email"); self.test_btn.clicked.connect(self.send_test); self.history_btn = QPushButton("History"); self.history_btn.clicked.connect(self.show_history); self.send_btn = QPushButton("START CAMPAIGN"); self.send_btn.clicked.connect(self.start_campaign); self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False); self.stop_btn.clicked.connect(self.stop_campaign)
        actions.addWidget(self.preview_btn); actions.addWidget(self.test_address); actions.addWidget(self.test_btn); actions.addWidget(self.history_btn); actions.addStretch(); actions.addWidget(self.stop_btn); actions.addWidget(self.send_btn); root.addLayout(actions)
        progress_box = QGroupBox("Progress"); progress = QVBoxLayout(progress_box); self.progress = QProgressBar(); self.progress.setValue(0); self.current = QLabel("Ready"); self.log = QListWidget(); progress.addWidget(self.progress); progress.addWidget(self.current); progress.addWidget(self.log); root.addWidget(progress_box, 1)
        self.setCentralWidget(central); menu = self.menuBar().addMenu("Tools"); history_action = QAction("Campaign history", self); history_action.triggered.connect(self.show_history); menu.addAction(history_action); help_menu = self.menuBar().addMenu("Help"); about = QAction("About", self); about.triggered.connect(lambda: QMessageBox.information(self, "SMTP Mail Sender", "PySide6 email campaign tool")); help_menu.addAction(about)

    def _load_profiles(self, select_name: str | None = None):
        names = profiles.names(); current = select_name if select_name is not None else self.profile_combo.currentText(); self._profile_loading = True; self.profile_combo.blockSignals(True); self.profile_combo.clear(); self.profile_combo.addItems(names)
        if current and current in names: self.profile_combo.setCurrentText(current)
        elif names: self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False); self._profile_loading = False; self._update_profile_summary()

    def _profile_changed(self, _index: int):
        if not self._profile_loading: self._update_profile_summary()

    def _update_profile_summary(self):
        name = self.profile_combo.currentText().strip()
        if not name: self.profile_summary.setText("No SMTP profile selected"); return
        try:
            p = profiles.get(name); username = str(p.get("username", "")).strip(); server = str(p.get("server", "")).strip(); port = p.get("port", 465); self.profile_summary.setText(f"{username} · SMTP {server}:{port}" if username and server else "Profile is not configured")
        except Exception: self.profile_summary.setText("Profile could not be loaded")

    def new_profile(self):
        dialog = ProfileDialog(self)
        if dialog.exec() != QDialog.Accepted: return
        name = dialog.profile_name()
        if name in profiles.names(): QMessageBox.warning(self, "Profile exists", "Choose a different profile name."); return
        try: profiles.save(name, dialog.profile_data()); self._load_profiles(name)
        except Exception as exc: QMessageBox.critical(self, "Save error", str(exc))

    def edit_profile(self):
        old_name = self.profile_combo.currentText().strip()
        if not old_name: QMessageBox.information(self, "Edit profile", "Choose a profile first."); return
        try: current = profiles.get(old_name)
        except Exception as exc: QMessageBox.critical(self, "Profile error", str(exc)); return
        dialog = ProfileDialog(self, old_name, current)
        if dialog.exec() != QDialog.Accepted: return
        new_name = dialog.profile_name()
        if new_name != old_name and new_name in profiles.names(): QMessageBox.warning(self, "Profile exists", "Choose a different profile name."); return
        try:
            profiles.save(new_name, dialog.profile_data());
            if new_name != old_name: profiles.remove(old_name)
            self._load_profiles(new_name)
        except Exception as exc: QMessageBox.critical(self, "Save error", str(exc))

    def delete_profile(self):
        name = self.profile_combo.currentText().strip()
        if not name: return
        if QMessageBox.question(self, "Delete profile", f"Delete '{name}'?") != QMessageBox.Yes: return
        try: profiles.remove(name); self._load_profiles()
        except Exception as exc: QMessageBox.critical(self, "Delete error", str(exc))

    def test_smtp(self):
        name = self.profile_combo.currentText().strip()
        if not name: QMessageBox.information(self, "Test SMTP", "Choose an SMTP profile first."); return
        try:
            p = profiles.get(name); username = str(p.get("username", "")).strip(); password = p.get("password", ""); server = str(p.get("server", "")).strip(); port = int(p.get("port", 465))
            if not username or not password or not server: raise ValueError("Complete the SMTP profile before testing it.")
            ok, error = test_connection(server, port, username, password)
            if ok: QMessageBox.information(self, "SMTP test", f"Connection and authentication succeeded.\n\n{server}:{port}")
            else: raise RuntimeError(error or "SMTP connection failed")
        except Exception as exc: QMessageBox.critical(self, "SMTP test failed", f"Profile: {name}\n\n{exc}")

    def choose_html(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose HTML template", "", "HTML files (*.html *.htm);;All files (*)")
        if path: self.html_path.setText(path); self._read_template()

    def _read_template(self):
        path = self.html_path.text()
        if path and Path(path).exists(): self.template_text = Path(path).read_text(encoding="utf-8-sig"); self._update_stats()

    def edit_html(self):
        path = self.html_path.text()
        if not path: self.choose_html(); path = self.html_path.text()
        if not path: return
        try:
            if sys.platform == "win32": subprocess.Popen(["start", "", path], shell=True)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except OSError as exc: QMessageBox.warning(self, "Cannot open editor", str(exc))

    def choose_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose recipient database", "", "Recipient files (*.txt *.csv *.xlsx);;All files (*)")
        if path: self.data_path.setText(path); self._read_data()

    def _read_data(self):
        try:
            raw_rows, _ = load(self.data_path.text(), False); self.duplicate_count = count_duplicates(raw_rows); self.rows, self.columns = load(self.data_path.text(), self.dedupe.isChecked()); self._populate_table(); self._update_stats()
        except Exception as exc:
            self.rows, self.columns = [], []; self.duplicate_count = 0; self.recipient_table.setRowCount(0); QMessageBox.critical(self, "Recipient file error", str(exc))

    def _populate_table(self):
        _, invalid = validate(self.rows); invalid_ids = {id(row) for row in invalid}; headers = list(self.columns); headers += ["email"] if "email" not in headers else []; headers.append("status")
        self.recipient_table.clear(); self.recipient_table.setColumnCount(len(headers)); self.recipient_table.setHorizontalHeaderLabels(headers); self.recipient_table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            for c, column in enumerate(headers):
                value = (("Invalid email" if id(row) in invalid_ids else "Valid") if column == "status" else row.get(column, ""))
                self.recipient_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.recipient_table.resizeColumnsToContents()

    def _update_stats(self):
        if not self.data_path.text(): return
        valid, invalid = validate(self.rows); vars_ = variables_in(self.template_text); missing = validate_columns(self.template_text, self.columns) if vars_ else []
        text = f"Total: {len(self.rows)} · Valid: {len(valid)} · Invalid: {len(invalid)} · Duplicates: {self.duplicate_count}"
        if vars_: text += f" · Variables: {', '.join(vars_)}"
        if missing: text += f" · MISSING COLUMNS: {', '.join(missing)}"
        self.stats.setText(text)

    def _ensure_ready(self, test=False):
        self._read_template()
        if not self.template_text: raise ValueError("Choose an HTML template")
        profile_name = self.profile_combo.currentText().strip()
        if not profile_name: raise ValueError("Choose an SMTP profile")
        smtp = profiles.get(profile_name)
        if not str(smtp.get("username", "")).strip() or not smtp.get("password") or not str(smtp.get("server", "")).strip(): raise ValueError("Complete SMTP profile settings")
        if not self.subject.text().strip(): raise ValueError("Subject cannot be empty")
        if test: return smtp
        if not self.rows: self._read_data()
        if not self.rows: raise ValueError("Choose a recipient database")
        missing = validate_columns(self.template_text, self.columns)
        if missing: raise ValueError("Missing columns: " + ", ".join(missing))
        valid, invalid = validate(self.rows)
        if invalid: raise ValueError(f"There are {len(invalid)} invalid recipient rows")
        if not valid: raise ValueError("No valid recipients found")
        return smtp

    def preview(self):
        try:
            self._ensure_ready(); row = self.rows[0]; body = render(self.template_text, row); dialog = QDialog(self); dialog.setWindowTitle("Email preview"); dialog.resize(1000, 760); layout = QVBoxLayout(dialog); sender = self.sender_name.text().strip() or str(self.profile_combo.currentText()); layout.addWidget(QLabel(f"From: {sender}\nTo: {row['email']}\nSubject: {self.subject.text().strip()}")); browser = QTextBrowser(); browser.setHtml(body); layout.addWidget(browser, 1); dialog.exec()
        except Exception as exc: QMessageBox.warning(self, "Cannot preview", str(exc))

    def send_test(self):
        try:
            smtp = self._ensure_ready(test=True); address = self.test_address.text().strip()
            if not address: raise ValueError("Enter a test recipient")
            row = self.rows[0] if self.rows else {"email": address}
            campaign = Campaign(smtp, [{**row, "email": address}], self.subject.text().strip(), self.sender_name.text().strip() or str(smtp["username"]).strip(), self.template_text)
            ok, failed, _ = campaign.run()
            if failed or not ok: raise RuntimeError("Test email was not sent")
            QMessageBox.information(self, "Test sent", f"Test email sent to {address}.")
        except Exception as exc: QMessageBox.critical(self, "Test failed", str(exc))

    def start_campaign(self):
        try:
            smtp_profile = self._ensure_ready(); valid, _ = validate(self.rows)
            if QMessageBox.question(self, "Start campaign", f"Send {len(valid)} emails now?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
            smtp = {"username": str(smtp_profile["username"]).strip(), "password": smtp_profile["password"], "server": str(smtp_profile["server"]).strip(), "port": int(smtp_profile["port"])}; sender = self.sender_name.text().strip() or smtp["username"]
            self.history_entry = history.start(self.profile_combo.currentText().strip(), self.subject.text().strip(), sender, self.html_path.text(), self.data_path.text(), len(valid))
            campaign = Campaign(smtp, valid, self.subject.text().strip(), sender, self.template_text, self.delay.value())
            self.thread = QThread(); self.worker = SendWorker(campaign); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.progress.connect(self.on_progress); self.worker.failed.connect(self.on_worker_failed); self.worker.finished.connect(self.on_finished); self.thread.start()
            self.send_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.preview_btn.setEnabled(False); self.test_btn.setEnabled(False); self.history_btn.setEnabled(False); self.log.clear(); self.progress.setMaximum(len(valid)); self.progress.setValue(0); self.current.setText("Starting…")
        except Exception as exc: QMessageBox.warning(self, "Cannot start", str(exc))

    def stop_campaign(self):
        if self.worker: self.worker.stop_requested = True
        self.stop_btn.setEnabled(False)

    @Slot(int, int, str, bool, str)
    def on_progress(self, current, total, recipient, ok, error):
        self.progress.setValue(current); self.current.setText(f"{current} / {total}: {recipient}"); text = f"✓ {recipient}" if ok else f"✗ {recipient}: {error}"; self.log.addItem(text); self.log.scrollToBottom()
        if self.history_entry: history.append_log(self.history_entry, f"{datetime.now().astimezone():%Y-%m-%d %H:%M:%S} {text}")

    @Slot(str)
    def on_worker_failed(self, message):
        if self.history_entry: history.append_log(self.history_entry, f"{datetime.now().astimezone():%Y-%m-%d %H:%M:%S} FATAL: {message}")
        QMessageBox.critical(self, "Campaign failed", message)

    @Slot(int, int, bool)
    def on_finished(self, ok, failed, stopped):
        self.send_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.preview_btn.setEnabled(True); self.test_btn.setEnabled(True); self.history_btn.setEnabled(True)
        if self.history_entry: history.finish(self.history_entry, ok, failed, stopped)
        if self.thread: self.thread.quit(); self.thread.wait(); self.thread = self.worker = None
        QMessageBox.information(self, "Campaign " + ("stopped" if stopped else "finished"), f"Successful: {ok}\nErrors: {failed}" + ("\nCampaign was stopped." if stopped else "")); self.history_entry = None

    def show_history(self): HistoryDialog(self).exec()


if __name__ == "__main__":
    app = QApplication(sys.argv); window = MainWindow(); window.show(); sys.exit(app.exec())
