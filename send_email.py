import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from secrets_parameters import calendar_manager_email, calendar_manager_password

email_address = calendar_manager_email
email_password = calendar_manager_password


def send_email(send_to, subject, text, send_logs=False):
    #assert isinstance(send_to, list)

    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = send_to
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(text))

    if send_logs:
        

        f = 'debug.log'
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)

    # send email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_address, email_password)
        print(smtp.send_message(msg))
