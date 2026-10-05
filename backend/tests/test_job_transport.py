"""Regression checks for verified HTTPS imports without a system CA bundle."""

import socket
import ssl
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from backend.services import job_service


def test_importer_has_trusted_roots_even_without_system_certificates(monkeypatch):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert not context.get_ca_certs()
    monkeypatch.setattr(ssl, "create_default_context", lambda: context)
    connection = job_service.PinnedHTTPSConnection("example.com", "93.184.216.34", 8)
    assert connection._context.get_ca_certs()
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    connection.close()


def test_pinned_connection_checks_original_hostname_and_closes_failed_socket(monkeypatch):
    connection = job_service.PinnedHTTPSConnection("jobs.example.com", "93.184.216.34", 8)
    raw_socket = Mock()
    connect = Mock(return_value=raw_socket)
    monkeypatch.setattr(socket, "create_connection", connect)
    connection._context = Mock()
    connection._context.wrap_socket.side_effect = ssl.SSLCertVerificationError("bad certificate")
    with pytest.raises(ssl.SSLCertVerificationError):
        connection.connect()
    connect.assert_called_once_with(("93.184.216.34", 443), 8)
    connection._context.wrap_socket.assert_called_once_with(
        raw_socket, server_hostname="jobs.example.com"
    )
    raw_socket.close.assert_called_once()


def test_invalid_certificate_never_retries_with_verification_disabled(monkeypatch):
    monkeypatch.setattr(
        job_service, "public_address", lambda url: ("example.com", "93.184.216.34", "/job")
    )
    connection = Mock()
    connection.request.side_effect = ssl.SSLCertVerificationError("bad certificate")
    create = Mock(return_value=connection)
    monkeypatch.setattr(job_service, "PinnedHTTPSConnection", create)
    with pytest.raises(HTTPException) as caught:
        job_service.fetch_page("https://example.com/job")
    assert caught.value.status_code == 422
    assert "HTTPS-Zertifikat" in caught.value.detail
    create.assert_called_once()
    connection.close.assert_called_once()


def test_public_redirect_cannot_fetch_internal_address(monkeypatch):
    def resolve(host, *args, **kwargs):
        address = "127.0.0.1" if host == "localhost" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    response = Mock(status=302)
    response.getheader.return_value = "https://localhost/private"
    connection = Mock()
    connection.getresponse.return_value = response
    create = Mock(return_value=connection)
    monkeypatch.setattr(job_service, "PinnedHTTPSConnection", create)
    with pytest.raises(HTTPException) as caught:
        job_service.fetch_page("https://example.com/job")
    assert caught.value.status_code == 422
    assert "Private/interne" in caught.value.detail
    create.assert_called_once()
    connection.close.assert_called_once()
