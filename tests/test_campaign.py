from unittest.mock import patch

from core.campaign import Campaign
from core.recipients import count_duplicates


def test_count_duplicates():
    rows = [
        {"email": "a@example.com"},
        {"email": "A@example.com"},
        {"email": "b@example.com"},
    ]
    assert count_duplicates(rows) == 1


def test_campaign_reuses_one_smtp_connection():
    rows = [{"email": "a@example.com"}, {"email": "b@example.com"}]
    smtp = {"server": "smtp.example.com", "port": 465, "username": "u", "password": "p"}

    with patch("core.campaign.SMTPClient") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        campaign = Campaign(smtp, rows, "Subject", "Sender", "<p>Hello</p>")
        ok, failed, stopped = campaign.run()

    assert (ok, failed, stopped) == (2, 0, False)
    client_cls.assert_called_once_with("smtp.example.com", 465, "u", "p")
    assert client.send.call_count == 2


def test_campaign_renders_each_recipient():
    rows = [{"email": "a@example.com", "name": "Alice"}]
    smtp = {"server": "smtp.example.com", "port": 465, "username": "u", "password": "p"}

    with patch("core.campaign.SMTPClient") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        Campaign(smtp, rows, "Subject", "Sender", "<p>Hello {{ name }}</p>").run()
        body = client.send.call_args.kwargs["html_body"]

    assert "Hello Alice" in body
