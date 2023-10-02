import os
import smtplib
import csv
import email

f = open('contacts.txt', 'r') # открыть файл
emails = f.readlines() # читаем почты построчно

for email in emails:
  print(email) # prints each line

message = email.message_from_file(open('email.html', 'rb')) # Читаем файл email.html построчно и преобразуем его в объект типа email.Message
email_from = 'iprofi.olimp@yandex.ru' # Отправитель
subject = 'Олимпиада «Я — профессионал»' # Тема письма

print("Connecting server")
server = smtplib.SMTP('smtp.yandex.ru',465) # Адрес сервера для отправки почты
server.starttls() # Включаем шифрование
server.login(email_from, password='wohbqlqsuxmqxdag') # Получаем доступ к серверу от имени отправителя
print("Sending emails...")
server.sendmail(email_from, emails, message) # Отправляем письма
server.quit() # Отключаемся от сервера
print("Finished!")