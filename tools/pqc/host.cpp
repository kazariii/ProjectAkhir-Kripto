#include "pqc_proof.h"
extern "C" {
#include "fndsa.h"
}
#include "mlkem_native.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <vector>
#include <stdexcept>
#include <cstring>
#include <sys/stat.h>
namespace fs = std::filesystem;
using namespace pqc;
constexpr char MESSAGE[] = "{\"device_id\":\"pqc-proof-only\",\"temperature_c\":26.25,\"gas_raw\":321,\"gas_alarm\":false,\"temperature_alarm\":false}";
void require(bool ok, const char* error) { if (!ok) throw std::runtime_error(error); }
void write(const fs::path& p, const void* data, size_t n) {
    std::ofstream f(p, std::ios::binary | std::ios::trunc);
    require(bool(f.write(static_cast<const char*>(data), n)), "cannot write fixture");
    require(chmod(p.c_str(),0600) == 0, "cannot restrict fixture permissions");
}
void read(const fs::path& p, void* data, size_t n) {
    std::ifstream f(p, std::ios::binary);
    require(bool(f.read(static_cast<char*>(data), n)) && f.peek() == EOF, "missing or wrong-sized input");
}
void array(std::ostream& out, const char* name, const void* data, size_t n) {
    out << "static const unsigned char " << name << "[" << n << "] = {";
    const auto* p = static_cast<const uint8_t*>(data);
    for (size_t i=0; i<n; ++i) out << (i ? "," : "") << unsigned(p[i]);
    out << "};\n";
}
struct Fixture {
    Challenge challenge;
    uint8_t server_public[SIGN_PK];
    uint8_t device_secret[SIGN_SK];
    uint8_t kem_secret[KEM_SK];
    void load(const fs::path& d) {
        read(d/"challenge.bin", &challenge, sizeof(challenge));
        read(d/"server.pk", server_public, sizeof(server_public));
        read(d/"device.sk", device_secret, sizeof(device_secret));
        read(d/"kem.sk", kem_secret, sizeof(kem_secret));
    }
};
int main(int argc, char** argv) try {
    require(argc >= 3, "usage: pqc-proof init|respond|verify|selftest DIRECTORY [RESPONSE]");
    const std::string command = argv[1];
    const fs::path dir = argv[2];
    require(aead_self_test(), "RFC 8439 AEAD self-test failed");
    Fixture f{};
    if (command == "init") {
        require(!fs::exists(dir), "fixture directory already exists; choose a new directory");
        fs::create_directories(dir); require(chmod(dir.c_str(),0700) == 0, "fixture permission failed");
        uint8_t server_secret[SIGN_SK], coins[64];
        require(random_bytes(coins, sizeof(coins)), "CSPRNG failed");
        require(pqc_mlkem_keypair_derand(f.challenge.kem_public,f.kem_secret,coins) == 0, "ML-KEM keygen failed");
        require(fndsa_keygen(DEGREE,server_secret,f.server_public) == 1, "server FN-DSA keygen failed");
        require(fndsa_keygen(DEGREE,f.device_secret,f.challenge.device_public) == 1, "device FN-DSA keygen failed");
        require(random_bytes(f.challenge.salt,sizeof(f.challenge.salt)), "CSPRNG failed");
        constexpr char context[] = "lab-kimia/proof-v1/server";
        require(fndsa_sign(server_secret, SIGN_SK, context,sizeof(context)-1,FNDSA_HASH_ID_RAW,
            &f.challenge,CHALLENGE_BODY,f.challenge.signature,SIGNATURE) == SIGNATURE,"server sign failed");
        write(dir/"challenge.bin", &f.challenge,sizeof(f.challenge));
        write(dir/"server.pk", f.server_public,sizeof(f.server_public));
        write(dir/"device.sk", f.device_secret,sizeof(f.device_secret));
        write(dir/"kem.sk", f.kem_secret,sizeof(f.kem_secret));
        std::ofstream header(dir/"pqc_fixture.h");
        header << "#pragma once\n// PRIVATE disposable proof fixture. Never commit or deploy as production keys.\n";
        array(header,"PROOF_CHALLENGE", &f.challenge,sizeof(f.challenge));
        array(header,"PROOF_SERVER_PUBLIC",f.server_public,sizeof(f.server_public));
        array(header,"PROOF_DEVICE_SECRET",f.device_secret,sizeof(f.device_secret));
        header.close(); require(chmod((dir/"pqc_fixture.h").c_str(),0600) == 0,"header permission failed");
        std::cout << "{\"fixture_created\":true,\"private_material_printed\":false}\n";
        return 0;
    }
    f.load(dir);
    Response r{};
    Metrics metrics;
    uint8_t plaintext[MAX_MESSAGE] = {}; size_t length = 0;
    if (command == "respond") {
        require(argc == 4,"respond requires output path");
        require(respond(f.challenge,f.server_public,f.device_secret,
            reinterpret_cast<const uint8_t*>(MESSAGE),strlen(MESSAGE),r,metrics),"response failed");
        write(argv[3],&r,sizeof(r));
        std::cout << "{\"native_response\":true,\"server_verify_us\":" << metrics.server_verify_us
            << ",\"encapsulate_us\":" << metrics.encapsulate_us << ",\"sign_us\":" << metrics.sign_us
            << ",\"encrypt_us\":" << metrics.encrypt_us << "}\n";
        return 0;
    }
    require(argc == 4,"verify/selftest requires captured response path");
    read(argv[3], &r,sizeof(r));
    auto accepts = [&](const Challenge& c, const uint8_t* pk,const uint8_t* sk,const Response& response) {
        return pqc::open(c,pk,sk,response,plaintext,length);
    };
    require(accepts(f.challenge,f.server_public,f.kem_secret,r),"valid response rejected");
    require(length == strlen(MESSAGE) && memcmp(plaintext,MESSAGE,length) == 0,"plaintext mismatch");
    if (command == "verify") {
        std::cout << "{\"verified\":true,\"aead_rfc8439\":true,\"payload\":" << MESSAGE << "}\n";
        return 0;
    }
    require(command == "selftest","unknown command");
    unsigned checks = 0;
    auto rejected = [&](bool ok,const char* error) { require(!ok,error); checks++; };
    Challenge c = f.challenge; c.signature[10] ^= 1;
    rejected(verify_challenge(c,f.server_public),"altered server signature accepted");
    Response ignored{};
    rejected(respond(c,f.server_public,f.device_secret,reinterpret_cast<const uint8_t*>(MESSAGE),strlen(MESSAGE),ignored,metrics),"device accepted unauthenticated server");
    uint8_t wrong_pk[SIGN_PK]; memcpy(wrong_pk,f.server_public,SIGN_PK); wrong_pk[40] ^= 1;
    rejected(verify_challenge(f.challenge,wrong_pk),"wrong server identity accepted");
    c = f.challenge; c.kem_public[50] ^= 1;
    rejected(accepts(c,f.server_public,f.kem_secret,r),"altered challenge accepted");
    Response bad = r; bad.signature[5] ^= 1;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"bad device signature accepted");
    bad = r; bad.kem_ciphertext[5] ^= 1;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"altered KEM transcript accepted");
    bad = r; bad.ciphertext[5] ^= 1;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"altered ciphertext accepted");
    bad = r; bad.tag[5] ^= 1;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"altered tag accepted");
    bad = r; bad.nonce[5] ^= 1;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"altered nonce accepted");
    bad = r; bad.length[1] = 255;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"oversized length accepted");
    bad = r; bad.length[0] = 0; bad.length[1] = 0;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"empty length accepted");
    bad = r; bad.ciphertext[MAX_MESSAGE-1] = 1;
    rejected(accepts(f.challenge,f.server_public,f.kem_secret,bad),"noncanonical padding accepted");
    uint8_t wrong_sk[KEM_SK]; memcpy(wrong_sk,f.kem_secret,KEM_SK); wrong_sk[10] ^= 1;
    rejected(accepts(f.challenge,f.server_public,wrong_sk,r),"wrong KEM private key accepted");
    require(accepts(f.challenge,f.server_public,f.kem_secret,r),"positive control failed after negative tests");
    std::cout << "{\"positive_controls\":2,\"negative_checks\":" << checks << ",\"aead_rfc8439\":true,\"passed\":true}\n";
    return 0;
} catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n'; return 1;
}
