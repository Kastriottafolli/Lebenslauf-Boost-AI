"""Encrypted transactional mail outbox with verified TLS and recoverable leases."""

import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import smtplib
import ssl
import time
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import and_, or_, text, update

from backend.account_models import EmailOutbox
from backend.config import get_settings
from backend.services.account_service import now

MAIL_UNAVAILABLE = {
    "code": "MAIL_UNAVAILABLE",
    "message": "Der E-Mail-Versand ist gerade nicht verfügbar. Bitte später erneut versuchen.",
}


def ready():
    settings = get_settings()
    parsed = urlsplit(settings.site_url)
    transport_ready = bool(
        settings.smtp_enabled and settings.smtp_host.strip()
        and settings.smtp_username.strip() and settings.smtp_password
    )
    if settings.mail_transport == "https_relay":
        relay = urlsplit(settings.mail_relay_url)
        transport_ready = bool(
            relay.scheme == "https" and relay.hostname and not relay.username
            and not relay.password and not relay.query and not relay.fragment
            and len(settings.mail_relay_secret) >= 32
        )
        if settings.mail_relay_connect_ip:
            try:
                transport_ready = transport_ready and ipaddress.ip_address(
                    settings.mail_relay_connect_ip
                ).is_global
            except ValueError:
                transport_ready = False
    return bool(
        transport_ready
        and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", settings.smtp_from_email)
        and parsed.hostname
        and (parsed.scheme == "https" or not settings.secure_cookies and parsed.scheme == "http")
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def cipher(create=False):
    path = Path(get_settings().mail_key_file)
    if create and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as output:
                output.write(Fernet.generate_key())
    try:
        return Fernet(path.read_bytes().strip())
    except (OSError, ValueError):
        raise HTTPException(503, MAIL_UNAVAILABLE) from None


def ensure_ready():
    if not ready():
        raise HTTPException(503, MAIL_UNAVAILABLE)
    cipher(True)


def queue(db, account, recipient, purpose, token=None, language="de", expires_at=None):
    ensure_ready()
    payload = {"token": token, "language": language}
    message = EmailOutbox(
        account_id=account.id,
        recipient=recipient,
        purpose=purpose,
        payload_cipher=cipher().encrypt(json.dumps(payload).encode()).decode(),
        expires_at=expires_at or now() + timedelta(hours=24),
    )
    db.add(message)
    return message


def queue_receipt(db, account, subject, text, language="de"):
    """A durable document snapshot is enqueued with the caller's transaction."""
    ensure_ready()
    if not isinstance(subject, str) or not 1 <= len(subject) <= 200 or "\n" in subject or "\r" in subject:
        raise ValueError("Invalid receipt subject")
    if not isinstance(text, str) or not 1 <= len(text) <= 150000:
        raise ValueError("Invalid receipt text")
    message = EmailOutbox(
        account_id=account.id, recipient=account.email, purpose="receipt",
        payload_cipher=cipher().encrypt(json.dumps({"language": language, "subject": subject, "text": text}, ensure_ascii=False).encode()).decode(),
        expires_at=now() + timedelta(days=7),
    )
    db.add(message)
    return message


COPY = {
    "de": {
        "verify": ("Bestätige deine E-Mail-Adresse", "Willkommen bei TafolliBoost! Bestätige deine E-Mail-Adresse, um dein Konto zu aktivieren.", "E-Mail bestätigen"),
        "reset": ("Dein TafolliBoost-Passwort zurücksetzen", "Du hast einen Link zum Zurücksetzen deines Passworts angefordert. Lege über diesen Link ein neues Passwort fest.", "Passwort zurücksetzen"),
        "change_email": ("Bestätige deine neue E-Mail-Adresse", "Bestätige diese neue E-Mail-Adresse für dein TafolliBoost-Konto. Danach musst du dich erneut anmelden.", "Neue E-Mail bestätigen"),
        "email_change_notice": ("Eine neue E-Mail-Adresse wurde angefordert", "Für dein TafolliBoost-Konto wurde eine Änderung der E-Mail-Adresse angefordert. Wenn du das nicht warst, ändere dein Passwort und kontaktiere info@tafolli.net.", ""),
        "password_changed": ("Dein TafolliBoost-Passwort wurde geändert", "Dein Passwort wurde geändert. Wenn du das nicht warst, setze es sofort zurück und kontaktiere info@tafolli.net.", ""),
        "ignore": "Wenn du diese Nachricht nicht angefordert hast, ignoriere sie. Teile diesen persönlichen Link nicht.",
        "expiry": "Der Link ist einmalig und gültig bis",
    },
    "en": {
        "verify": ("Confirm your email address", "Welcome to TafolliBoost! Confirm your email address to activate your account.", "Confirm email"),
        "reset": ("Reset your TafolliBoost password", "You requested a password reset. Choose a new password using this link.", "Reset password"),
        "change_email": ("Confirm your new email address", "Confirm this new email address for your TafolliBoost account. You will need to sign in again afterwards.", "Confirm new email"),
        "email_change_notice": ("An email address change was requested", "Someone requested an email address change for your TafolliBoost account. If this was not you, change your password and contact info@tafolli.net.", ""),
        "password_changed": ("Your TafolliBoost password was changed", "Your password was changed. If this was not you, reset it immediately and contact info@tafolli.net.", ""),
        "ignore": "If you did not request this message, ignore it. Do not share this personal link.",
        "expiry": "This one-time link is valid until",
    },
    "sq": {
        "verify": ("Konfirmo adresën tënde të emailit", "Mirë se erdhe në TafolliBoost! Konfirmo adresën e emailit për të aktivizuar llogarinë.", "Konfirmo emailin"),
        "reset": ("Rivendos fjalëkalimin e TafolliBoost", "Ke kërkuar rivendosjen e fjalëkalimit. Zgjidh një fjalëkalim të ri përmes kësaj lidhjeje.", "Rivendos fjalëkalimin"),
        "change_email": ("Konfirmo adresën e re të emailit", "Konfirmo këtë adresë të re për llogarinë tënde TafolliBoost. Më pas duhet të hysh përsëri.", "Konfirmo emailin e ri"),
        "email_change_notice": ("U kërkua ndryshimi i adresës së emailit", "U kërkua ndryshimi i emailit për llogarinë tënde TafolliBoost. Nëse nuk ishe ti, ndrysho fjalëkalimin dhe kontakto info@tafolli.net.", ""),
        "password_changed": ("Fjalëkalimi yt i TafolliBoost u ndryshua", "Fjalëkalimi u ndryshua. Nëse nuk ishe ti, rivendose menjëherë dhe kontakto info@tafolli.net.", ""),
        "ignore": "Nëse nuk e kërkove këtë mesazh, injoroje. Mos e ndaj këtë lidhje personale.",
        "expiry": "Kjo lidhje përdoret vetëm një herë dhe është e vlefshme deri më",
    },
}


def message_for(row, payload):
    settings = get_settings()
    language = payload.get("language") if payload.get("language") in COPY else "de"
    copy = COPY[language]
    if row.purpose == "receipt":
        subject, intro, _button = payload["subject"], payload["text"], ""
    else:
        subject, intro, _button = copy[row.purpose]
    message = EmailMessage()
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = row.recipient
    message["Subject"] = subject
    message["Message-ID"] = f"<{row.id}@{settings.smtp_from_email.split('@')[1]}>"
    message["Auto-Submitted"] = "auto-generated"
    content = intro + "\n\n"
    link = None
    if payload.get("token"):
        fragment = "reset-password" if row.purpose == "reset" else "verify-email"
        link = (
            settings.site_url.rstrip("/")
            + "/?"
            + urlencode({"lang": language})
            + "#"
            + urlencode({fragment: payload["token"]})
        )
        content += link + "\n\n" + copy["expiry"] + " " + row.expires_at.isoformat() + " UTC.\n\n"
    if row.purpose != "receipt":
        content += copy["ignore"] + "\n\n"
    content += "TafolliBoost · info@tafolli.net\n"
    message.set_content(content)
    safe_content = html.escape(content).replace("\n", "<br>")
    if link:
        safe_content = safe_content.replace(
            html.escape(link),
            '<a href="' + html.escape(link, quote=True)
            + '" style="display:inline-block;background:#087e8b;color:white;text-decoration:none;'
            + 'border-radius:10px;padding:14px 20px;font-weight:bold">'
            + html.escape(_button) + '</a>',
        )
    message.add_alternative(
        '<!doctype html><html><body style="margin:0;background:#eef3f7;font-family:Arial,sans-serif;color:#17283b">'
        '<table role="presentation" style="width:100%;padding:24px"><tr><td align="center">'
        '<table role="presentation" style="max-width:580px;width:100%;background:white;border-radius:18px;padding:28px">'
        '<tr><td style="color:#087e8b;font-size:24px;font-weight:bold">TafolliBoost</td></tr>'
        f'<tr><td><h1 style="font-size:24px">{html.escape(subject)}</h1>'
        f'<p style="font-size:16px;line-height:1.65;overflow-wrap:anywhere">{safe_content}</p></td></tr>'
        '</table></td></tr></table></body></html>',
        subtype="html",
    )
    return message


def send_message(message):
    settings = get_settings()
    if settings.mail_transport == "https_relay":
        payload = {
            "recipient": str(message["To"]), "subject": str(message["Subject"]),
            "text": message.get_body(preferencelist=("plain",)).get_content(),
            "html": message.get_body(preferencelist=("html",)).get_content(),
        }
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        timestamp, nonce = str(int(time.time())), secrets.token_urlsafe(24)
        signature = hmac.new(
            settings.mail_relay_secret.encode(),
            timestamp.encode() + b"\n" + nonce.encode() + b"\n" + raw,
            hashlib.sha256,
        ).hexdigest()
        headers = {"Content-Type": "application/json", "X-Tafolli-Timestamp": timestamp,
                   "X-Tafolli-Nonce": nonce, "X-Tafolli-Signature": signature}
        if settings.mail_relay_connect_ip:
            address = ipaddress.ip_address(settings.mail_relay_connect_ip)
            if not address.is_global:
                raise ValueError("Relay pin must be a public operator-selected address")
            original = httpx.URL(settings.mail_relay_url)
            headers["Host"] = original.host + (":" + str(original.port) if original.port and original.port != 443 else "")
            pinned_url = original.copy_with(host=str(address))
            with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
                request = client.build_request(
                    "POST", pinned_url, content=raw, headers=headers,
                    extensions={"sni_hostname": original.host},
                )
                response = client.send(request)
        else:
            response = httpx.post(
                settings.mail_relay_url, content=raw, timeout=15, follow_redirects=False,
                trust_env=False, headers=headers,
            )
        data = response.json() if response.status_code == 200 else None
        if not isinstance(data, dict) or data.get("accepted") is not True:
            raise ValueError("Transactional relay unavailable")
        return
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        transport = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
    else:
        transport = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with transport as smtp:
        if settings.smtp_security == "starttls":
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def drain(limit=20, session_factory=None):
    """At-least-once delivery; stable message IDs and single-use links make retries safe."""
    if not ready():
        return {"sent": 0, "failed": 0}
    from backend.database import SessionLocal

    factory = session_factory or SessionLocal
    totals = {"sent": 0, "failed": 0}
    for _ in range(limit):
        with factory() as db:
            if db.bind.dialect.name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            timestamp = now()
            db.query(EmailOutbox).filter(
                EmailOutbox.expires_at <= timestamp, EmailOutbox.payload_cipher.is_not(None)
            ).update({"status": "failed", "payload_cipher": None, "lease_until": None})
            row = db.query(EmailOutbox).filter(
                EmailOutbox.expires_at > timestamp,
                EmailOutbox.next_attempt_at <= timestamp,
                or_(EmailOutbox.status == "pending", and_(EmailOutbox.status == "sending", EmailOutbox.lease_until <= timestamp)),
            ).order_by(EmailOutbox.created_at).first()
            if row is None:
                db.commit()
                break
            row.status = "sending"
            row.attempts += 1
            row.lease_until = timestamp + timedelta(minutes=2)
            row_id, lease = row.id, row.lease_until
            try:
                payload = json.loads(cipher().decrypt(row.payload_cipher.encode()))
                message = message_for(row, payload)
            except (HTTPException, InvalidToken, ValueError, KeyError, AttributeError):
                row.status, row.payload_cipher, row.lease_until = "failed", None, None
                db.commit()
                totals["failed"] += 1
                continue
            attempt = row.attempts
            db.commit()
        successful = False
        try:
            send_message(message)
            successful = True
        except (OSError, smtplib.SMTPException, ValueError, httpx.HTTPError):
            # Never log SMTP responses or message content: they may include secrets.
            pass
        with factory() as db:
            values = {"lease_until": None}
            if successful:
                values.update(status="sent", payload_cipher=None, sent_at=now())
            elif attempt >= 8:
                values.update(status="failed", payload_cipher=None)
            else:
                values.update(status="pending", next_attempt_at=now() + timedelta(seconds=min(3600, 30 * 2 ** (attempt - 1))))
            changed = db.execute(update(EmailOutbox).where(
                EmailOutbox.id == row_id, EmailOutbox.status == "sending", EmailOutbox.lease_until == lease
            ).values(**values)).rowcount
            db.commit()
            if changed:
                totals["sent" if successful else "failed"] += 1
    return totals
