import logging
from app.services.email_service import send_email, send_email_async
from app.config.config import Config

logger = logging.getLogger(__name__)

def _get_base_template(title, header_badge, body_content, cta_url=None, cta_text=None):
    """
    Standard Base HTML Email Wrapper for HavenSpace Real Estate Notifications.
    """
    frontend_url = Config.FRONTEND_URL or "http://localhost:5173"
    button_html = ""
    if cta_url and cta_text:
        full_url = cta_url if cta_url.startswith("http") else f"{frontend_url.rstrip('/')}/{cta_url.lstrip('/')}"
        button_html = f"""
        <div style="margin-top: 25px; margin-bottom: 25px; text-align: center;">
            <a href="{full_url}" style="background-color: #2563eb; color: #ffffff; padding: 12px 28px; text-decoration: none; font-size: 14px; font-weight: bold; border-radius: 8px; display: inline-block; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);">
                {cta_text}
            </a>
        </div>
        """

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; color: #334155;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 30px 15px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;" cellspacing="0" cellpadding="0">
                    <!-- Brand Header -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 24px 30px; text-align: left;">
                            <table width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td>
                                        <h1 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 800; letter-spacing: -0.5px;">
                                            Haven<span style="color: #38bdf8;">Space</span>
                                        </h1>
                                        <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: 600; tracking: 1px;">
                                            Real Estate Marketplace
                                        </p>
                                    </td>
                                    <td align="right">
                                        <span style="background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(56, 189, 248, 0.3);">
                                            {header_badge}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 32px 30px;">
                            {body_content}
                            {button_html}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; padding: 20px 30px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
                            <p style="margin: 0 0 6px 0; font-weight: 600;">HavenSpace Real Estate Marketplace</p>
                            <p style="margin: 0; font-size: 11px; color: #94a3b8;">
                                Automated transactional notification. Please do not reply directly to this email.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

# ==========================================
# CENTRAL NOTIFICATION SERVICE METHODS
# ==========================================

