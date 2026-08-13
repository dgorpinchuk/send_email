import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage

# ANSI-цвета для красивого вывода
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

CONFIG_FILE = "config.txt"
RECIPIENTS_FILE = "list.txt"
LOG_FILE = "send.log"
HTML_FILE = "mail.html"


def print_header(text):
    """Выводит заголовок в рамке."""
    width = 60
    print(COLOR_CYAN + "=" * width + COLOR_RESET)
    print(
        COLOR_CYAN
        + "|"
        + COLOR_RESET
        + COLOR_BOLD
        + text.center(width - 2)
        + COLOR_RESET
        + COLOR_CYAN
        + "|"
        + COLOR_RESET
    )
    print(COLOR_CYAN + "=" * width + COLOR_RESET)


def print_progress(current, total, prefix="", suffix=""):
    """Выводит простой прогресс-бар."""
    bar_length = 30
    percent = current / total if total else 0
    filled = int(bar_length * percent)
    bar = "█" * filled + "─" * (bar_length - filled)
    print(
        f"\r{prefix} [{bar}] {current}/{total} ({percent * 100:.1f}%) {suffix}",
        end="",
        flush=True,
    )
    if current == total:
        print()


def log_message(recipient, status, error=None):
    """Выводит цветной лог в консоль и записывает в файл."""
    tz = datetime.now().astimezone().tzinfo
    timestamp = datetime.now(tz=tz).strftime("%d.%m.%Y %H:%M:%S")

    if status == "OK":
        icon = COLOR_GREEN + "✔" + COLOR_RESET
        status_text = COLOR_GREEN + "OK" + COLOR_RESET
        log_entry = f"[{timestamp}] OK: {recipient}"
    else:
        icon = COLOR_RED + "✘" + COLOR_RESET
        status_text = COLOR_RED + "ERROR" + COLOR_RESET
        log_entry = f"[{timestamp}] ERROR: {recipient} - {error}"

    print(f"{icon} {timestamp} {status_text} {recipient}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(COLOR_RED + f"Ошибка: файл {CONFIG_FILE} не найден." + COLOR_RESET)
        sys.exit(1)
    config = {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    required_keys = ["username", "password", "server", "port"]
    for key in required_keys:
        if key not in config:
            print(
                COLOR_RED
                + f"Ошибка: в {CONFIG_FILE} отсутствует ключ '{key}'."
                + COLOR_RESET
            )
            sys.exit(1)
    try:
        config["port"] = int(config["port"])
    except ValueError:
        print(COLOR_RED + "Ошибка: порт должен быть числом." + COLOR_RESET)
        sys.exit(1)
    return config


def load_recipients():
    if not os.path.exists(RECIPIENTS_FILE):
        print(COLOR_RED + f"Ошибка: файл {RECIPIENTS_FILE} не найден." + COLOR_RESET)
        sys.exit(1)
    with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        print(
            COLOR_YELLOW + f"Предупреждение: файл {RECIPIENTS_FILE} пуст." + COLOR_RESET
        )
    return lines


def load_html_body():
    if not os.path.exists(HTML_FILE):
        print(COLOR_RED + f"Ошибка: файл {HTML_FILE} не найден." + COLOR_RESET)
        sys.exit(1)
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        return f.read()


def ask_yes_no(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("д", "да", "y", "yes", ""):
            return True
        elif answer in ("н", "нет", "n", "no"):
            return False
        else:
            print(
                COLOR_YELLOW
                + "Пожалуйста, введите 'Д' (да) или 'н' (нет)."
                + COLOR_RESET
            )


def send_email(
    smtp_server,
    port,
    username,
    password,
    from_addr,
    to_addr,
    subject,
    html_body,
    sender_name,
):
    msg = EmailMessage()
    msg.set_content(html_body, subtype="html")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{from_addr}>"
    msg["To"] = to_addr
    msg["Reply-To"] = from_addr

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(username, password)
            server.send_message(msg)
        return True, None
    except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
        return False, str(e)


def main():
    print_header("SMTP-рассылка через Яндекс Почту")
    print()

    # Загружаем конфиг сразу, чтобы получить username для отправителя
    config = load_config()
    from_addr = config["username"]  # берём отправителя из логина

    subject = input(COLOR_BOLD + "Введите тему письма: " + COLOR_RESET).strip()
    if not subject:
        print(COLOR_RED + "Ошибка: тема не может быть пустой." + COLOR_RESET)
        sys.exit(1)

    sender_name = input(COLOR_BOLD + "Введите имя отправителя: " + COLOR_RESET).strip()
    if not sender_name:
        sender_name = from_addr

    html_body = load_html_body()
    recipients = load_recipients()

    if not recipients:
        print(COLOR_RED + "Нет получателей. Завершение." + COLOR_RESET)
        sys.exit(1)

    print()
    print_header("Проверка данных")
    print(f"  {COLOR_CYAN}Тема:{COLOR_RESET} {subject}")
    print(f"  {COLOR_CYAN}Отправитель:{COLOR_RESET} {sender_name} <{from_addr}>")
    print(f"  {COLOR_CYAN}Количество получателей:{COLOR_RESET} {len(recipients)}")

    if not ask_yes_no(
        COLOR_BOLD + "Приступить к отправке рассылки? (Д/н): " + COLOR_RESET
    ):
        print(COLOR_YELLOW + "Отмена." + COLOR_RESET)
        sys.exit(0)

    print()
    print_header("Начинаю отправку")
    print()

    tz = datetime.now().astimezone().tzinfo
    start_time = datetime.now(tz=tz).strftime("%d.%m.%Y %H:%M:%S")
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Рассылка от {start_time} ===\n")

    success_count = 0
    fail_count = 0
    total = len(recipients)

    for i, recipient in enumerate(recipients, 1):
        print_progress(i - 1, total, prefix="Прогресс:", suffix="")
        ok, error = send_email(
            smtp_server=config["server"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            from_addr=from_addr,
            to_addr=recipient,
            subject=subject,
            html_body=html_body,
            sender_name=sender_name,
        )
        if ok:
            log_message(recipient, "OK")
            success_count += 1
        else:
            log_message(recipient, "ERROR", error)
            fail_count += 1

    print_progress(total, total, prefix="Прогресс:", suffix="Готово!")
    print()
    print_header("Результаты")
    print(f"  {COLOR_GREEN}✔ Успешно:{COLOR_RESET} {success_count}")
    print(f"  {COLOR_RED}✘ Ошибок:{COLOR_RESET} {fail_count}")
    print(f"  {COLOR_CYAN}Лог сохранён в:{COLOR_RESET} {LOG_FILE}")
    print()


if __name__ == "__main__":
    main()
