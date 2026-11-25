"""Offline, idempotent pin provisioning. Never prints keys or rotates existing identities."""
import argparse
import json
import os
from pathlib import Path
from tools.session.native import Native, ROOT, IDENTITY_SIZE


# The demo profile is for firmware shared outside the lab (Wokwi web). Its client
# secret key ships inside that firmware, so it must never equal the lab identity.
PROFILES = {
    "lab": (ROOT / "evidence/local/session-private", ROOT / "firmware/include/pqc_session_identity.h"),
    "demo": (ROOT / "evidence/local/session-demo", ROOT / "firmware/include/pqc_session_identity_demo.h"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="lab")
    profile = parser.parse_args().profile
    os.umask(0o077)
    folder, header = PROFILES[profile]
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    client, server = folder / "client.identity", folder / "server.identity"
    if client.exists() != server.exists():
        raise RuntimeError("Partial identity state; refusing implicit rotation")
    if not client.exists():
        native = Native()
        csk, cpk = native.keypair()
        ssk, spk = native.keypair()
        client.write_bytes(csk + cpk + spk)
        server.write_bytes(ssk + spk + cpk)
    c, s = client.read_bytes(), server.read_bytes()
    if len(c) != IDENTITY_SIZE or len(s) != IDENTITY_SIZE or c[1345:2242] != s[2242:] or s[1345:2242] != c[2242:]:
        raise RuntimeError("Invalid paired pinned identities")
    for path in (client, server):
        path.chmod(0o600)
    for name, (other, _) in PROFILES.items():
        other_client = other / "client.identity"
        if name != profile and other_client.exists():
            o = other_client.read_bytes()
            if {o[1345:2242], o[2242:]} & {c[1345:2242], c[2242:]}:
                raise RuntimeError("Identity profiles share public keys; refusing")
    fields = [c[:1345], c[1345:2242], c[2242:]]
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text('#pragma once\n#include "pqc_session.h"\n// PRIVATE: do not commit or upload.\n'
                      'static const pqc::session::Identity SESSION_IDENTITY = {\n' +
                      ',\n'.join('{' + ','.join('0x%02x' % b for b in field) + '}' for field in fields) + '\n};\n')
    header.chmod(0o600)
    print(json.dumps({"provisioned": True, "profile": profile, "rotated": False, "keys_printed": False}))


if __name__ == "__main__":
    main()
