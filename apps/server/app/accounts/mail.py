"""SMTP delivery for account recovery; no credentials or reset links are logged."""

import smtplib
import ssl
from email.message import EmailMessage

from app.config import AppConfig


def send_reset(config: AppConfig, email: str, url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Restablece tu contraseña de SongLine"
    message["From"] = config.smtp_from
    message["To"] = email
    message.set_content(
        "Has solicitado cambiar tu contraseña de SongLine.\n\n"
        f"Abre este enlace en los próximos 30 minutos:\n{url}\n\n"
        "Si no lo has solicitado, ignora este correo."
    )
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as smtp:
        if config.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if config.smtp_username:
            smtp.login(config.smtp_username, config.smtp_password)
        smtp.send_message(message)
