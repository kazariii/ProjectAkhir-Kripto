#include "pqc_session.h"
extern "C" {
#include "fndsa.h"
}
#include <cstdio>
#include <cstdlib>
#include <cstring>
using namespace pqc;
using namespace pqc::session;
namespace {
unsigned checks = 0;
void check(bool ok, const char* why) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", why); std::exit(1); }
    ++checks;
}
Identity client = {}, server = {};
Event receive(Channel& c, const Packet& in, uint64_t now, Packet& out) {
    uint8_t plain[MAX_MESSAGE]; size_t n;
    return c.receive(in.data, in.size, now, out, plain, n);
}
struct Pair {
    Channel c{Role::Client, client}, s{Role::Server, server};
    Packet m1, m2, m3, m4, ignored;
    void start(uint64_t now = 100) {
        check(c.begin(now, m1), "client hello");
        check(receive(s, m1, now+1, m2) == Event::Send, "server hello");
    }
    void key(uint64_t now = 102) {
        const bool previously_active = c.active();
        uint8_t previous_id[16]; std::memcpy(previous_id, c.id(), 16);
        check(receive(c, m2, now, m3) == Event::Send, "verify server and client key");
        check(c.active() == previously_active && !std::memcmp(previous_id, c.id(), 16), "client waits for confirmation before committing new epoch");
    }
    void finish(uint64_t now = 103) {
        check(receive(s, m3, now, m4) == Event::Established, "server verifies client and key possession");
        check(receive(c, m4, now+1, ignored) == Event::Established, "client verifies server key possession");
        check(c.active() && s.active() && !std::memcmp(c.id(), s.id(), 16), "matching active session ids");
    }
    void handshake(uint64_t now = 100) { start(now); key(now+2); finish(now+3); }
};
void rejected(Channel& c, Packet p, size_t offset, uint64_t now, const char* why) {
    p.data[offset] ^= 1; Packet out;
    check(receive(c, p, now, out) == Event::Rejected && out.size == 0, why);
}
}
int main() {
    check(fndsa_keygen(DEGREE, client.secret, client.public_key) == 1 &&
          fndsa_keygen(DEGREE, server.secret, server.public_key) == 1, "generate fixture identities");
    std::memcpy(client.peer, server.public_key, SIGN_PK); std::memcpy(server.peer, client.public_key, SIGN_PK);
    Pair p; Packet out, data;
    const uint8_t text[] = "authenticated probe";
    check(!p.c.encrypt(text, sizeof(text), 0, data), "no plaintext before session");
    p.start();
    rejected(p.c, p.m2, 4, 102, "wrong frame type");
    rejected(p.c, p.m2, 0, 102, "wrong profile magic");
    rejected(p.c, p.m2, 3, 102, "wrong version");
    rejected(p.c, p.m2, 1518, 102, "modified server signature");
    rejected(p.c, p.m2, 53, 102, "modified KEM public key");
    p.key();
    rejected(p.s, p.m3, 5, 103, "modified KEM ciphertext");
    rejected(p.s, p.m3, 773, 103, "modified client signature");
    rejected(p.s, p.m3, 1454, 103, "invalid client key confirmation");
    check(!p.s.active(), "bad client confirmation never establishes server");
    check(receive(p.s, p.m3, 103, p.m4) == Event::Established, "valid after invalid client finish");
    rejected(p.c, p.m4, 36, 104, "invalid server key confirmation");
    rejected(p.c, p.m4, 5, 104, "invalid finished session id");
    check(!p.c.active(), "invalid server confirmation leaves client pending");
    check(receive(p.c, p.m4, 104, out) == Event::Established, "valid after invalid server finish");
    check(receive(p.s, p.m3, 105, out) == Event::Send && out.size == FINISH_SIZE &&
          !std::memcmp(out.data, p.m4.data, out.size), "duplicate authenticated M3 only resends cached M4");
    check(p.c.encrypt(text, sizeof(text), 106, data), "client data encrypted");
    Channel unopened(Role::Server, server);
    check(receive(unopened, data, 107, out) == Event::Rejected, "data rejected before session");
    rejected(p.s, data, 5, 107, "unknown session id");
    rejected(p.s, data, 206, 107, "bad data tag");
    rejected(p.s, data, 31, 107, "bad ciphertext");
    rejected(p.s, data, 29, 107, "tampered authenticated length");
    rejected(p.s, data, 21, 107, "tampered counter does not advance replay state");
    rejected(p.s, data, 31+sizeof(text), 107, "noncanonical padding");
    Packet too_short = data; --too_short.size;
    check(receive(p.s, too_short, 107, out) == Event::Rejected, "truncated data");
    Packet zero_counter = data; zero_counter.data[21] = 0;
    check(receive(p.s, zero_counter, 107, out) == Event::Rejected, "nonce zero reserved for finished");
    Packet oversized = data; oversized.data[29] = 161;
    check(receive(p.s, oversized, 107, out) == Event::Rejected, "oversized plaintext length");
    uint8_t plain[MAX_MESSAGE]; size_t n = 0;
    check(p.s.receive(data.data, data.size, 107, out, plain, n) == Event::Plaintext &&
          n == sizeof(text) && !std::memcmp(plain, text, n), "valid payload after corrupt attempts (counter unchanged)");
    check(receive(p.s, data, 108, out) == Event::Rejected, "duplicate counter rejected");
    check(p.s.encrypt(text, sizeof(text), 108, out), "server reply encrypted");
    check(std::memcmp(out.data+31, data.data+31, sizeof(text)) != 0, "directional keys yield distinct ciphertext at counter one");
    check(receive(p.s, out, 109, data) == Event::Rejected, "reflected directional ciphertext rejected");
    check(p.c.receive(out.data, out.size, 109, data, plain, n) == Event::Plaintext, "encrypted reverse direction works");
    // Unauthenticated rekey requests must preserve the active session.
    check(p.c.begin(110, p.m1), "begin rekey");
    check(receive(p.s, p.m1, 111, p.m2) == Event::Send && p.s.active(), "server preserves active during pending rekey");
    Packet bad_key = p.m3;
    check(receive(p.s, bad_key, 112, out) == Event::Send && p.s.active(), "cached M4 during rekey cannot destroy active session");
    check(p.c.encrypt(text, sizeof(text), 113, data) && receive(p.s, data, 114, out) == Event::Plaintext, "active data survives invalid rekey");
    uint8_t old_id[16]; std::memcpy(old_id, p.c.id(), 16);
    p.key(115); p.finish(116);
    check(std::memcmp(old_id, p.c.id(), 16) != 0, "new handshake gets fresh session");
    check(receive(p.s, data, 118, out) == Event::Rejected, "old epoch rejected after rekey");
    p.c.tick(300117); p.s.tick(300116);
    check(!p.c.active() && !p.s.active() && !p.c.encrypt(text, sizeof(text), 300118, out), "session expiry closes data path");
    Pair timeout; timeout.start();
    check(receive(timeout.c, timeout.m2, HANDSHAKE_MS+100, out) == Event::Rejected, "pending handshake expiry");
    Pair fresh; fresh.start();
    Packet old_hello = fresh.m2;
    fresh.start(200);
    check(receive(fresh.c, old_hello, 202, out) == Event::Rejected, "server hello replay against fresh nonce");
    fresh.key(203); fresh.finish(204);
    fresh.c.reset(); fresh.s.reset();
    check(!fresh.c.active() && !fresh.s.active() && !fresh.c.encrypt(text, sizeof(text), 206, out), "disconnect reset erases active state");
    Identity wrong = client; wrong.peer[100] ^= 1;
    Channel untrusted(Role::Client, wrong);
    check(untrusted.begin(300, out), "untrusted client begins");
    check(receive(untrusted, fresh.m2, 301, out) == Event::Rejected, "wrong pinned server identity rejected");
    Packet wrong_binding = fresh.m1; wrong_binding.data[5] ^= 1;
    check(receive(fresh.s, wrong_binding, 301, out) == Event::Rejected, "unknown identity binding rejected");
    Identity forged = client; std::memcpy(forged.secret, server.secret, SIGN_SK);
    Channel impostor(Role::Client, forged), verifier(Role::Server, server);
    Packet a, b, c;
    check(impostor.begin(400, a) && receive(verifier, a, 401, b) == Event::Send &&
          receive(impostor, b, 402, c) == Event::Send, "impostor copies legitimate public binding");
    check(receive(verifier, c, 403, out) == Event::Rejected && !verifier.active(), "server requires possession of pinned client secret");
    forged = server; std::memcpy(forged.secret, client.secret, SIGN_SK);
    Channel fake_server(Role::Server, forged), pinned_client(Role::Client, client);
    check(pinned_client.begin(500, a) && receive(fake_server, a, 501, b) == Event::Send,
          "fake server advertises expected public identity");
    check(receive(pinned_client, b, 502, out) == Event::Rejected, "client requires possession of pinned server secret");
    Pair loss; Packet retry, duplicate;
    check(!loss.c.retry(99, retry), "no retry before begin");
    loss.start();
    check(loss.c.retry(5100, retry) && retry.size == loss.m1.size &&
          !std::memcmp(retry.data, loss.m1.data, retry.size), "lost M2 retries exact M1");
    check(receive(loss.s, retry, 5101, duplicate) == Event::Send && duplicate.size == loss.m2.size &&
          !std::memcmp(duplicate.data, loss.m2.data, duplicate.size), "duplicate M1 returns exact cached challenge");
    loss.key(5102);
    check(receive(loss.s, loss.m3, 5103, loss.m4) == Event::Established, "server commits despite lost M4");
    check(loss.c.retry(10102, retry) && retry.size == loss.m3.size &&
          !std::memcmp(retry.data, loss.m3.data, retry.size), "lost M4 retries exact signed M3 and finished tag");
    rejected(loss.s, retry, 1454, 10103, "modified duplicate finish rejected");
    check(receive(loss.s, retry, 10103, duplicate) == Event::Send && duplicate.size == loss.m4.size &&
          !std::memcmp(duplicate.data, loss.m4.data, duplicate.size), "duplicate M3 recovers lost server finish");
    check(receive(loss.c, duplicate, 10104, out) == Event::Established, "client recovers lost M4");
    check(!loss.c.retry(10105, retry), "finished client cannot retry stale handshake");
    check(!loss.s.renewal_due(185102) && loss.s.renewal_due(185103), "server renewal margin uses its own clock");
    const uint8_t renew[] = "{\"renew_session\":true}";
    check(loss.s.encrypt(renew, sizeof(renew)-1, 185103, data), "server encrypts renewal before expiry");
    rejected(loss.c, data, 31, 10105, "forged renewal rejected with slow client clock");
    check(loss.c.receive(data.data, data.size, 10105, out, plain, n) == Event::Plaintext &&
          n == sizeof(renew)-1 && !std::memcmp(plain, renew, n), "authenticated renewal works despite clock skew");
    check(receive(loss.c, data, 10106, out) == Event::Rejected, "renewal replay rejected");
    check(loss.c.encrypt(text, sizeof(text), 10107, data) &&
          receive(loss.s, data, 185104, out) == Event::Plaintext, "data before duplicate M3");
    check(receive(loss.s, loss.m3, 185105, out) == Event::Send &&
          receive(loss.s, data, 185106, out) == Event::Rejected, "M3 retransmission cannot reset data replay counter");
    check(receive(loss.s, loss.m3, 305102, out) == Event::Send, "M3 retry just before expiry allowed");
    loss.s.tick(305103);
    check(!loss.s.active() && receive(loss.s, loss.m3, 305103, out) == Event::Rejected,
          "M3 retries do not extend key lifetime");
    Pair deadline; deadline.start();
    check(receive(deadline.s, deadline.m1, 120100, out) == Event::Send, "last duplicate M1 before pending expiry");
    deadline.key(120099);
    check(receive(deadline.s, deadline.m3, 120101, out) == Event::Rejected,
          "M1 retries do not extend pending deadline");
    check(!deadline.c.retry(120100, out), "expired pending state cannot retry");
    Pair restart; restart.start(); restart.key(); restart.s.reset();
    check(restart.c.retry(5102, retry) && receive(restart.s, retry, 5103, out) == Event::Rejected,
          "receiver restart has no old pending secret");
    restart.handshake(16000);
    check(restart.c.encrypt(text, sizeof(text), 16005, data) &&
          receive(restart.s, data, 16006, out) == Event::Plaintext, "fresh hello recovers receiver restart");
    std::printf("SESSION_NATIVE_RESULT {\"passed\":true,\"checks\":%u}\n", checks);
    return 0;
}
