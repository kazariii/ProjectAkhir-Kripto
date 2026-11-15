// Import only pinned upstream source, retain licenses, and record every source hash.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
const root = path.resolve(import.meta.dirname, '../..');
const packages = [
  {name:'mlkem-native', commit:'d1b2fe782888bdb761a50336012923180be7f502', url:'https://github.com/pq-code-package/mlkem-native', revision:'v2.0.0'},
  {name:'c-fn-dsa', commit:'1b858880dcac091b5e5f84f0e4d8617c35ba1392', url:'https://github.com/pornin/c-fn-dsa', revision:'prospective FN-DSA; not final FIPS 206'},
  {name:'mbedtls-extra', commit:'555f84735aecdbd76a566cf087ec8425dfb0c8ab', url:'https://github.com/Mbed-TLS/mbedtls', revision:'v2.28.7; missing AEAD/HKDF components only, matching Arduino SDK headers'}
];
for (const pkg of packages) {
  const source = path.join(root, 'evidence/local/pqc-sources', pkg.name);
  const actual = execFileSync('git',['-C', source, 'rev-parse','HEAD'], {encoding:'utf8'}).trim();
  if (actual !== pkg.commit) throw new Error(`Wrong upstream revision: ${pkg.name}`);
  const dest = path.join(root, 'firmware/lib', pkg.name);
  fs.mkdirSync(dest, {recursive:true});
  if (pkg.name === 'mlkem-native') {
    fs.cpSync(path.join(source,'mlkem'),dest,{recursive:true});
    for (const entry of fs.readdirSync(source)) {
      if (entry.startsWith('LICENSE')) fs.cpSync(path.join(source,entry),path.join(dest,entry),{recursive:true});
    }
  } else if (pkg.name === 'mbedtls-extra') {
    for (const file of ['chacha20.c','poly1305.c','chachapoly.c','hkdf.c','common.h']) {
      fs.copyFileSync(path.join(source,'library',file),path.join(dest,file));
    }
    for (const file of ['LICENSE','LICENSES']) {
      if (fs.existsSync(path.join(source,file))) fs.cpSync(path.join(source,file),path.join(dest,file),{recursive:true});
    }
  } else {
    for (const entry of fs.readdirSync(source)) {
      if (/\.(c|h)$/.test(entry) && !/^(test|speed)/.test(entry) || /^(LICENSE|README)/.test(entry)) {
        fs.cpSync(path.join(source,entry),path.join(dest,entry));
      }
    }
  }
  pkg.files = {};
  function walk(dir) {
    for (const entry of fs.readdirSync(dir,{withFileTypes:true})) {
      const full = path.join(dir,entry.name);
      if (entry.isDirectory()) walk(full);
      else if (!['library.json','mbedtls_extra.h'].includes(entry.name)) {
        pkg.files[path.relative(dest,full).replaceAll('\\','/')] = crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex');
      }
    }
  }
  walk(dest);
}
fs.writeFileSync(path.join(root,'tools/pqc/sources.lock.json'), JSON.stringify({packages},null,2)+'\n');
console.log('Pinned sources imported with licenses and per-file SHA-256 hashes.');
