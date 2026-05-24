"""
Email notification service using the Resend API.

Sends transactional emails for:
- Critical vehicle alerts (speeding, geofence exit, offline)
- Welcome / account-created emails for new users
- Password reset emails

All functions are fire-and-forget: they log errors but never raise so that
the main request path is never blocked by email delivery failures.
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _api_key() -> Optional[str]:
    return os.getenv("RESEND_API_KEY")


def _from_email() -> str:
    return os.getenv("RESEND_FROM_EMAIL", "noreply@damascustransit.sy")


def _alert_recipients() -> list[str]:
    raw = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


# ---------------------------------------------------------------------------
# Low-level send
# ---------------------------------------------------------------------------


async def _send(*, to: list[str], subject: str, html: str) -> bool:
    """
    Send an email via the Resend API.

    Returns True on success, False on any failure.
    Never raises — callers should not depend on delivery.
    """
    api_key = _api_key()
    if not api_key:
        logger.debug("RESEND_API_KEY not set — skipping email to %s", to)
        return False

    if not to:
        logger.debug("No recipients — skipping email '%s'", subject)
        return False

    payload = {
        "from": _from_email(),
        "to": to,
        "subject": subject,
        "html": html,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code in (200, 201):
                logger.info("Email sent: '%s' -> %s", subject, to)
                return True
            else:
                logger.warning(
                    "Resend API error %s sending '%s': %s",
                    resp.status_code,
                    subject,
                    resp.text[:200],
                )
                return False
    except Exception as exc:
        logger.error("Failed to send email '%s': %s", subject, exc)
        return False


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def _base_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #f4f4f5; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 600px; margin: 32px auto; background: #fff;
                border-radius: 8px; overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
    .header {{ background: #1e40af; padding: 24px 32px; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 20px; font-weight: 600; }}
    .header p {{ color: #bfdbfe; margin: 4px 0 0; font-size: 13px; }}
    .body {{ padding: 32px; color: #374151; line-height: 1.6; }}
    .body h2 {{ margin-top: 0; font-size: 18px; color: #111827; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 9999px;
              font-size: 12px; font-weight: 600; text-transform: uppercase; }}
    .badge-high {{ background: #fee2e2; color: #991b1b; }}
    .badge-medium {{ background: #fef3c7; color: #92400e; }}
    .badge-low {{ background: #d1fae5; color: #065f46; }}
    .detail-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    .detail-table td {{ padding: 8px 0; border-bottom: 1px solid #f3f4f6;
                        font-size: 14px; }}
    .detail-table td:first-child {{ color: #6b7280; width: 40%; }}
    .footer {{ padding: 16px 32px; background: #f9fafb; font-size: 12px;
               color: #9ca3af; border-top: 1px solid #f3f4f6; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>Damascus Transit Platform</h1>
      <p>Automated notification</p>
    </div>
    <div class="body">{body}</div>
    <div class="footer">
      This is an automated message from the Damascus Transit Platform.
      Please do not reply to this email.
    </div>
  </div>
</body>
</html>"""


def _alert_html(
    alert_type: str,
    severity: str,
    title: str,
    vehicle_id: str,
    description: Optional[str],
    created_at: str,
) -> str:
    badge_class = (
        f"badge-{severity}" if severity in ("high", "medium", "low") else "badge-medium"
    )
    desc_row = (
        f"<tr><td>Description</td><td>{description}</td></tr>" if description else ""
    )
    body = f"""
    <h2>Vehicle Alert: {title}</h2>
    <p><span class="badge {badge_class}">{severity}</span></p>
    <table class="detail-table">
      <tr><td>Alert type</td><td>{alert_type}</td></tr>
      <tr><td>Vehicle ID</td><td>{vehicle_id}</td></tr>
      <tr><td>Time</td><td>{created_at}</td></tr>
      {desc_row}
    </table>
    <p style="font-size:13px;color:#6b7280;">
      Log in to the platform to review and resolve this alert.
    </p>
    """
    return _base_html(f"Alert: {title}", body)


def _welcome_html(full_name: str, email: str, role: str) -> str:
    body = f"""
    <h2>Welcome, {full_name}!</h2>
    <p>Your Damascus Transit Platform account has been created.</p>
    <table class="detail-table">
      <tr><td>Email</td><td>{email}</td></tr>
      <tr><td>Role</td><td>{role}</td></tr>
    </table>
    <p>Please log in and change your password on first sign-in.</p>
    """
    return _base_html("Welcome to Damascus Transit Platform", body)


def _password_reset_html(full_name: str, reset_url: str) -> str:
    body = f"""
    <h2>Password Reset</h2>
    <p>Hi {full_name},</p>
    <p>We received a request to reset your Damascus Transit Platform password.
       Click the button below to set a new password. The link expires in
       <strong>30 minutes</strong> and can only be used once.</p>
    <p style="margin:24px 0;">
      <a href="{reset_url}"
         style="background:#1e40af;color:#fff;text-decoration:none;
                padding:12px 24px;border-radius:6px;font-weight:600;
                display:inline-block;">Reset my password</a>
    </p>
    <p style="font-size:13px;color:#6b7280;">
      If the button doesn't work, copy and paste this URL into your browser:<br>
      <span style="word-break:break-all;">{reset_url}</span>
    </p>
    <p style="font-size:13px;color:#6b7280;">
      If you did not request a password reset, you can safely ignore this email.
      Your password will not change.
    </p>
    """
    return _base_html("Password Reset — Damascus Transit Platform", body)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


async def send_alert_email(
    *,
    alert_type: str,
    severity: str,
    title: str,
    vehicle_id: str,
    description: Optional[str] = None,
    created_at: str,
) -> bool:
    """
    Send a critical-alert notification email to all configured recipients.

    Recipients are read from ALERT_EMAIL_RECIPIENTS (comma-separated).
    If the env var is empty, the call is a no-op.
    """
    recipients = _alert_recipients()
    if not recipients:
        return False

    html = _alert_html(
        alert_type=alert_type,
        severity=severity,
        title=title,
        vehicle_id=vehicle_id,
        description=description,
        created_at=created_at,
    )
    severity_label = severity.upper()
    return await _send(
        to=recipients,
        subject=f"[{severity_label}] Transit Alert — {title}",
        html=html,
    )


async def send_welcome_email(
    *,
    full_name: str,
    email: str,
    role: str,
) -> bool:
    """Send an account-created welcome email to the new user."""
    html = _welcome_html(full_name=full_name, email=email, role=role)
    return await _send(
        to=[email],
        subject="Welcome to Damascus Transit Platform",
        html=html,
    )


async def send_password_reset_email(
    *,
    full_name: str,
    email: str,
    reset_url: str,
) -> bool:
    """Send a password-reset email containing a time-limited reset link."""
    html = _password_reset_html(full_name=full_name, reset_url=reset_url)
    return await _send(
        to=[email],
        subject="Reset your Damascus Transit Platform password",
        html=html,
    )
