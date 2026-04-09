import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, TO_EMAIL


def send_email(subject: str, html_body: str) -> None:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not TO_EMAIL:
        raise RuntimeError(
            "Email configuration is incomplete. Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and TO_EMAIL before sending."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, TO_EMAIL, msg.as_string())
