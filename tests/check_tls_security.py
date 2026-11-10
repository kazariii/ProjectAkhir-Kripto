"""Actual ticket-06 confidentiality/integrity experiment on an isolated broker.

Requires Docker, OpenSSL, Wireshark dumpcap/tshark (Npcap on Windows).
No production configuration, credentials, services or data are accessed.
Usage: python tests/check_tls_security.py [--interface <loopback-interface>]
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid

from check_monitoring_stack import BROKER
from mqtt_probe import Probe
from tls_relay import TLSRelay, stamp


ROOT = Path(__file__).resolve().parents[1]
PROTECTED = "(tls.record.content_type == 23 || tls.record.opaque_type == 23)"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def executable(name, fallback):
    path = shutil.which(name) or fallback
    require(Path(path).is_file(), name + " is required")
    return path


def run(command):
    # Commands may contain disposable passwords. Never print command/errors.
    result = subprocess.run(command, capture_output=True, timeout=90)
    require(result.returncode == 0, "External tool failed: " + Path(command[0]).stem)
    return result.stdout.decode("utf-8", errors="replace")


@contextmanager
def capture(dumpcap, interface, path, ports):
    log = path.with_suffix(".capture.txt")
    with log.open("w") as output:
        process = subprocess.Popen([dumpcap, "-i", interface, "-f",
                                    "tcp and (" + " or ".join("port " + str(p) for p in ports) + ")",
                                    "-a", "duration:15", "-w", str(path)],
                                   stdout=output, stderr=output)
        try:
            deadline = time.monotonic() + 5
            while "File:" not in log.read_text(errors="replace"):
                require(process.poll() is None and time.monotonic() < deadline, "Capture failed to start")
                time.sleep(0.1)
            yield
            require(process.wait(timeout=20) == 0, "Capture did not complete")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def fields(tshark, path, display_filter, names, decode=()):
    # Disable decryption regardless of the user's Wireshark preferences.
    command = [tshark, "-n", "-r", str(path), "-o", "tls.keylog_file:"]
    for port, protocol in decode:
        command += ["-d", f"tcp.port=={port},{protocol}"]
    command += ["-Y", display_filter, "-T", "fields"]
    for name in names:
        command += ["-e", name]
    return [line.split("\t") for line in run(command).splitlines() if line]


def wire_bytes(tshark, path, display_filter):
    # Let Wireshark reassemble segments and retransmissions in each direction.
    result = []
    streams = {row[0] for row in fields(tshark, path, display_filter, ["tcp.stream"])}
    for stream in sorted(streams):
        directions = [bytearray(), bytearray()]
        followed = run([tshark, "-n", "-r", str(path), "-o", "tls.keylog_file:",
                        "-q", "-z", "follow,tcp,raw," + stream])
        for line in followed.splitlines():
            if re.fullmatch(r"\t?[0-9a-fA-F]+", line):
                directions[line.startswith("\t")].extend(bytes.fromhex(line.strip()))
        result.extend(directions)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default=r"\Device\NPF_Loopback" if os.name == "nt" else "lo")
    args = parser.parse_args()
    run_id = "ticket06-" + uuid.uuid4().hex[:12]
    output = ROOT / "evidence/local/ticket-06" / run_id
    output.mkdir(parents=True)
    report = {"run_id": run_id, "started_utc": stamp(), "scope": "isolated loopback Mosquitto; no EMQX mutation",
              "status": "running", "checks": [], "retry": False, "reconnect": False, "retained": False, "publish_qos": 1}
    step = "prerequisites"
    broker_started = False

    def record(name, **details):
        report["checks"].append(dict(check=name, **details))
        print("PASS: " + name, flush=True)

    try:
        openssl = executable("openssl", "C:/Program Files/Git/usr/bin/openssl.exe")
        dumpcap = executable("dumpcap", "C:/Program Files/Wireshark/dumpcap.exe")
        tshark = executable("tshark", "C:/Program Files/Wireshark/tshark.exe")
        report["runtime"] = {"python_tls": ssl.OPENSSL_VERSION, "broker_image": BROKER,
                             "tshark": run([tshark, "--version"]).splitlines()[0]}
        with tempfile.TemporaryDirectory(prefix=run_id) as directory:
            fixture = Path(directory)
            mount = f"type=bind,source={directory},target=/test"
            password = secrets.token_hex(24)
            topic = "demo/ticket06/" + run_id
            step = "isolated broker setup"
            # Disposable password stays in a temporary file, never arguments/evidence.
            (fixture / "passwords").write_text("demo:" + password + "\n", encoding="ascii")
            run(["docker", "run", "--rm", "--mount", mount, BROKER,
                 "mosquitto_passwd", "-U", "/test/passwords"])
            (fixture / "acl").write_text("user demo\ntopic readwrite " + topic + "\n", encoding="ascii")
            run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                 "-subj", "/CN=Ticket06 Demo CA", "-keyout", str(fixture / "ca.key"), "-out", str(fixture / "ca.pem")])
            run([openssl, "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost",
                 "-keyout", str(fixture / "server.key"), "-out", str(fixture / "server.csr")])
            (fixture / "extensions").write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n")
            run([openssl, "x509", "-req", "-days", "1", "-in", str(fixture / "server.csr"),
                 "-CA", str(fixture / "ca.pem"), "-CAkey", str(fixture / "ca.key"), "-CAcreateserial",
                 "-extfile", str(fixture / "extensions"), "-out", str(fixture / "server.pem")])
            (fixture / "mosquitto.conf").write_text(
                "user root\nper_listener_settings false\nallow_anonymous false\npassword_file /test/passwords\n"
                "acl_file /test/acl\nlistener 1883\nlistener 8883\ncertfile /test/server.pem\n"
                "keyfile /test/server.key\nlog_dest stdout\nlog_type all\n")
            broker_started = True
            # Loopback-only ephemeral ports; no production network or volumes.
            run(["docker", "run", "-d", "--name", run_id, "-p", "127.0.0.1::1883", "-p", "127.0.0.1::8883",
                 "--mount", mount + ",readonly", BROKER, "mosquitto", "-c", "/test/mosquitto.conf"])
            plain_port = int(run(["docker", "port", run_id, "1883"]).strip().rsplit(":", 1)[1])
            tls_port = int(run(["docker", "port", run_id, "8883"]).strip().rsplit(":", 1)[1])
            # Construct directly: create_default_context would honor SSLKEYLOGFILE.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(str(fixture / "ca.pem"))
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            require(context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname and context.keylog_filename is None,
                    "Certificate verification and no-keylog invariant")
            report["certificate_verification"] = {"ca_required": True, "hostname_checked": True, "keylog": False}

            def connect(port, tls_context=context):
                probe = Probe("127.0.0.1", port, tls_context)
                try:
                    require(probe.connect("t06-" + uuid.uuid4().hex[:16], "demo", password) == 0, "CONNACK must succeed")
                    return probe
                except BaseException:
                    probe.__exit__()
                    raise

            # Wait for actual readiness before capture/test; bounded, no publish retries.
            deadline = time.monotonic() + 15
            while True:
                try:
                    with connect(tls_port):
                        break
                except OSError:
                    require(time.monotonic() < deadline, "Broker readiness timeout")
                    time.sleep(0.2)

            for name, trust in (("plaintext", None), ("tls", context)):
                step = "confidentiality " + name
                port = plain_port if trust is None else tls_port
                marker = run_id + "-" + name
                payload = json.dumps({"marker": marker, "temperature_c": 25.5, "gas_raw": 1234}).encode()
                path = output / (name + ".pcapng")
                with capture(dumpcap, args.interface, path, [port]):
                    with connect(port, trust) as subscriber, connect(port, trust) as publisher:
                        require(subscriber.subscribe(topic) == 0, "SUBACK must succeed")
                        require(publisher.publish(topic, payload) == 0, "PUBACK must succeed")
                        require(subscriber.message() == (topic, payload), "Independent subscriber must match")
                streams = wire_bytes(tshark, path, "tcp.port == " + str(port))
                found = any(marker.encode() in stream for stream in streams)
                require(found == (name == "plaintext"), "Unexpected marker visibility")
                protected = fields(tshark, path, PROTECTED, ["frame.number"], [(port, "tls")]) if trust else []
                require(trust is None or bool(protected), "TLS application records missing")
                record(step, marker=marker, payload=payload.decode(), connack=0, suback=0, puback=0,
                       subscriber_received=True, marker_visible_in_tcp=found, tls_application_frames=len(protected),
                       capture=path.name, port=port)

            step = "integrity before / tampered / after"
            path = output / "integrity.pcapng"
            with connect(tls_port) as subscriber:
                require(subscriber.subscribe(topic) == 0, "Independent subscriber SUBACK")
                with capture(dumpcap, args.interface, path, [tls_port]):
                    for stage in ("before", "tampered", "after"):
                        stage_dir = output / stage
                        stage_dir.mkdir()
                        marker = run_id + "-" + stage
                        payload = json.dumps({"marker": marker, "temperature_c": 26.5}).encode()
                        with TLSRelay(tls_port, stage_dir) as relay:
                            with connect(relay.port) as publisher:
                                tls_version, cipher = publisher.connection.version(), publisher.connection.cipher()[0]
                                if stage == "tampered":
                                    relay.arm_after_connack()
                                    try:
                                        publisher.publish(topic, payload)
                                    except ssl.SSLError as error:
                                        tls_result = {"exception": type(error).__name__, "library": error.library, "reason": error.reason}
                                    except (ConnectionError, OSError) as error:
                                        require(not isinstance(error, TimeoutError), "Timeout is not evidence of TLS rejection")
                                        tls_result = {"exception": type(error).__name__}
                                    else:
                                        raise AssertionError("Tampered publish unexpectedly acknowledged")
                                    subscriber.connection.settimeout(2)
                                    try:
                                        subscriber.message()
                                    except socket.timeout:
                                        pass
                                    else:
                                        raise AssertionError("Subscriber received tampered publication")
                                    finally:
                                        subscriber.connection.settimeout(10)
                                else:
                                    require(publisher.publish(topic, payload) == 0, "Control PUBACK must succeed")
                                    require(subscriber.message() == (topic, payload), "Control subscriber marker mismatch")
                            # Let the relay consume the broker alert/EOF before stopping.
                            relay.thread.join(timeout=2)
                        (stage_dir / "relay.json").write_text(json.dumps(relay.events, indent=2) + "\n")
                        require(not relay.errors, "Relay forwarding error")
                        flips = [event for event in relay.events if event["event"] == "bit_flip"]
                        require(len(flips) == (1 if stage == "tampered" else 0), "Unexpected mutation count")
                        original = (stage_dir / "client-original.tls").read_bytes()
                        forwarded = (stage_dir / "client-forwarded.tls").read_bytes()
                        changed_bits = sum((a ^ b).bit_count() for a, b in zip(original, forwarded))
                        require(len(original) == len(forwarded) and changed_bits == len(flips),
                                "Forwarded stream must differ by exactly one bit only in tampered stage")
                        broker_log = run(["docker", "logs", run_id])
                        # Docker log_dest stdout is returned here; preserve actual TLS library diagnostic.
                        if stage == "tampered":
                            tls_errors = [line for line in broker_log.splitlines() if "decryption failed or bad record mac" in line.lower()]
                            require(bool(tls_errors), "Broker TLS rejection diagnostic missing")
                            record("integrity tampered", marker=marker, connack=0, puback=None, subscriber_received=False,
                                   subscriber_observation_seconds=2, tls_version=tls_version, cipher=cipher,
                                   client_tls=tls_result, broker_tls=tls_errors, relay_events=relay.events, changed_bits=changed_bits)
                        else:
                            record("integrity " + stage, marker=marker, connack=0, puback=0, subscriber_received=True,
                                   tls_version=tls_version, cipher=cipher, relay_events=relay.events, changed_bits=changed_bits)
            report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", failed_step=step, error_type=type(error).__name__)
        # Messages here are authored assertions, never raw SSL/process responses.
        if isinstance(error, AssertionError):
            report["failure"] = str(error)
        print("FAIL: " + step + " (" + type(error).__name__ + ")", file=sys.stderr)
    finally:
        if broker_started:
            try:
                (output / "broker.log").write_text(run(["docker", "logs", run_id]), encoding="utf-8")
            except Exception:
                report["broker_log"] = "unavailable"
            try:
                run(["docker", "rm", "-f", run_id])
            except Exception:
                report.update(status="failed", cleanup="failed; remove only container " + run_id)
        report["finished_utc"] = stamp()
        report["files_sha256"] = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(output.rglob("*")) if p.is_file()}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Evidence: " + str(output))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
