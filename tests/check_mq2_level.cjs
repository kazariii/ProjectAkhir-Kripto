// Exercise the shipped WebAssembly with the Wokwi API boundary replaced by
// voltage/logic inputs. This does not claim to run the complete simulator.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const memory = new WebAssembly.Memory({ initial: 256 });
const pins = [];
let callback, userData, analogInput, digitalInput, analogOutput, digitalOutput;
const moduleBytes = fs.readFileSync(path.join(__dirname, '../firmware/mq2-level.chip.wasm'));
const instance = new WebAssembly.Instance(new WebAssembly.Module(moduleBytes), { env: {
  memory,
  pinInit(pointer, mode) {
    const bytes = new Uint8Array(memory.buffer);
    const name = Buffer.from(bytes.subarray(pointer, bytes.indexOf(0, pointer))).toString();
    pins.push({ name, mode });
    return pins.length - 1;
  },
  timerInit(pointer) {
    const fields = new DataView(memory.buffer);
    userData = fields.getUint32(pointer, true);
    callback = fields.getUint32(pointer + 4, true);
    return 1;
  },
  timerStart(timer, micros, repeat) {
    assert.deepEqual([timer, micros, repeat], [1, 1000, 1]);
  },
  pinADCRead(pin) { assert.equal(pins[pin].name, 'A5V'); return analogInput; },
  pinDACWrite(pin, volts) { assert.equal(pins[pin].name, 'A3V'); analogOutput = volts; },
  pinRead(pin) { assert.equal(pins[pin].name, 'D5V'); return digitalInput; },
  pinWrite(pin, level) { assert.equal(pins[pin].name, 'D3V'); digitalOutput = level; },
}});
instance.exports.chipInit();
assert.deepEqual(pins, [
  { name: 'A5V', mode: 4 }, { name: 'A3V', mode: 4 },
  { name: 'D5V', mode: 0 }, { name: 'D3V', mode: 17 },
]);
for (const [volts, level] of [[0, 0], [2.5, 1], [5, 0], [4.4, 1]]) {
  analogInput = volts;
  digitalInput = level;
  instance.exports.__indirect_function_table.get(callback)(userData);
  assert.ok(Math.abs(analogOutput - volts * 0.6) < 0.00001);
  assert.ok(analogOutput <= 3.00001);
  assert.equal(digitalOutput, level); // Active LOW must reach the ESP32 as LOW.
}
console.log('PASS: shipped MQ2 level model maps 0..5V to 0..3V and preserves DOUT LOW/HIGH');
