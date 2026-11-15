// Passive UART capture via Wokwi's documented RFC2217 TCP endpoint.
// Does not send serial data, reset the MCU, or control the simulator UI.
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';

export class TelnetDecoder {
  constructor(write, reply) {
    this.write = write; this.reply = reply;
    this.state = 'data'; this.command = 0; this.subLength = 0; this.replied = new Set();
  }
  feed(bytes) {
    const output = [];
    for (const byte of bytes) {
      switch (this.state) {
        case 'data':
          if (byte === 255) this.state = 'iac'; else output.push(byte);
          break;
        case 'iac':
          if (byte === 255) { output.push(byte); this.state = 'data'; }
          else if (byte === 250) { this.state = 'sub'; this.subLength = 0; }
          else if ([251,252,253,254].includes(byte)) { this.command = byte; this.state = 'option'; }
          else this.state = 'data';
          break;
        case 'option': {
          const allowed = [0,3,44].includes(byte); // binary, suppress-go-ahead, COM-PORT
          const response = this.command === 251 ? (allowed ? 253 : 254) :
                           this.command === 253 ? (allowed ? 251 : 252) : null;
          const key = `${this.command}/${byte}`;
          if (response !== null && !this.replied.has(key)) {
            this.replied.add(key); this.reply(Buffer.from([255,response,byte]));
          }
          this.state = 'data'; break;
        }
        case 'sub':
          if (++this.subLength > 4096) throw Error('Oversized Telnet negotiation');
          if (byte === 255) this.state = 'sub-iac';
          break;
        case 'sub-iac':
          this.state = byte === 240 ? 'data' : 'sub';
          break;
      }
    }
    if (output.length) this.write(Buffer.from(output));
  }
}

function capture() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const output = path.resolve(process.argv[2] || path.join(root, 'evidence/local/wokwi-ticket04-serial.txt'));
  if (fs.existsSync(output)) throw Error('Capture already exists; preserve it and choose a new output filename');
  fs.mkdirSync(path.dirname(output), {recursive:true});
  const fd = fs.openSync(output, 'wx');
  let total = 0, connected = false, socket;
  const deadline = Date.now()+30*60*1000;
  function connect() {
    if (Date.now() >= deadline) { fs.closeSync(fd); process.exitCode = 2; return; }
    socket = net.createConnection({host:'localhost', port:4000, autoSelectFamily:true});
    const decoder = new TelnetDecoder(bytes => {
      total += bytes.length;
      if (total > 2*1024*1024) { socket.destroy(Error('Serial capture exceeded 2 MiB')); return; }
      fs.writeSync(fd, bytes);
    }, bytes => socket.write(bytes));
    socket.on('connect', () => {
      connected = true;
      process.stdout.write('WOKWI_SERIAL_CAPTURE connected to localhost:4000\n');
      socket.write(Buffer.from([255,251,0,255,253,0,255,251,44]));
    });
    socket.on('data', bytes => { try { decoder.feed(bytes); } catch(error) { socket.destroy(error); } });
    socket.on('error', error => { if (error.code !== 'ECONNREFUSED') process.stderr.write(error.message+'\n'); });
    socket.on('close', () => {
      if (!connected || total === 0) { connected = false; setTimeout(connect, 100); return; }
      fs.closeSync(fd);
      process.stdout.write(`WOKWI_SERIAL_CAPTURE saved ${total} bytes to ${output}\n`);
      process.exitCode = total ? 0 : 1;
    });
  }
  const timer = setTimeout(() => {
    if (connected) socket.end(); else process.exit(2);
  }, 30*60*1000);
  timer.unref();
  process.stdout.write('WOKWI_SERIAL_CAPTURE waiting for Wokwi; keep simulator visible and running\n');
  connect();
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) capture();
