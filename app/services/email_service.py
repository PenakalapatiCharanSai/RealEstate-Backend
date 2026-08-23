import logging
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config.config import Config

# Configure logger
logger = logging.getLogger(__name__)

def send_email(to, subject, html, text=None):
    """
    Core Reusable Synchronous Email Dispatch Function using Gmail / Standard SMTP.
    
    Parameters:
      - to (str or list): Recipient email address or list of addresses
      - subject (str): Subject line of the email
      - html (str): HTML body content of the email
      - text (str, optional): Plaintext fallback body content
      
    Returns:
      dict: {"success": True} or {"success": False, "error": "details"}
    """
    smtp_host = Config.SMTP_HOST or "smtp.gmail.com"
    smtp_port = getattr(Config, "SMTP_PORT", 587) or 587
    smtp_user = Config.SMTP_USERNAME
    smtp_pass = Config.SMTP_PASSWORD

    if not smtp_user or not smtp_pass or smtp_pass.strip() == "":
        logger.warning(f"[SMTP UNCONFIGURED] SMTP_USERNAME or SMTP_PASSWORD missing. Skipped sending '{subject}' to {to}.")
        return {"success": False, "message": "SMTP email service is not configured."}

    sender_name = Config.EMAIL_FROM_NAME or "HavenSpace Real Estate"
    sender_address = Config.EMAIL_FROM_ADDRESS or smtp_user
    from_header = f"{sender_name} <{sender_address}>"

    # Normalize recipient address(es)
    recipients = [to] if isinstance(to, str) else to
    recipients = [r.strip() for r in recipients if r and isinstance(r, str) and "@" in r]

    if not recipients:
        logger.error(f"[SMTP ERROR] Invalid recipient address provided: {to}")
        return {"success": False, "error": "No valid recipient email address provided."}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = ", ".join(recipients)

        if text:
            msg.attach(MIMEText(text, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))

        # Connect to Gmail / SMTP server with STARTTLS
        server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=15)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_address, recipients, msg.as_string())
        server.quit()

        logger.info(f"[SMTP SUCCESS] Email '{subject}' successfully sent to {recipients} via {smtp_host}.")
        return {"success": True}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[SMTP FAILURE] Exception sending email '{subject}' to {recipients}: {error_msg}")
        return {"success": False, "error": error_msg}


def send_email_async(to, subject, html, text=None):
    """
    Non-blocking Asynchronous Email Dispatch.
    Spawns a background daemon thread to send email without delaying API responses.
    """
    def _worker():
        try:
            send_email(to, subject, html, text)
        except Exception as e:
            logger.error(f"[SMTP ASYNC ERROR] Background thread error for '{subject}': {e}")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return {"success": True, "message": "Email dispatch queued in background."}
