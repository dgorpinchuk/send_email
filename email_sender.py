import pandas as pd
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

# Read sender email and password from 'secret.txt'
with open('secret.txt', 'r') as f:
    lines = f.readlines()
    sender_email = lines[0].strip()  # почта, с которой делаем рассылку
    password = lines[1].strip()  # пароль к почте (пароли приложений Яндекс)

# Email server configuration
smtp_server = 'smtp.yandex.ru'
port = 465

# Read email list from Excel file 'list.xlsx'
df = pd.read_excel('list.xlsx')

# тема письма
subject = 'Уведомление об аннулировании результатов'

# Read email content from HTML file 'mail.html'
with open('mail.html', 'r') as email_file:
    email_content = email_file.read()

# Iterate through each row in the DataFrame
for index, row in df.iterrows():
    receiver_email = row['E-mail']
    var1 = row['Направление']  # столбец с назавнием направления в эксельке
    var2 = row['Пункт аннулирования']  # столбец с пунктом положения в эксельке
    var3 = row['Доп текст']  # столбец с текстом пункта положения в эксельке

    # Replace variables in email content
    email_body = email_content.replace('courseName', str(var1)).replace(
        'numberField', str(var2)).replace('additionalText', str(var3))

    # Set up the MIME
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject

    # Attach HTML content to the email
    message.attach(MIMEText(email_body, 'html'))

    # Establish a secure SSL context
    context = ssl.create_default_context()

    # Create SMTP session for sending the email
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

    logging.info("Email sent to " + receiver_email)
