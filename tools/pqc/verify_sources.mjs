import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const root = path.resolve(import.meta.dirname,'../..');
const lock = JSON.parse(fs.readFileSync(path.join(import.meta.dirname,'sources.lock.json'),'utf8'));
let count = 0;
for (const pkg of lock.packages) for (const [file,expected] of Object.entries(pkg.files)) {
  const full = path.join(root,'firmware/lib',pkg.name,file);
  const actual = crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex');
  if (actual !== expected) throw new Error(`Source mismatch: ${pkg.name}/${file}`);
  count++;
}
console.log(`PASS: ${count} pinned upstream files verified.`);
