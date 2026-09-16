"""SMTP delivery backend."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


def test_connection(
    smtp_server: str,
    port: int,
    username: str,
    password: str,
    timeout: int = 10,
) -> tuple[bool, str | None]:
    """Open an SMTP SSL connection and authenticate without sending a message."""
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            smtp_server, port, context=context, timeout=timeout
        ) as server:
            server.login(username, password)
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
    msg = EmailMessage()
    msg.set_content("This email requires an HTML-capable email client.")
    msg.add_alternative(html_body, subtype="html")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, from_addr))
    msg["To"] = to_addr
    msg["Reply-To"] = from_addr

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context, timeout=30) as server:
            server.login(username, password)
            server.send_message(msg)
        return True, None
    except (OSError, smtplib.SMTPException, ssl.SSLError) as exc:
        return False, str(exc)
