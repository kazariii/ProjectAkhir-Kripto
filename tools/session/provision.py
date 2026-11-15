"""Offline, idempotent pin provisioning. Never prints keys or rotates existing identities."""
import json
import os
from pathlib import Path
from tools.session.native import Native, ROOT, IDENTITY_SIZE


def main():
    os.umask(0o077)
    folder = ROOT / "evidence/local/session-private"
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
    fields = [c[:1345], c[1345:2242], c[2242:]]
    header = ROOT / "firmware/include/pqc_session_identity.h"
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text('#pragma once\n#include "pqc_session.h"\n// PRIVATE: do not commit or upload.\n'
                      'static const pqc::session::Identity SESSION_IDENTITY = {\n' +
                      ',\n'.join('{' + ','.join('0x%02x' % b for b in field) + '}' for field in fields) + '\n};\n')
    header.chmod(0o600)
    print(json.dumps({"provisioned": True, "rotated": False, "keys_printed": False}))


if __name__ == "__main__":
    main()