def send_welcome_email(user_email, user_name, role="customer"):
    """1. Send Welcome Email upon User Registration"""
    subject = "Welcome to HavenSpace Real Estate Marketplace"
    badge = "ACCOUNT CREATED"
    
    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Welcome, {user_name}!</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        Thank you for creating an account on <strong>HavenSpace</strong> as a <strong>{role.capitalize()}</strong>.
    </p>
    <div style="background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
        <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #1e293b;">Explore Marketplace Features:</h4>
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #475569; line-height: 1.6;">
            <li>Browse verified residential & commercial properties in Indian cities.</li>
            <li>Schedule site visits directly with verified agents & owners.</li>
            <li>Submit inquiries and track status in real-time on your dashboard.</li>
            <li>Save favorite properties and track market price updates.</li>
        </ul>
    </div>
    <p style="font-size: 13px; color: #64748b;">
        Log in to your personalized dashboard to get started with your real estate search.
    </p>
    """
    
    html = _get_base_template(subject, badge, body, cta_url="/login", cta_text="Access Your Dashboard")
    return send_email_async(user_email, subject, html)


def send_property_inquiry_email(owner_email, owner_name, buyer_name, buyer_email, buyer_phone, property_title, property_location, message):
    """2. Send Property Inquiry Notification to Property Owner / Agent"""
    subject = f"New Inquiry Received for '{property_title}'"
    badge = "NEW INQUIRY"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {owner_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        You have received a new inquiry from a buyer regarding your property listing on HavenSpace.
    </p>
    
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 20px 0;">
        <h4 style="margin: 0 0 10px 0; color: #2563eb; font-size: 15px; border-b: 1px solid #e2e8f0; pb: 8px;">
            {property_title}
        </h4>
        <p style="margin: 4px 0; font-size: 12px; color: #64748b;"><strong>Location:</strong> {property_location}</p>
    </div>

    <div style="background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <h4 style="margin: 0 0 10px 0; font-size: 13px; color: #0f172a; text-transform: uppercase; tracking: 0.5px;">Buyer Contact Details:</h4>
        <p style="margin: 4px 0; font-size: 13px; color: #334155;"><strong>Name:</strong> {buyer_name}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #334155;"><strong>Email:</strong> {buyer_email}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #334155;"><strong>Phone:</strong> {buyer_phone or 'Not provided'}</p>
        <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed #e2e8f0;">
            <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color: #475569;">Inquiry Message:</p>
            <p style="margin: 0; font-size: 13px; color: #1e293b; font-style: italic; background-color: #f1f5f9; padding: 10px; border-radius: 6px;">
                "{message}"
            </p>
        </div>
    </div>
    <p style="font-size: 13px; color: #64748b;">
        Log in to your agent portal to respond directly to this customer enquiry.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/dashboard", cta_text="View Agent Dashboard")
    return send_email_async(owner_email, subject, html)


def send_inquiry_confirmation_email(buyer_email, buyer_name, property_title, property_location, message):
    """3. Send Inquiry Confirmation to Buyer"""
    subject = "Your Property Inquiry Has Been Submitted"
    badge = "INQUIRY SENT"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {buyer_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        Your inquiry for <strong>"{property_title}"</strong> has been successfully delivered to the property representative.
    </p>

    <div style="background-color: #f8fafc; border-left: 4px solid #16a34a; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
        <p style="margin: 0 0 6px 0; font-size: 13px; font-weight: bold; color: #15803d;">Property Listing:</p>
        <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold; color: #0f172a;">{property_title}</p>
        <p style="margin: 0; font-size: 12px; color: #64748b;">Location: {property_location}</p>
    </div>

    <div style="background-color: #f1f5f9; padding: 14px; border-radius: 8px; margin-bottom: 20px;">
        <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color: #475569;">Your Message:</p>
        <p style="margin: 0; font-size: 13px; color: #334155; font-style: italic;">"{message}"</p>
    </div>

    <p style="font-size: 13px; color: #64748b;">
        The property owner or agent will contact you shortly via email or phone. You can track all active inquiries on your customer portal.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/customer/enquiries", cta_text="View My Enquiries")
    return send_email_async(buyer_email, subject, html)


def send_appointment_request_email(owner_email, owner_name, buyer_name, buyer_email, buyer_phone, property_title, property_location, visit_date, visit_time, message):
    """4. Send Visit / Appointment Request Notification to Owner / Agent"""
    subject = f"New Property Visit Request for '{property_title}'"
    badge = "VISIT REQUEST"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {owner_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        A prospective buyer has requested an on-site property visit for your listing.
    </p>

    <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <h4 style="margin: 0 0 8px 0; color: #1e40af; font-size: 15px;">Requested Schedule:</h4>
        <p style="margin: 4px 0; font-size: 13px; color: #1e3a8a;"><strong>Date:</strong> {visit_date}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #1e3a8a;"><strong>Time:</strong> {visit_time}</p>
    </div>

    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0 0 4px 0; font-size: 13px; color: #0f172a;"><strong>Property:</strong> {property_title}</p>
        <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;"><strong>Location:</strong> {property_location}</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 10px 0;">
        <p style="margin: 4px 0; font-size: 13px; color: #334155;"><strong>Visitor:</strong> {buyer_name}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #334155;"><strong>Email:</strong> {buyer_email}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #334155;"><strong>Phone:</strong> {buyer_phone or 'N/A'}</p>
        {f'<p style="margin: 8px 0 0 0; font-size: 12px; color: #475569; font-style: italic;">Note: "{message}"</p>' if message else ''}
    </div>

    <p style="font-size: 13px; color: #64748b;">
        Please log into your dashboard to confirm, reschedule, or manage this visit booking.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/agent/visits", cta_text="Manage Visit Schedule")
    return send_email_async(owner_email, subject, html)


def send_appointment_confirmation_email(buyer_email, buyer_name, property_title, property_location, visit_date, visit_time, notes=None):
    """5. Send Visit Request Submission Confirmation to Buyer"""
    subject = "Property Visit Request Submitted"
    badge = "VISIT SUBMITTED"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {buyer_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        Your site visit request for <strong>"{property_title}"</strong> has been successfully submitted to the agent.
    </p>

    <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0 0 4px 0; font-size: 13px; color: #0f172a;"><strong>Property:</strong> {property_title}</p>
        <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;"><strong>Location:</strong> {property_location}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #2563eb;"><strong>Requested Date:</strong> {visit_date}</p>
        <p style="margin: 4px 0; font-size: 13px; color: #2563eb;"><strong>Requested Time:</strong> {visit_time}</p>
    </div>

    <p style="font-size: 13px; color: #64748b;">
        You will receive an update once the agent approves or confirms your schedule.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/customer/visits", cta_text="Track Visit Requests")
    return send_email_async(buyer_email, subject, html)


def send_appointment_status_email(buyer_email, buyer_name, property_title, status, notes=None):
    """6. Send Visit Status Update Email (Confirmed, Rescheduled, Completed, Cancelled)"""
    status_lower = str(status).lower()
    
    if status_lower == "confirmed":
        subject = "Your Property Visit Has Been Confirmed!"
        badge = "VISIT CONFIRMED"
        badge_bg = "#16a34a"
        message_text = "Great news! The property agent has confirmed your site visit booking."
    elif status_lower == "rescheduled":
        subject = "Property Visit Rescheduled"
        badge = "RESCHEDULED"
        badge_bg = "#8b5cf6"
        message_text = "The property agent has proposed a rescheduled time for your site visit."
    elif status_lower == "cancelled":
        subject = "Property Visit Cancelled"
        badge = "CANCELLED"
        badge_bg = "#e11d48"
        message_text = "Your property visit request has been cancelled."
    elif status_lower == "completed":
        subject = "Property Visit Marked as Completed"
        badge = "VISIT COMPLETED"
        badge_bg = "#059669"
        message_text = "Thank you for completing your site visit!"
    else:
        subject = f"Property Visit Status: {status.capitalize()}"
        badge = status.upper()
        badge_bg = "#2563eb"
        message_text = f"Your property visit status is now {status}."

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {buyer_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">{message_text}</p>

    <div style="background-color: #f8fafc; border-left: 4px solid {badge_bg}; padding: 16px; margin: 20px 0; border-radius: 0 8px 8px 0;">
        <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold; color: #0f172a;">{property_title}</p>
        <p style="margin: 4px 0 0 0; font-size: 13px; font-weight: bold; color: {badge_bg};">
            Current Status: {status.capitalize()}
        </p>
        {f'<p style="margin: 8px 0 0 0; font-size: 12px; color: #64748b;">Agent Note: "{notes}"</p>' if notes else ''}
    </div>

    <p style="font-size: 13px; color: #64748b;">
        Log into your dashboard to view full appointment details or message the agent.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/customer/visits", cta_text="View My Visits")
    return send_email_async(buyer_email, subject, html)


def send_property_approved_email(owner_email, owner_name, property_title, property_location):
    """7. Send Property Approval Email to Agent / Owner"""
    subject = f"Your Property Listing '{property_title}' Has Been Approved!"
    badge = "LISTING APPROVED"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Congratulations, {owner_name}!</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        Your property submission <strong>"{property_title}"</strong> has been reviewed and <strong>APPROVED</strong> by the HavenSpace administration.
    </p>

    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold; color: #166534;">{property_title}</p>
        <p style="margin: 0 0 8px 0; font-size: 12px; color: #15803d;">Location: {property_location}</p>
        <p style="margin: 0; font-size: 12px; font-weight: bold; color: #166534;">Status: Publicly Live on Marketplace</p>
    </div>

    <p style="font-size: 13px; color: #64748b;">
        Your property is now visible to thousands of buyers and tenants across the marketplace.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/agent/properties", cta_text="View My Properties")
    return send_email_async(owner_email, subject, html)


def send_property_rejected_email(owner_email, owner_name, property_title, property_location, rejection_reason=None):
    """8. Send Property Rejection Email to Agent / Owner"""
    subject = f"Property Listing Update for '{property_title}'"
    badge = "REVIEW UPDATE"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {owner_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        Your property listing submission <strong>"{property_title}"</strong> required review modifications and was not published.
    </p>

    <div style="background-color: #fff1f2; border: 1px solid #fecdd3; border-radius: 12px; padding: 16px; margin: 20px 0;">
        <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold; color: #9f1239;">{property_title}</p>
        <p style="margin: 0 0 8px 0; font-size: 12px; color: #be123c;">Location: {property_location}</p>
        {f'<p style="margin: 8px 0 0 0; font-size: 13px; color: #9f1239; font-weight: bold;">Rejection Reason: <span style="font-weight: normal; font-style: italic;">"{rejection_reason}"</span></p>' if rejection_reason else ''}
    </div>

    <p style="font-size: 13px; color: #64748b;">
        You can edit and resubmit your listing details from your agent dashboard for re-inspection.
    </p>
    """

    html = _get_base_template(subject, badge, body, cta_url="/agent/properties", cta_text="Edit & Resubmit Listing")
    return send_email_async(owner_email, subject, html)


