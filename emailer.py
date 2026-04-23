import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import AppConfig, current_config


def send_email(subject: str, html_body: str, *, config: AppConfig | None = None) -> None:
    resolved = config or current_config()
    if not resolved.gmail_address or not resolved.gmail_app_password or not resolved.to_email:
        raise RuntimeError(
            "Email configuration is incomplete. Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and TO_EMAIL before sending."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = resolved.gmail_address
    msg["To"] = resolved.to_email

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(resolved.gmail_address, resolved.gmail_app_password)
        server.sendmail(resolved.gmail_address, resolved.to_email, msg.as_string())
