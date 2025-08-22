from __future__ import annotations

import smtplib
from email.mime.text import MIMEText


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
    use_tls: bool,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    if use_tls:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port)

    if smtp_user and smtp_password:
        server.login(smtp_user, smtp_password)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    server.quit()
