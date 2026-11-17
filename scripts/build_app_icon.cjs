#!/usr/bin/env node
'use strict';

// Authoring tool only. The game and packaging consume the committed exports.
const fs = require('node:fs/promises');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const sharp = require('sharp');

const root = path.resolve(__dirname, '..');
const assets = path.join(root, 'packaging', 'assets');

async function main() {
  const source = await fs.readFile(path.join(assets, 'app-icon.svg'));
  const master = await sharp(source).png().toBuffer();
  await fs.writeFile(path.join(assets, 'app-icon.png'), master);

  if (process.platform === 'darwin') {
    const os = require('node:os');
    const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'nba-gm-icon-'));
    try {
      const iconset = path.join(temporary, 'app.iconset');
      await fs.mkdir(iconset);
      for (const size of [16, 32, 128, 256, 512]) {
        for (const scale of [1, 2]) {
          const filename = `icon_${size}x${size}${scale === 2 ? '@2x' : ''}.png`;
          await sharp(master).resize(size * scale).png().toFile(path.join(iconset, filename));
        }
      }
      execFileSync('/usr/bin/iconutil', ['-c', 'icns', iconset, '-o', path.join(assets, 'app-icon.icns')]);
    } finally {
      await fs.rm(temporary, {recursive: true, force: true});
    }
  }

  const layers = [];
  for (const [row, background] of ['#eef1f3', '#242b30'].entries()) {
    const band = await sharp({create: {width: 900, height: 260, channels: 4, background}}).png().toBuffer();
    layers.push({input: band, left: 0, top: row * 260});
    let left = 24;
    for (const size of [224, 128, 64, 32, 16]) {
      layers.push({input: await sharp(master).resize(size).png().toBuffer(), left, top: row * 260 + 130 - size / 2});
      left += size + 48;
    }
  }
  await sharp({create: {width: 900, height: 520, channels: 4, background: '#eef1f3'}})
    .composite(layers).png().toFile(path.join(assets, 'app-icon-preview.png'));
  console.log(`Icon exports: ${assets}`);
}

main().catch(error => { console.error(error); process.exitCode = 1; });
