import os
import logging
import threading
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config.config import Config

# Configure logger
logger = logging.getLogger(__name__)

def send_email(to, subject, html, text=None):
    """
    Multi-Provider Universal Email Dispatch Function.
    
    1. Tries Resend HTTP REST API (Port 443) if RESEND_API_KEY is configured.
    2. Tries Brevo HTTP REST API (Port 443) if BREVO_API_KEY is configured.
    3. Tries Gmail / Standard SMTP (SSL 465 -> TLS 587 -> 25) as primary/fallback.
    
    Returns:
      dict: {"success": True} or {"success": False, "error": "details"}
    """
    sender_name = Config.EMAIL_FROM_NAME or "HavenSpace Real Estate"
    smtp_user = Config.SMTP_USERNAME or "havenspace.marketplace@gmail.com"
    sender_address = Config.EMAIL_FROM_ADDRESS or smtp_user
    from_header = f"{sender_name} <{sender_address}>"

    # Normalize recipient address(es)
    recipients = [to] if isinstance(to, str) else to
    recipients = [r.strip() for r in recipients if r and isinstance(r, str) and "@" in r]

    if not recipients:
        logger.error(f"[EMAIL ERROR] Invalid recipient address provided: {to}")
        return {"success": False, "error": "No valid recipient email address provided."}

    # ==========================================
    # METHOD 1: Resend HTTP REST API (Port 443 - Render Unblocked)
    # ==========================================
    resend_key = getattr(Config, "RESEND_API_KEY", "") or os.getenv("RESEND_API_KEY", "")
    if resend_key and resend_key.strip():
        try:
            # Note: onboarding@resend.dev works for testing to user email
            resend_sender = "HavenSpace <onboarding@resend.dev>" if "resend.dev" not in sender_address else from_header
            res_payload = {
                "from": resend_sender,
                "to": recipients,
                "subject": subject,
                "html": html,
                "text": text or ""
            }
            resp = requests.post(
                "https://api.resend.com/emails",
                json=res_payload,
                headers={"Authorization": f"Bearer {resend_key.strip()}", "Content-Type": "application/json"},
                timeout=10
            )
            if resp.status_code in [200, 201]:
                logger.info(f"[RESEND SUCCESS] Email '{subject}' delivered via Resend HTTP API to {recipients}.")
                return {"success": True}
            else:
                logger.warning(f"[RESEND HTTP WARN] Resend API returned status {resp.status_code}: {resp.text}")
        except Exception as resend_err:
            logger.warning(f"[RESEND EXCEPTION] {resend_err}. Retrying via alternate providers...")

    # ==========================================
    # METHOD 2: Brevo HTTP REST API (Port 443 - Render Unblocked)
    # ==========================================
    brevo_key = getattr(Config, "BREVO_API_KEY", "") or os.getenv("BREVO_API_KEY", "")
    if brevo_key and brevo_key.strip():
        try:
            brevo_payload = {
                "sender": {"name": sender_name, "email": sender_address},
                "to": [{"email": r} for r in recipients],
                "subject": subject,
                "htmlContent": html
            }
            if text:
                brevo_payload["textContent"] = text

            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                json=brevo_payload,
                headers={"api-key": brevo_key.strip(), "Content-Type": "application/json"},
                timeout=10
            )
            if resp.status_code in [200, 201, 202]:
                logger.info(f"[BREVO SUCCESS] Email '{subject}' delivered via Brevo HTTP API to {recipients}.")
                return {"success": True}
            else:
                logger.warning(f"[BREVO HTTP WARN] Brevo API returned status {resp.status_code}: {resp.text}")
        except Exception as brevo_err:
            logger.warning(f"[BREVO EXCEPTION] {brevo_err}. Retrying via Gmail SMTP...")

    # ==========================================
    # METHOD 3: Gmail / Standard SMTP Dispatch
    # ==========================================
    smtp_host = Config.SMTP_HOST or "smtp.gmail.com"
    smtp_pass = Config.SMTP_PASSWORD

    if not smtp_user or not smtp_pass or smtp_pass.strip() == "":
        logger.warning(f"[SMTP UNCONFIGURED] SMTP_PASSWORD missing. Skipped sending '{subject}' to {to}.")
        return {"success": False, "message": "SMTP credentials not configured."}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = ", ".join(recipients)

    if text:
        msg.attach(MIMEText(text, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    # Attempt 3a: Direct SSL Port 465
    try:
        server = smtplib.SMTP_SSL(smtp_host, 465, timeout=6)
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_address, recipients, msg.as_string())
        server.quit()
        logger.info(f"[SMTP SUCCESS - SSL 465] Email '{subject}' sent to {recipients}.")
        return {"success": True}
    except Exception as ssl_err:
        logger.warning(f"[SMTP SSL 465 WARN] Port 465 failed ({ssl_err}). Retrying via TLS Port 587...")

    # Attempt 3b: TLS Port 587
    try:
        server = smtplib.SMTP(smtp_host, 587, timeout=6)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_address, recipients, msg.as_string())
        server.quit()
        logger.info(f"[SMTP SUCCESS - TLS 587] Email '{subject}' sent to {recipients}.")
        return {"success": True}
    except Exception as tls_err:
        err_str = str(tls_err)
        if "Network is unreachable" in err_str or "101" in err_str:
            logger.error(
                f"[RENDER PORT BLOCK DETECTED] Render has restricted raw outbound SMTP ports 465/587. "
                f"To enable 100% free HTTP email delivery on Render (Port 443), set 'RESEND_API_KEY' or 'BREVO_API_KEY' in your Render Environment Variables."
            )
        error_msg = f"SSL 465 and TLS 587 failed: {err_str}"
        return {"success": False, "error": error_msg}


def send_email_async(to, subject, html, text=None):
    """
    Non-blocking High-Priority Asynchronous Email Dispatch.
    """
    def _worker():
        try:
            send_email(to, subject, html, text)
        except Exception as e:
            logger.error(f"[EMAIL ASYNC ERROR] Background thread error for '{subject}': {e}")

    thread = threading.Thread(target=_worker, name=f"email-worker-{to}", daemon=True)
    thread.start()
    return {"success": True, "message": "Email dispatch queued in background."}
