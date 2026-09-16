"""SMTP delivery backend."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


class SMTPClient:
    """Reusable SMTP-over-SSL connection."""

    def __init__(self, smtp_server: str, port: int, username: str, password: str, timeout: int = 30):
        self.smtp_server = smtp_server
        self.port = int(port)
        self.username = username
        self.password = password
        self.timeout = timeout
        self._server: smtplib.SMTP_SSL | None = None

    def connect(self) -> None:
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(
            self.smtp_server, self.port, context=context, timeout=self.timeout
        )
        try:
            server.login(self.username, self.password)
        except Exception:
            server.quit()
            raise
        self._server = server

    def close(self) -> None:
        if self._server is not None:
            try:
                self._server.quit()
            except (OSError, smtplib.SMTPException):
                pass
            finally:
                self._server = None

    def __enter__(self) -> "SMTPClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def send(self, recipient: str, subject: str, html_body: str, sender_name: str) -> None:
        if self._server is None:
            raise RuntimeError("SMTP connection is not open")

        msg = EmailMessage()
        msg.set_content("This email requires an HTML-capable email client.")
        msg.add_alternative(html_body, subtype="html")
        msg["Subject"] = subject
        msg["From"] = formataddr((sender_name, self.username))
        msg["To"] = recipient
        msg["Reply-To"] = self.username
        self._server.send_message(msg)


def test_connection(
    smtp_server: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 10,
) -> tuple[bool, str | None]:
    """Open an SMTP SSL connection and authenticate without sending a message."""
    try:
        with SMTPClient(smtp_server, port, username, password, timeout=timeout):
            pass
        return True, None
    except (OSError, smtplib.SMTPException, ssl.SSLError) as exc:
        return False, str(exc)


def send_email(
    smtp_server: str,
    port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    html_body: str,
    sender_name: str,
) -> tuple[bool, str | None]:
    """Backward-compatible one-message helper."""
    try:
        with SMTPClient(smtp_server, port, username, password) as client:
            # Preserve the old API's explicit from_addr semantics for callers
            # outside the GUI. The GUI uses the authenticated username.
            if from_addr == username:
                client.send(to_addr, subject, html_body, sender_name)
            else:
                msg = EmailMessage()
                msg.set_content("This email requires an HTML-capable email client.")
                msg.add_alternative(html_body, subtype="html")
                msg["Subject"] = subject
                msg["From"] = formataddr((sender_name, from_addr))
                msg["To"] = to_addr
                msg["Reply-To"] = from_addr
                client._server.send_message(msg)  # type: ignore[union-attr]
        return True, None
    except (OSError, smtplib.SMTPException, ssl.SSLError) as exc:
        return False, str(exc)