def send_password_reset_email(user_email, user_name, reset_token):
    """9. Send Secure Password Reset Email"""
    subject = "Password Reset Request - HavenSpace Marketplace"
    badge = "SECURITY VERIFICATION"
    
    frontend_url = Config.FRONTEND_URL or "http://localhost:5173"
    reset_link = f"{frontend_url.rstrip('/')}/reset-password?token={reset_token}"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {user_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        We received a request to reset your password for your HavenSpace account.
    </p>

    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin: 20px 0; text-align: center;">
        <p style="margin: 0 0 10px 0; font-size: 12px; font-weight: bold; color: #64748b; text-transform: uppercase;">Password Reset Link:</p>
        <a href="{reset_link}" style="background-color: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; font-size: 13px; font-weight: bold; border-radius: 8px; display: inline-block;">
            Reset Password Now
        </a>
        <p style="margin: 12px 0 0 0; font-size: 11px; color: #94a3b8;">
            Link valid for 1 hour.
        </p>
    </div>

    <div style="background-color: #f1f5f9; padding: 12px; border-radius: 6px; font-size: 12px; color: #475569;">
        <strong>Security Warning:</strong> If you did not request a password reset, please ignore this email or contact support immediately. Your account remains secure.
    </div>
    """

    html = _get_base_template(subject, badge, body)
    return send_email_async(user_email, subject, html)


def send_otp_email(user_email, user_name, otp_code):
    """10. Send Account Verification OTP Email via Gmail SMTP"""
    subject = "Verify Your HavenSpace Account"
    badge = "ACCOUNT VERIFICATION"

    body = f"""
    <h2 style="margin-top: 0; color: #0f172a; font-size: 18px;">Hello {user_name},</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
        Welcome to <strong>HavenSpace Real Estate Marketplace</strong>.
    </p>

    <div style="background-color: #f8fafc; border: 2px dashed #2563eb; border-radius: 12px; padding: 24px; margin: 20px 0; text-align: center;">
        <p style="margin: 0 0 10px 0; font-size: 12px; font-weight: bold; color: #64748b; text-transform: uppercase;">Your email verification code is:</p>
        <span style="font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #1e40af; font-family: monospace;">
            {otp_code}
        </span>
        <p style="margin: 12px 0 0 0; font-size: 12px; color: #64748b; font-weight: 600;">
            This code expires in 10 minutes.
        </p>
    </div>

    <div style="background-color: #f1f5f9; padding: 14px; border-radius: 8px; font-size: 12px; color: #475569; margin-bottom: 20px;">
        <strong>For your security:</strong>
        <ul style="margin: 6px 0 0 0; padding-left: 20px;">
            <li>Do not share this code with anyone.</li>
            <li>HavenSpace will never ask for your OTP over phone or chat.</li>
        </ul>
    </div>

    <p style="font-size: 13px; color: #64748b; margin-top: 10px;">
        If you did not create this account, you can safely ignore this email.
    </p>
    """

    html = _get_base_template(subject, badge, body)
    text_body = f"Hello {user_name},\n\nWelcome to HavenSpace Real Estate Marketplace.\n\nYour email verification code is: {otp_code}\n\nThis code expires in 10 minutes.\n\nFor your security:\n- Do not share this code with anyone.\n- HavenSpace will never ask for your OTP.\n\nIf you did not create this account, you can safely ignore this email."
    return send_email_async(user_email, subject, html, text_body)

