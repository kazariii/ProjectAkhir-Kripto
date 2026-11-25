"""ctypes transport adapter; cryptographic protocol lives in the shared C++ Channel."""
import ctypes as C
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "evidence/local/pqc-session-build/libpqc-session.so"
IDENTITY_SIZE = 3139
# Must equal PQC_TOPIC_PREFIX in firmware/include/pqc_broker.h for the same broker.
TOPIC_PREFIX = "lab/kimia/pqc/session"


def topics(prefix=TOPIC_PREFIX):
    """Session (up, down) topics. A prefix avoids collisions; it grants no access."""
    if not prefix or prefix.endswith("/") or any(c in prefix for c in "+#"):
        raise ValueError("Invalid MQTT topic prefix")
    return prefix + "/up", prefix + "/down"


UP, DOWN = topics()


def now_ms():
    return time.monotonic_ns() // 1_000_000


class Native:
    def __init__(self):
        self.lib = C.CDLL(str(LIBRARY))
        pointer, count, clock = C.c_void_p, C.POINTER(C.c_size_t), C.c_uint64
        self.lib.ps_create.argtypes = [C.c_int, pointer]
        self.lib.ps_create.restype = pointer
        self.lib.ps_free.argtypes = [pointer]
        self.lib.ps_keypair.argtypes = [pointer, pointer]
        self.lib.ps_begin.argtypes = [pointer, clock, pointer, count]
        self.lib.ps_retry.argtypes = [pointer, clock, pointer, count]
        self.lib.ps_renewal_due.argtypes = [pointer, clock]
        self.lib.ps_receive.argtypes = [pointer, pointer, C.c_size_t, clock, pointer, count, pointer, count]
        self.lib.ps_encrypt.argtypes = [pointer, pointer, C.c_size_t, clock, pointer, count]
        self.lib.ps_status.argtypes = [pointer, pointer]
        self.lib.ps_tick.argtypes = [pointer, clock]
        self.lib.ps_reset.argtypes = [pointer]

    def keypair(self):
        secret, public = C.create_string_buffer(1345), C.create_string_buffer(897)
        if self.lib.ps_keypair(secret, public) != 1:
            raise RuntimeError("FN-DSA key generation failed")
        return secret.raw, public.raw


class Channel:
    def __init__(self, native, identity, server=False):
        if len(identity) != IDENTITY_SIZE:
            raise ValueError("Wrong private identity length")
        self.lib = native.lib
        self.context = self.lib.ps_create(server, identity)
        if not self.context:
            raise RuntimeError("Cannot allocate cryptographic channel")

    def close(self):
        if self.context:
            self.lib.ps_free(self.context)
            self.context = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def begin(self):
        out, n = C.create_string_buffer(1519), C.c_size_t()
        if self.lib.ps_begin(self.context, now_ms(), out, C.byref(n)) != 1:
            raise RuntimeError("Cannot begin handshake")
        return out.raw[:n.value]

    def receive(self, packet):
        out, n = C.create_string_buffer(1519), C.c_size_t()
        plain, size = C.create_string_buffer(160), C.c_size_t()
        event = self.lib.ps_receive(self.context, packet, len(packet), now_ms(),
                                    out, C.byref(n), plain, C.byref(size))
        return event, out.raw[:n.value], plain.raw[:size.value]

    def encrypt(self, plain):
        out, n = C.create_string_buffer(1519), C.c_size_t()
        if self.lib.ps_encrypt(self.context, plain, len(plain), now_ms(), out, C.byref(n)) != 1:
            raise RuntimeError("No active session for encryption")
        return out.raw[:n.value]

    def tick(self):
        self.lib.ps_tick(self.context, now_ms())

    def retry(self):
        out, n = C.create_string_buffer(1519), C.c_size_t()
        self.lib.ps_retry(self.context, now_ms(), out, C.byref(n))
        return out.raw[:n.value]

    def renewal_due(self):
        return bool(self.lib.ps_renewal_due(self.context, now_ms()))

    def reset(self):
        self.lib.ps_reset(self.context)

    def status(self):
        sid = C.create_string_buffer(16)
        return bool(self.lib.ps_status(self.context, sid)), sid.raw.hex()
