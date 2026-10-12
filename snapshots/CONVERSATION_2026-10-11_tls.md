# Conversation snapshot — 2026-10-11 (mrfluffyv1.14.2)

## Task
"Real-TLS relay" — switch the presence relay's ghost weave from stdlib HMAC to real TLS (honest upgrade).

## Changes
- `wiretls.py` (new): pinned self-signed TLS with SSH-host-key style; uses cryptography or openssl CLI to generate `config/wire_tls/relay.pem` + `relay.key`; server/client contexts; fingerprint; env `MRFLUFFY_WIRE_TLS`/`MRFLUFFY_WIRE_CA`/`MRFLUFFY_WIRE_TLS_INSECURE`.
- `wiregate.py`: presence relay now serves HTTPS by default (listening socket wrapped with TLS). Client pins the cert; `_urlopen` uses SSL context. Ghost layer: XOR weave retired, v2 HMAC signatures kept for authenticity. Legacy v1 detection removed for secrecy but v2 used; key still gates sealed floor. `describe()` shows TLS state + fingerprint. CLI prints join instructions. Server uses per-conn wrapping removed, wrapped listening socket.
- Docs updated: `SNAPSHOT.md` (ghost+TLS explanation).
- Test coverage: same-host pinned cert works; insecure opt-out; wrong CA refused; sealed floor with shared key works; relay + client HTTPS handshakes verified.

## Verification
- `python3 -m py_compile wiregame.py wiregate.py wiretls.py wiresettings.py machinevision.py birdguard.py` OK.
- Offscreen tests show: entering market starts presence (https by default on same host), joining external https relay with insecure works, announce/peers work with pinned cert.
- `wiretls.py` generates cert once, fingerprints match.

## Fakegit
`~/fakegit/mrfluffyv1.14.2` (clean copy, includes `wiretls.py`).
