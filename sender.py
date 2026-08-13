import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage

CONFIG_FILE = "config.txt"          # файл с настройками
RECIPIENTS_FILE = "list.txt"
LOG_FILE = "send.log"
HTML_FILE = "mail.html"

def load_config():
    """Читает настройки из текстового файла с парами ключ=значение."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Ошибка: файл {CONFIG_FILE} не найден.")
        sys.exit(1)
    config = {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):  # пропускаем пустые строки и комментарии
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    required_keys = ['username', 'password', 'server', 'port']
    for key in required_keys:
        if key not in config:
            print(f"Ошибка: в {CONFIG_FILE} отсутствует ключ '{key}'.")
            sys.exit(1)
    # Преобразуем порт в int
    try:
        config['port'] = int(config['port'])
    except ValueError:
        print("Ошибка: порт должен быть числом.")
        sys.exit(1)
    return config

def load_recipients():
    if not os.path.exists(RECIPIENTS_FILE):
        print(f"Ошибка: файл {RECIPIENTS_FILE} не найден.")
        sys.exit(1)
    with open(RECIPIENTS_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        print(f"Предупреждение: файл {RECIPIENTS_FILE} пуст.")
    return lines

def load_html_body():
    if not os.path.exists(HTML_FILE):
        print(f"Ошибка: файл {HTML_FILE} не найден.")
        sys.exit(1)
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        return f.read()

def ask_yes_no(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ('д', 'да', 'y', 'yes', ''):
            return True
        elif answer in ('н', 'нет', 'n', 'no'):
            return False
        else:
            print("Пожалуйста, введите 'Д' (да) или 'н' (нет).")

def send_email(smtp_server, port, username, password, from_addr, to_addr,
               subject, html_body, sender_name):
    msg = EmailMessage()
    msg.set_content(html_body, subtype='html')
    msg['Subject'] = subject
    msg['From'] = f"{sender_name} <{from_addr}>"
    msg['To'] = to_addr
    msg['Reply-To'] = from_addr

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(username, password)
            server.send_message(msg)
        return True, None
    except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
        return False, str(e)

def log_message(recipient, status, error=None):
    tz = datetime.now().astimezone().tzinfo
    timestamp = datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S")
    if status == "OK":
        log_entry = f"[{timestamp}] OK: {recipient}"
    else:
        log_entry = f"[{timestamp}] ERROR: {recipient} - {error}"
    print(log_entry)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry + "\n")

def main():
    print("=== Рассылка писем через Яндекс Почту (HTML из файла) ===\n")

    subject = input("Введите тему письма: ").strip()
    if not subject:
        print("Тема не может быть пустой. Завершение.")
        sys.exit(1)

    from_addr = input("Введите адрес отправителя (ваш Яндекс-адрес): ").strip()
    if not from_addr:
        print("Адрес отправителя не может быть пустым. Завершение.")
        sys.exit(1)

    sender_name = input("Введите имя отправителя: ").strip()
    if not sender_name:
        sender_name = from_addr

    html_body = load_html_body()
    config = load_config()
    recipients = load_recipients()

    if not recipients:
        print("Нет получателей. Завершение.")
        sys.exit(1)

    print("\n--- Проверка данных ---")
    print(f"Тема: {subject}")
    print(f"Отправитель: {sender_name} <{from_addr}>")
    print(f"Количество получателей: {len(recipients)}")

    if not ask_yes_no("Приступить к отправке рассылки? (Д/н): "):
        print("Отмена.")
        sys.exit(0)

    print("\nНачинаю отправку...")
    tz = datetime.now().astimezone().tzinfo
    start_time = datetime.now(tz=tz).strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Рассылка от {start_time} ===\n")

    success_count = 0
    fail_count = 0

    for i, recipient in enumerate(recipients, 1):
        print(f"[{i}/{len(recipients)}] Обработка {recipient}...")
        ok, error = send_email(
            smtp_server=config['server'],
            port=config['port'],
            username=config['username'],
            password=config['password'],
            from_addr=from_addr,
            to_addr=recipient,
            subject=subject,
            html_body=html_body,
            sender_name=sender_name
        )
        if ok:
            log_message(recipient, "OK")
            success_count += 1
        else:
            log_message(recipient, "ERROR", error)
            fail_count += 1

    print(f"\nОтправка завершена. Успешно: {success_count}, Ошибок: {fail_count}")
    print(f"Лог сохранён в {LOG_FILE}")

if __name__ == "__main__":
    main()