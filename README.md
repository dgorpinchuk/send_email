# SMTP Mail Sender

Desktop-приложение для HTML-рассылок через SMTP. GUI построен на **PySide6**.

## Возможности

- выбор HTML-файла верстки;
- кнопка **Edit in default editor** — открывает выбранный HTML в приложении, назначенном ОС для этого типа файла (например, Sublime Text), поэтому шаблон можно быстро изменить и сохранить прямо во время подготовки рассылки;
- выбор базы получателей в `.txt`, `.csv` или `.xlsx`;
- полноценная таблица загруженных получателей в GUI;
- статистика базы: всего, валидных, невалидных и дубликатов;
- простой режим: одинаковое письмо всем адресатам;
- персонализация через `{{ variable }}`;
- автоматическая проверка соответствия переменных колонкам базы;
- `{{ unsubscribe_link }}` имеет встроенное значение по умолчанию `https://mail.yandex.ru/unsubscribe.html` и может быть переопределен колонкой базы;
- удаление дубликатов;
- проверка email-адресов до отправки;
- предпросмотр готового письма с заголовками From/To/Subject и отрендеренным HTML;
- тестовая отправка на отдельный адрес;
- SMTP-профили с username, password, server и port;
- пароль SMTP хранится через системное credential storage (`keyring`), а не в открытом конфигурационном файле;
- отдельная кнопка проверки SMTP-соединения без отправки письма;
- одно SMTP-соединение и одна авторизация используются для всей кампании;
- прогресс отправки и список успешных/ошибочных адресатов;
- возможность остановить текущую рассылку;
- настраиваемая задержка между письмами;
- история кампаний с датой, профилем, темой, шаблоном, базой и результатами;
- отдельный полный `.log` файл для каждой кампании с результатом по каждому адресату;
- SMTP, шаблонизация, получатели, кампании и история отделены от GUI на уровне модулей.

## Установка

Требуется Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\\Scripts\\activate    # Windows

pip install -r requirements.txt
```

## Запуск GUI

```bash
python app.py
```

## HTML-шаблон

Обычное письмо не требует переменных:

```html
<h1>Здравствуйте!</h1>
<p>Это обычное письмо.</p>
```

Для персонализации используйте:

```html
<h1>Здравствуйте, {{ name }}!</h1>
<p>Компания: {{ company }}</p>
<a href="{{ link }}">Открыть предложение</a>
```

И CSV/XLSX с колонками:

| email | name | company | link |
|---|---|---|---|
| user@example.com | Иван | ООО Ромашка | https://example.com |

Колонка `email` обязательна. Допустимы также названия `mail`, `e-mail`, `email_address` и `recipient`.

Значения переменных HTML-экранируются перед вставкой в шаблон.

### Unsubscribe link

Переменная `{{ unsubscribe_link }}` доступна всегда. Если колонка `unsubscribe_link` отсутствует в базе, используется:

```text
https://mail.yandex.ru/unsubscribe.html
```

Если в базе есть одноименная колонка, ее значение имеет приоритет.

## Формат TXT

Для простого списка адресатов можно использовать `.txt`, по одному адресу в строке:

```text
user1@example.com
user2@example.com
user3@example.com
```

## SMTP

Создайте профиль в GUI и сохраните его. Пароль сохраняется в системном хранилище учетных данных. Для Яндекс Почты используйте пароль приложения, а не обычный пароль аккаунта.

Кнопка **Test SMTP** проверяет соединение и авторизацию, но не отправляет письмо.

Во время кампании приложение открывает одно SMTP-соединение и переиспользует его для всех сообщений.

## Campaign history and logs

После запуска кампании создается запись в локальной истории и отдельный log-файл. В GUI доступен раздел **History**, где можно посмотреть параметры прошлых кампаний и открыть соответствующий log.

Данные приложения хранятся в пользовательском каталоге ОС:

- macOS: `~/Library/Application Support/send_email/`
- Windows: `%APPDATA%/send_email/`
- Linux: `$XDG_DATA_HOME/send_email/` или `~/.local/share/send_email/`

## Структура

```text
app.py                    # PySide6 GUI
core/
  campaign.py             # campaign orchestration and one SMTP session
  history.py              # campaign history and log files
  profiles.py             # SMTP profiles + secure password storage
  recipients.py           # TXT/CSV/XLSX loading and validation
  smtp_sender.py          # SMTP delivery backend
  template_engine.py      # {{ variable }} rendering
sender.py                 # legacy CLI sender
requirements.txt
```

## Legacy CLI

Существующий `sender.py` остается в репозитории для обратной совместимости со старым сценарием на основе `config.txt`, `mail.html` и `list.txt`.
