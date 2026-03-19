import smtplib
from email.mime.text import MIMEText
import base64
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests import HTTPError

# https://stackoverflow.com/questions/46160886/how-to-send-smtp-email-for-office365-with-python-using-tls-ssl#:~:text=import%20smtplib%20mailserver%20%3D%20smtplib.SMTP%28%27smtp.office365.com%27%2C587%29%20mailserver.ehlo%28%29%20mailserver.starttls%28%29%20mailserver.login%28%27user%40company.co%27%2C,fixes%20the%20missing%20message%20body%20mailserver.sendmail%28%27user%40company.co%27%2C%27user%40company.co%27%2C%27%5B%26npython%26%5D%20email%27%29%20mailserver.quit%28%29

def sendMailThroughExchangeServer(exchangeServerUrl : str, user : str, password : str, fromaddr : str, toaddrs : str, messageToBeSent : str):
    url = exchangeServerUrl
    conn = smtplib.SMTP(url,587)
    conn.starttls()
    conn.login(user, password)
    fromWhom, toWhom = fromaddr,toaddrs
    conn.sendmail(fromWhom,toWhom, messageToBeSent)

def sendMailThroughGmail(user : str, password : str, fromaddr : str, toaddrs : str, subject: str, messageToBeSent : str, isHTML : bool = True):
    # try:
    #     url = "smtp.gmail.com"
    #     message = None
    #     if isHTML:
    #         message = MIMEText(messageToBeSent, 'html')
    #     else:
    #         message = MIMEText(messageToBeSent)
    #     message['Subject'] = subject
    #     message['From'] = fromaddr
    #     message['To'] = ', '.join(toaddrs)
    #     with smtplib.SMTP_SSL(url, 465) as server:
    #         server.login(fromaddr, password)
    #         server.sendmail(fromaddr, toaddrs, message.as_string())
    # except Exception as e:
    #     print(e)

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.send"
    ]
    flow = InstalledAppFlow.from_client_secrets_file('C:/client_secret_gmail.json', SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('gmail', 'v1', credentials=creds)
    message = None
    if isHTML:
        message = MIMEText(messageToBeSent, 'html')
    else:
        message = MIMEText(messageToBeSent)
    message['Subject'] = subject
    message['From'] = fromaddr
    message['To'] = ', '.join(toaddrs)
    create_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
    try:
        message = (service.users().messages().send(userId="Uddipan", body=create_message).execute())
        print(f'Sent message to {message["To"]} Message Id: {message["id"]}')
    except HTTPError as error:
        print(f'An error occurred: {error}')
        message = None

# sendMailThroughGmail("Uddipan", "@Sumona1968", "uddipan@gmail.com", "uddipan@gmail.com", "Trial", messageToBeSent = "Some message", isHTML=False)