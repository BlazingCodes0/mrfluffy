"""wiretls.py — real TLS for the wiregate presence relay.

The market's online layer used to hide its traffic with a homemade weave (a
PBKDF2-derived key driving an HMAC-SHA256 keystream). That was a weave, not a
vow. This module replaces the secrecy half with **real TLS** — the same thing
every other client on the wire uses — while staying honest about trust:

  * the relay owns ONE self-signed certificate (config/wire_tls/relay.pem),
    generated once, the way an SSH host owns its host key;
  * a player verifies the relay against that certificate, PINNED — it trusts
    the exact cert, not a public CA tree. A man-in-the-middle with some other
    valid certificate is refused, silently or not at all;
  * a player on the SAME host simply reads the cert from the shared path; a
    player on ANOTHER host is handed the cert (MRFLUFFY_WIRE_CA=/path/relay.pem)
    exactly as you would hand over a host key. Without it, the client refuses —
    it never silently trusts.

stdlib only for the living part (ssl); certificate generation uses the
`cryptography` module if present, else the `openssl` command line. No network,
no CA, no invented identity.

Env knobs
  MRFLUFFY_WIRE_TLS=0            turn the TLS floor off (plain HTTP; honest, weaker)
  MRFLUFFY_WIRE_CA=/path.pem     the relay cert a client pins (default: local cert)
  MRFLUFFY_WIRE_TLS_INSECURE=1   client skips verifying the cert (visible warning)

CLI:  python3 wiretls.py            # generate/refresh the cert, print its fingerprint
      python3 wiretls.py --fingerprint
"""
from __future__ import annotations
import hashlib, os, ssl, subprocess, sys, time
from pathlib import Path

FLUFFY = Path.home() / "mrfluffy"
CERT_DIR = FLUFFY / "config" / "wire_tls"
CERT_PEM = CERT_DIR / "relay.pem"
KEY_PEM = CERT_DIR / "relay.key"
COMMON_NAME = "mrfluffy-wire"

TLS_ENV = "MRFLUFFY_WIRE_TLS"
CA_ENV = "MRFLUFFY_WIRE_CA"
INSECURE_ENV = "MRFLUFFY_WIRE_TLS_INSECURE"


def enabled() -> bool:
    """TLS is on unless explicitly switched off. Explicit choice is honoured."""
    return os.environ.get(TLS_ENV, "1").strip().lower() not in ("0", "off", "no", "false")


def _wants_insecure() -> bool:
    return os.environ.get(INSECURE_ENV, "").strip().lower() in ("1", "on", "true", "yes")


def _gen_with_cryptography(cert: Path, key: Path) -> bool:
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except Exception:
        return False
    try:
        import datetime
        import ipaddress
        k = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                             COMMON_NAME)])
        san = x509.SubjectAlternativeName([
            x509.DNSName(COMMON_NAME),
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert_obj = (x509.CertificateBuilder()
                    .subject_name(name).issuer_name(name)
                    .public_key(k.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now - datetime.timedelta(days=1))
                    .not_valid_after(now + datetime.timedelta(days=3650))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None),
                                   critical=True)
                    .add_extension(san, critical=False)
                    .sign(k, hashes.SHA256()))
        key.write_bytes(k.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()))
        cert.write_bytes(cert_obj.public_bytes(serialization.Encoding.PEM))
        return True
    except Exception:
        return False


def _gen_with_openssl(cert: Path, key: Path) -> bool:
    try:
        r = subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "ec",
             "-pkeyopt", "ec_paramgen_curve:prime256v1",
             "-keyout", str(key), "-out", str(cert),
             "-days", "3650", "-nodes", "-subj", f"/CN={COMMON_NAME}",
             "-addext", f"subjectAltName=DNS:{COMMON_NAME},DNS:localhost,IP:127.0.0.1"],
            capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and cert.exists() and key.exists()
    except Exception:
        return False


def ensure_cert(cert: Path = CERT_PEM, key: Path = KEY_PEM) -> bool:
    """Generate the relay's self-signed cert once, if it is not already there."""
    if cert.exists() and key.exists():
        return True
    try:
        CERT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    ok = _gen_with_cryptography(cert, key) or _gen_with_openssl(cert, key)
    if not ok:
        return False
    try:
        os.chmod(key, 0o600)
    except Exception:
        pass
    return True


def fingerprint(cert: Path = CERT_PEM) -> str:
    """SHA-256 of the certificate's DER bytes, colon-separated — the pin."""
    try:
        pem = cert.read_bytes()
        der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
        h = hashlib.sha256(der).hexdigest().upper()
        return ":".join(h[i:i + 2] for i in range(0, 32, 2))
    except Exception:
        return ""


def _short_fp(fp: str) -> str:
    parts = (fp or "").split(":")
    return ":".join(parts[-8:]) if parts and parts[0] else "none"


def server_context(cert: Path = CERT_PEM, key: Path = KEY_PEM):
    """A TLS server context for the relay, or None when it cannot be built."""
    if not ensure_cert(cert, key):
        return None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(str(cert), str(key))
        return ctx
    except Exception:
        return None


def _ca_path() -> Path:
    p = os.environ.get(CA_ENV, "").strip()
    return Path(p).expanduser() if p else CERT_PEM


def client_context(ca: Path = None, insecure: bool = None):
    """A TLS client context that PINS the relay cert. Returns (ctx, info)."""
    if insecure is None:
        insecure = _wants_insecure()
    info = {"insecure": bool(insecure), "pinned": False, "ca": ""}
    if insecure:
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx, info
        except Exception:
            return None, info
    path = ca or _ca_path()
    try:
        if not path.exists():
            return None, info
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False          # we pin the exact cert, not a hostname
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=str(path))
        info["pinned"] = True
        info["ca"] = str(path)
        return ctx, info
    except Exception:
        return None, info


def describe(prefix: str = "tls") -> str:
    """One honest line about the TLS floor."""
    if not enabled():
        return f"{prefix}: off \u00b7 plain HTTP floor (set {TLS_ENV}=1 to seal it)"
    if not CERT_PEM.exists():
        return f"{prefix}: pending \u00b7 relay cert not made yet"
    fp = _short_fp(fingerprint())
    return (f"{prefix}: real \u00b7 pinned cert sha256 {fp} \u00b7 "
            f"verified against {CERT_PEM}")


if __name__ == "__main__":
    if "--fingerprint" in sys.argv:
        print(fingerprint() or "(no cert)")
    else:
        ok = ensure_cert()
        print(f"cert: {CERT_PEM}")
        print(f"key : {KEY_PEM}")
        print(f"made: {ok}")
        print(f"tls : {'enabled' if enabled() else 'disabled'}")
        print(describe())
