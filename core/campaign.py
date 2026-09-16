"""Framework-independent email campaign orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from core.smtp_sender import SMTPClient
from core.template_engine import render


@dataclass(frozen=True)
class DeliveryResult:
    index: int
    total: int
    recipient: str
    success: bool
    error: str = ""


class Campaign:
    """Send a collection of personalized messages through one SMTP session."""

    def __init__(
        self,
        smtp: dict,
        rows: list[dict[str, str]],
        subject: str,
        sender_name: str,
        template: str,
        delay_ms: int = 0,
    ):
        self.smtp = smtp
        self.rows = rows
        self.subject = subject
        self.sender_name = sender_name
        self.template = template
        self.delay_ms = max(0, int(delay_ms))

    def run(
        self,
        on_progress: Callable[[DeliveryResult], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> tuple[int, int, bool]:
        """Run the campaign and return (successful, failed, stopped)."""
        ok_count = fail_count = 0
        stopped = False
        client = SMTPClient(
            str(self.smtp["server"]).strip(),
            int(self.smtp["port"]),
            str(self.smtp["username"]).strip(),
            self.smtp["password"],
        )

        # One connection and authentication for the whole campaign.
        with client:
            total = len(self.rows)
            for index, row in enumerate(self.rows, 1):
                if should_stop and should_stop():
                    stopped = True
                    break

                recipient = row.get("email", "")
                try:
                    body = render(self.template, row)
                    client.send(
                        recipient=recipient,
                        subject=self.subject,
                        html_body=body,
                        sender_name=self.sender_name,
                    )
                    success, error = True, ""
                except Exception as exc:
                    success, error = False, str(exc)

                if success:
                    ok_count += 1
                else:
                    fail_count += 1

                result = DeliveryResult(index, total, recipient, success, error)
                if on_progress:
                    on_progress(result)

                if self.delay_ms and index < total:
                    # Sleep in small chunks so Stop remains responsive.
                    remaining = self.delay_ms / 1000
                    while remaining > 0:
                        if should_stop and should_stop():
                            stopped = True
                            break
                        chunk = min(0.1, remaining)
                        time.sleep(chunk)
                        remaining -= chunk
                    if stopped:
                        break

        return ok_count, fail_count, stopped
