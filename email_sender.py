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
    sender_email = lines[0].strip()
    password = lines[1].strip()

# Email server configuration
smtp_server = 'smtp.yandex.ru'
port = 465

# Read email list from Excel file 'list.xlsx'
df = pd.read_excel('list.xlsx')

# Read email content from HTML file 'mail.html'
with open('mail.html', 'r') as email_file:
    email_content = email_file.read()

# Iterate through each row in the DataFrame
for index, row in df.iterrows():
    receiver_email = row['Email']
    subject = row['Topic']
    var1 = row['Var1']  # столбец с назавнием направления в эксельке
    var2 = row['Var2']  # столбец с пунктом положения в эксельке
    var3 = row['Var3']  # столбец с текстом пункта положения в эксельке

    # Replace variables in email content
    email_body = email_content.replace('Var1', str(var1)).replace(
        'Var2', str(var2)).replace('Var3', str(var3))

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
