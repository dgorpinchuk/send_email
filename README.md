# SMTP Mail Sender

Desktop-приложение для HTML-рассылок через SMTP. GUI построен на **PySide6**.

## Возможности

- выбор HTML-файла верстки;
- кнопка **Edit in default editor** — открывает выбранный HTML в приложении, назначенном ОС для этого типа файла (например, Sublime Text), поэтому шаблон можно быстро изменить и сохранить прямо во время подготовки рассылки;
- выбор базы получателей в `.txt`, `.csv` или `.xlsx`;
- простой режим: одинаковое письмо всем адресатам;
- персонализация через `{{ variable }}`;
- автоматическая проверка соответствия переменных колонкам базы;
- удаление дубликатов;
- проверка email-адресов до отправки;
- HTML preview с данными первого получателя;
- тестовая отправка на отдельный адрес;
- SMTP-профили с username, password, server и port;
- пароль SMTP хранится через системное credential storage (`keyring`), а не в открытом конфигурационном файле;
- прогресс отправки, список успешных и ошибочных адресатов;
- возможность остановить текущую рассылку;
- настраиваемая задержка между письмами;
- SMTP-движок вынесен отдельно от GUI.

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

## Формат TXT

Для простого списка адресатов можно использовать `.txt`, по одному адресу в строке:

```text
user1@example.com
user2@example.com
user3@example.com
```

## SMTP

Создайте профиль в GUI и сохраните его. Пароль сохраняется в системном хранилище учетных данных. Для Яндекс Почты используйте пароль приложения, а не обычный пароль аккаунта.

## Структура

```text
app.py                    # PySide6 GUI
core/
  profiles.py             # SMTP profiles + secure password storage
  recipients.py           # TXT/CSV/XLSX loading and validation
  smtp_sender.py          # SMTP delivery backend
  template_engine.py      # {{ variable }} rendering
sender.py                 # legacy CLI sender
requirements.txt
```

## Legacy CLI

Существующий `sender.py` остается в репозитории для обратной совместимости со старым сценарием на основе `config.txt`, `mail.html` и `list.txt`.
