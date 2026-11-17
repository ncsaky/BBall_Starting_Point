// Export the existing original logo as a Windows ICO; no new artwork.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
(async () => {
  const assets = path.resolve(__dirname, '../packaging/assets');
  const png = await sharp(path.join(assets, 'app-icon.png')).resize(256, 256).png().toBuffer();
  const header = Buffer.alloc(22);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(1, 4);
  header.writeUInt16LE(1, 10);
  header.writeUInt16LE(32, 12);
  header.writeUInt32LE(png.length, 14);
  header.writeUInt32LE(22, 18);
  fs.writeFileSync(path.join(assets, 'app-icon.ico'), Buffer.concat([header, png]));
})().catch(error => { console.error(error); process.exitCode = 1; });
