#include "pqc_session.h"
extern "C" {
#include "fndsa.h"
}
#include <new>
#include <cstring>
using namespace pqc;
using namespace pqc::session;
extern "C" {
void* ps_create(int server, const Identity* identity) {
    return identity ? new(std::nothrow) Channel(server ? Role::Server : Role::Client, *identity) : nullptr;
}
void ps_free(Channel* c) { delete c; }
int ps_keypair(uint8_t* secret, uint8_t* pub) { return fndsa_keygen(DEGREE, secret, pub); }
int ps_begin(Channel* c, uint64_t now, uint8_t* out, size_t* length) {
    Packet p; bool ok = c->begin(now, p); *length = p.size;
    std::memcpy(out, p.data, p.size); return ok;
}
int ps_retry(Channel* c, uint64_t now, uint8_t* out, size_t* length) {
    Packet p; bool ok = c->retry(now, p); *length = p.size;
    std::memcpy(out, p.data, p.size); return ok;
}
int ps_renewal_due(Channel* c, uint64_t now) { return c->renewal_due(now); }
int ps_receive(Channel* c, const uint8_t* input, size_t size, uint64_t now,
               uint8_t* out, size_t* out_length, uint8_t* plain, size_t* plain_length) {
    Packet p; auto event = c->receive(input, size, now, p, plain, *plain_length);
    *out_length = p.size; std::memcpy(out, p.data, p.size); return int(event);
}
int ps_encrypt(Channel* c, const uint8_t* plain, size_t size, uint64_t now,
               uint8_t* out, size_t* length) {
    Packet p; bool ok = c->encrypt(plain, size, now, p); *length = p.size;
    std::memcpy(out, p.data, p.size); return ok;
}
int ps_status(Channel* c, uint8_t* sid) {
    std::memcpy(sid, c->id(), 16); return c->active();
}
void ps_tick(Channel* c, uint64_t now) { c->tick(now); }
void ps_reset(Channel* c) { c->reset(); }
}
