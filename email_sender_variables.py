import pandas as pd
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import ssl
import configparser

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

# Read config variables from 'config.ini'
config = configparser.ConfigParser()
config.read('config.ini')

# Read email list from Excel file 'list.xlsx'
df = pd.read_excel('list.xlsx')

# Read email content from HTML file 'mail.html'
with open('mail.html', 'r') as email_file:
    email_content = email_file.read()

# Get variables from config file
sender_email_name = config['Common']['sender_email_name']
sender_email = config['Common']['sender_email']
subject = config['Annulment']['subject']
smtp_server = config['Common']['smtp_server']
port = int(config['Common']['port'])
password = config['Common']['password']

logging.warning("Отправитель: " + sender_email_name)
logging.warning("От: " + sender_email)
logging.warning("Тема письма: " + subject)
logging.warning("SMTP сервер: " + smtp_server)
logging.warning("Порт сервера: " + str(port))
logging.warning("Пароль: " + password)

# Iterate through each row in the DataFrame
for index, row in df.iterrows():
    receiver_email = row['E-mail']
    courseNameVar = row['Направление']  # столбец с назавнием направления в эксельке
    numberFieldVar = row['Пункт аннулирования']  # столбец с пунктом положения в эксельке
    additionalTextVar = row['Доп текст']  # столбец с текстом пункта положения в эксельке

    # Replace variables in email content
    email_body = email_content.replace('courseName', str(courseNameVar)).replace(
        'numberField', str(numberFieldVar)).replace('additionalText', str(additionalTextVar))

    # Set up the MIME
    message = MIMEMultipart()
    # message['From'] = sender_email
    message['From'] = formataddr((str(Header(sender_email_name, 'utf-8')), sender_email))
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

    logging.info("Письмо отправлено " + receiver_email)
