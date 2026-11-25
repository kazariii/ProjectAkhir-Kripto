#pragma once
// MQTT endpoint and topic prefix for every PQC firmware build (TCP/1883, no TLS).
//
// Default: private Mosquitto account from the git-ignored mqtt_diag_secrets.h.
// A build that defines PQC_BROKER_HOST uses an account-less public broker
// instead. There the broker offers no access control; the session protocol
// still provides confidentiality, integrity and peer authentication.
//
// PQC_TOPIC_PREFIX must equal the receiver's "topic_prefix" (tools/session/native.py
// holds the same default). The prefix avoids collisions; it is not a secret.
#include <cstdint>

#ifdef PQC_BROKER_HOST
constexpr char BROKER_HOST[] = PQC_BROKER_HOST;
constexpr const char* BROKER_USERNAME = nullptr;
constexpr const char* BROKER_PASSWORD = nullptr;
constexpr bool BROKER_PUBLIC = true;
#else
#include "mqtt_diag_secrets.h"
constexpr const char* BROKER_HOST = MQTT_DIAG_HOST;
constexpr const char* BROKER_USERNAME = MQTT_DIAG_USERNAME;
constexpr const char* BROKER_PASSWORD = MQTT_DIAG_PASSWORD;
constexpr bool BROKER_PUBLIC = false;
#endif
constexpr uint16_t BROKER_PORT = 1883;

#ifndef PQC_TOPIC_PREFIX
#define PQC_TOPIC_PREFIX "lab/kimia/pqc/session"
#endif
constexpr char SESSION_UP[] = PQC_TOPIC_PREFIX "/up";
constexpr char SESSION_DOWN[] = PQC_TOPIC_PREFIX "/down";
