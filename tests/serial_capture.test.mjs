import test from 'node:test';
import assert from 'node:assert/strict';
import {TelnetDecoder} from '../tools/telemetry/capture_serial.mjs';

test('fragmented RFC2217 negotiation never enters the UART log', () => {
  const received=[], replies=[];
  const decoder=new TelnetDecoder(b=>received.push(b), b=>replies.push([...b]));
  for (const b of Buffer.concat([Buffer.from('TELE'), Buffer.from([255,251,0,255,253,44,255,250,44,101,255,255,255,240]), Buffer.from('METRY_BEGIN\r\n')])) {
    decoder.feed(Buffer.from([b]));
  }
  assert.equal(Buffer.concat(received).toString(), 'TELEMETRY_BEGIN\r\n');
  assert.deepEqual(replies, [[255,253,0],[255,251,44]]);
});
test('escaped IAC is data and duplicate negotiations do not loop', () => {
  const received=[], replies=[];
  const decoder=new TelnetDecoder(b=>received.push(b), b=>replies.push([...b]));
  decoder.feed(Buffer.from([65,255,255,66,255,251,1,255,251,1]));
  assert.deepEqual([...Buffer.concat(received)], [65,255,66]);
  assert.deepEqual(replies, [[255,254,1]]);
});
test('oversized subnegotiation is rejected', () => {
  const decoder=new TelnetDecoder(()=>{},()=>{});
  decoder.feed(Buffer.from([255,250]));
  assert.throws(()=>decoder.feed(Buffer.alloc(4097)), /Oversized/);
});
