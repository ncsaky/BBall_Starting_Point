#!/usr/bin/env node
// Builds the generated face library for fictional staff and fictional draft prospects.
//
// Each face is an SVG drawn with DiceBear from one avatar style. We pick every part ourselves from a seeded
// random stream (not DiceBear's own seed), so that:
//   - each face belongs to one gender, using only hair and facial-hair parts that read as that gender;
//   - no two faces in a group share the same combination of parts;
//   - the library is identical every time it is rebuilt.
// Groups: staff-m, staff-f (adult staff, some with grey hair, tagged "senior"), prospect-m (young players).
// The game picks a face for each fictional person from the matching group (src/nba_gm_data/faces.py).
//
// DiceBear is a build-time tool only (not shipped with the game). Install it once into the git-ignored tooling
// folder:   (cd output/headshots/tooling && npm install @dicebear/core@9.2.4 @dicebear/collection@9.2.4)
//
// Usage:
//   node scripts/build_face_library.mjs --style open-peeps            # full library into gui/assets
//   node scripts/build_face_library.mjs --style avataaars --sample 12 --out output/headshots/samples
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, arg, i, all) => {
  if (arg.startsWith('--')) pairs.push([arg.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return pairs;
}, []));
const tooling = resolve(ROOT, args.tooling || 'output/headshots/tooling');
const requireTool = createRequire(join(tooling, 'package.json'));
const { createAvatar } = await import(pathToFileURL(requireTool.resolve('@dicebear/core')).href);
const collection = await import(pathToFileURL(requireTool.resolve('@dicebear/collection')).href);

export const COUNTS = { 'staff-m': 640, 'staff-f': 260, 'prospect-m': 1100 };

// ---------------------------------------------------------------------------------------------- seeded stream
function hash(text) {
  let h = 2166136261 >>> 0;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0;
  return h;
}
function stream(seed) {
  let a = hash(seed);
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const pick = (rng, list) => list[Math.floor(rng() * list.length)];
function weighted(rng, entries) {
  const total = entries.reduce((sum, [, w]) => sum + w, 0);
  let roll = rng() * total;
  for (const [value, w] of entries) { roll -= w; if (roll <= 0) return value; }
  return entries[entries.length - 1][0];
}

// ---------------------------------------------------------------------------------------------- shared palettes
const HAIR_DARK = ['2c1b18', '2c1b18', '4a312c', '3b2a22'];
const HAIR_LIGHT_SKIN = ['2c1b18', '4a312c', '724133', 'a55728', 'b58143', 'd6b370', 'c93305'];
const HAIR_GREY = ['e8e1e1', 'c9c4c4', 'a9a6a6'];
const SUITS = ['1f2a44', '2d3748', '3c4a5c', '24324a', '4a5568', '5d6b7e', '6b2737', '2f4f3f', '7d8896', 'e6e6e6'];
const JERSEYS = ['e78276', 'ffcf77', '78e185', '9ddadb', '8fa7df', 'e279c7', 'c8102e', '1d428a', '006bb6', 'fdb927', '007a33', '552583', 'f58426', '0e2240', 'ce1141', '00788c'];

// ---------------------------------------------------------------------------------------------- style recipes
// Every recipe turns (group, rng) into DiceBear options plus a part key used to keep combinations unique.
const RECIPES = {
  'open-peeps': {
    style: collection.openPeeps,
    licence: { name: 'CC0 1.0 (public domain)', url: 'https://creativecommons.org/publicdomain/zero/1.0/', source: 'Open Peeps by Pablo Stanley (https://www.openpeeps.com/), via DiceBear (MIT)' },
    skins: { staff: [['ffdbb4', 26], ['edb98a', 18], ['d08b5b', 18], ['ae5d29', 20], ['694d3d', 18]],
             prospect: [['ffdbb4', 12], ['edb98a', 12], ['d08b5b', 18], ['ae5d29', 28], ['694d3d', 30]] },
    hair: {
      'staff-m': ['short1', 'short2', 'short3', 'short4', 'short5', 'noHair1', 'noHair2', 'noHair3', 'shaved1', 'shaved2', 'shaved3', 'flatTop', 'pomp', 'twists', 'twists2', 'afro', 'dreads2', 'grayShort'],
      'staff-f': ['bangs', 'bangs2', 'bantuKnots', 'bun', 'bun2', 'buns', 'grayBun', 'grayMedium', 'hijab', 'long', 'longBangs', 'longCurly', 'longAfro', 'medium1', 'medium2', 'medium3', 'mediumBangs', 'mediumBangs3', 'mediumStraight', 'cornrows2', 'dreads1'],
      'prospect-m': ['short1', 'short2', 'short3', 'short4', 'short5', 'shaved1', 'shaved2', 'shaved3', 'flatTop', 'flatTopLong', 'pomp', 'twists', 'twists2', 'afro', 'dreads2', 'cornrows', 'noHair1'],
    },
    seniorHair: { 'staff-m': ['grayShort', 'noHair1', 'noHair2', 'noHair3', 'short1', 'short2', 'short4', 'shaved1'], 'staff-f': ['grayBun', 'grayMedium', 'bun', 'medium1', 'mediumStraight', 'bangs'] },
    faces: { staff: ['serious', 'smile', 'calm', 'driven', 'blank', 'serious', 'smile'], senior: ['old', 'serious', 'smile', 'calm', 'blank'], prospect: ['serious', 'smile', 'driven', 'calm', 'cheeky', 'blank'] },
    beards: { staff: ['chin', 'full', 'full2', 'full3', 'goatee1', 'goatee2', 'moustache1', 'moustache4', 'moustache5', 'moustache6', 'moustache7', 'moustache9'], prospect: ['chin', 'goatee1', 'goatee2', 'moustache1', 'moustache9', 'full'] },
    glasses: ['glasses', 'glasses2', 'glasses3', 'glasses4', 'glasses5'],
    build(group, rng, senior) {
      const r = this, kind = group.startsWith('prospect') ? 'prospect' : 'staff', male = group.endsWith('-m');
      const skin = weighted(rng, r.skins[kind]);
      const head = pick(rng, senior ? r.seniorHair[group] : r.hair[group]);
      const darkSkin = ['ae5d29', '694d3d'].includes(skin);
      const hairColor = senior ? pick(rng, HAIR_GREY) : pick(rng, darkSkin ? HAIR_DARK : HAIR_LIGHT_SKIN);
      const face = pick(rng, senior ? r.faces.senior : r.faces[kind]);
      const beardChance = male ? (kind === 'staff' ? 0.5 : 0.22) : 0;
      const beard = rng() < beardChance ? pick(rng, r.beards[kind]) : null;
      const glasses = rng() < (kind === 'staff' ? (senior ? 0.45 : 0.22) : 0.03) ? pick(rng, r.glasses) : null;
      const clothing = pick(rng, kind === 'staff' ? SUITS : JERSEYS);
      const options = {
        skinColor: [skin], head: [head], headContrastColor: [hairColor], face: [face], clothingColor: [clothing],
        facialHair: beard ? [beard] : undefined, facialHairProbability: beard ? 100 : 0,
        accessories: glasses ? [glasses] : undefined, accessoriesProbability: glasses ? 100 : 0, maskProbability: 0,
      };
      return { options, key: [skin, head, hairColor, face, beard, glasses].join('|') };
    },
  },
  avataaars: {
    style: collection.avataaars,
    licence: { name: 'Free for personal and commercial use (Avataaars licence)', url: 'https://avataaars.com/', source: 'Avataaars by Pablo Stanley, via DiceBear (MIT)' },
    skins: { staff: [['ffdbb4', 26], ['edb98a', 18], ['d08b5b', 18], ['ae5d29', 20], ['614335', 18]],
             prospect: [['ffdbb4', 12], ['edb98a', 12], ['d08b5b', 18], ['ae5d29', 28], ['614335', 30]] },
    hair: {
      'staff-m': ['dreads01', 'frizzle', 'shortCurly', 'shortFlat', 'shortRound', 'shortWaved', 'sides', 'theCaesar', 'theCaesarAndSidePart', 'BALD'],
      'staff-f': ['bigHair', 'bob', 'bun', 'curly', 'curvy', 'froBand', 'longButNotTooLong', 'miaWallace', 'straight01', 'straight02', 'straightAndStrand', 'hijab'],
      'prospect-m': ['dreads01', 'dreads02', 'frizzle', 'shortCurly', 'shortFlat', 'shortRound', 'shortWaved', 'theCaesar', 'theCaesarAndSidePart', 'BALD'],
    },
    seniorHair: { 'staff-m': ['sides', 'shortFlat', 'theCaesar', 'theCaesarAndSidePart', 'BALD'], 'staff-f': ['bob', 'bun', 'straight02', 'curly'] },
    build(group, rng, senior) {
      const kind = group.startsWith('prospect') ? 'prospect' : 'staff', male = group.endsWith('-m');
      const skin = weighted(rng, this.skins[kind]);
      const top = pick(rng, senior ? this.seniorHair[group] : this.hair[group]);
      const darkSkin = ['ae5d29', '614335'].includes(skin);
      const hairColor = senior ? pick(rng, ['e8e1e1', 'ecdcbf']) : pick(rng, darkSkin ? ['2c1b18', '4a312c'] : ['2c1b18', '4a312c', '724133', 'a55728', 'b58143', 'd6b370', 'c93305']);
      const beard = male && rng() < (kind === 'staff' ? 0.45 : 0.2) ? pick(rng, ['beardLight', 'beardMedium', 'beardMajestic', 'moustacheFancy']) : null;
      const glasses = rng() < (kind === 'staff' ? 0.25 : 0.03) ? pick(rng, ['prescription01', 'prescription02', 'round']) : null;
      const mouth = pick(rng, ['default', 'smile', 'serious', 'twinkle']);
      const eyebrows = pick(rng, ['defaultNatural', 'flatNatural', 'raisedExcitedNatural', 'upDownNatural']);
      const options = {
        skinColor: [skin], top: top === 'BALD' ? undefined : [top], topProbability: top === 'BALD' ? 0 : 100,
        hairColor: [hairColor], facialHairColor: [hairColor], facialHair: beard ? [beard] : undefined,
        facialHairProbability: beard ? 100 : 0, accessories: glasses ? [glasses] : undefined,
        accessoriesProbability: glasses ? 100 : 0, mouth: [mouth], eyes: ['default'], eyebrows: [eyebrows],
        clothing: [kind === 'staff' ? pick(rng, ['blazerAndShirt', 'blazerAndSweater', 'collarAndSweater']) : pick(rng, ['hoodie', 'shirtCrewNeck', 'shirtVNeck'])],
        clothesColor: [pick(rng, kind === 'staff' ? ['262e33', '25557c', '3c4f5c', '929598', 'e6e6e6'] : ['5199e4', 'ff5c5c', '262e33', 'a7ffc4', 'ffffb1', '65c9ff'])],
      };
      return { options, key: [skin, top, hairColor, beard, glasses, mouth, eyebrows].join('|') };
    },
  },
  personas: {
    style: collection.personas,
    licence: { name: 'CC BY 4.0 (attribution required)', url: 'https://creativecommons.org/licenses/by/4.0/', source: 'Personas by Draftbit (https://personas.draftbit.com/), via DiceBear (MIT)' },
    skins: { staff: [['eeb4a4', 22], ['e5a07e', 18], ['d78774', 18], ['b16a5b', 20], ['92594b', 12], ['623d36', 10]],
             prospect: [['eeb4a4', 10], ['e5a07e', 12], ['d78774', 16], ['b16a5b', 22], ['92594b', 20], ['623d36', 20]] },
    hair: {
      'staff-m': ['shortCombover', 'buzzcut', 'bald', 'balding', 'fade', 'shortComboverChops', 'curlyHighTop'],
      'staff-f': ['long', 'sideShave', 'bobCut', 'bobBangs', 'straightBun', 'extraLong', 'bunUndercut', 'curlyBun', 'curly'],
      'prospect-m': ['buzzcut', 'fade', 'curlyHighTop', 'shortCombover', 'bald', 'curly'],
    },
    seniorHair: { 'staff-m': ['balding', 'bald', 'shortCombover'], 'staff-f': ['bobCut', 'straightBun', 'bobBangs'] },
    build(group, rng, senior) {
      const kind = group.startsWith('prospect') ? 'prospect' : 'staff', male = group.endsWith('-m');
      const skin = weighted(rng, this.skins[kind]);
      const hair = pick(rng, senior ? this.seniorHair[group] : this.hair[group]);
      const hairColor = senior ? 'dee1f5' : pick(rng, ['362c47', '6c4545', '362c47', 'f29c65']);
      const beard = male && rng() < (kind === 'staff' ? 0.45 : 0.2) ? pick(rng, ['beardMustache', 'goatee', 'shadow', 'soulPatch']) : null;
      const eyes = pick(rng, kind === 'staff' && rng() < 0.25 ? ['glasses'] : ['open', 'happy']);
      const mouth = pick(rng, ['smile', 'smirk', 'bigSmile']);
      const options = {
        skinColor: [skin], hair: [hair], hairColor: [hairColor], eyes: [eyes], mouth: [mouth],
        facialHair: beard ? [beard] : undefined, facialHairProbability: beard ? 100 : 0,
        body: [pick(rng, ['squared', 'rounded'])], clothingColor: [pick(rng, kind === 'staff' ? ['456dff', '7555ca', '54d7c7'] : ['e24553', 'f3b63a', '6dbb58', '456dff'])],
      };
      return { options, key: [skin, hair, hairColor, beard, eyes, mouth].join('|') };
    },
  },
};

function strip(svg) {
  // The licence is recorded once in the manifest; drop DiceBear's per-file RDF block to keep files small.
  return svg.replace(/<metadata[\s\S]*?<\/metadata>/, '');
}

export function buildGroup(styleName, group, count) {
  const recipe = RECIPES[styleName];
  const seen = new Set();
  const faces = [];
  const seniorShare = group.startsWith('staff') ? 0.24 : 0;
  for (let index = 1; faces.length < count; index += 1) {
    const rng = stream(`${styleName}:${group}:${index}`);
    const senior = rng() < seniorShare;
    const { options, key } = recipe.build(group, rng, senior);
    if (seen.has(key)) continue; // keep every combination of parts unique within the group
    seen.add(key);
    const svg = strip(createAvatar(recipe.style, { seed: `${group}-${index}`, size: 256, ...options }).toString());
    faces.push({ id: `${group}/${String(faces.length + 1).padStart(4, '0')}`, senior, svg });
  }
  return faces;
}

function main() {
  const styleName = args.style || 'open-peeps';
  if (!RECIPES[styleName]) throw new Error(`unknown style ${styleName}; use ${Object.keys(RECIPES).join(', ')}`);
  const recipe = RECIPES[styleName];
  if (args.sample) {
    // A small mixed sheet for choosing a style: alternating women and men, staff then prospects.
    const n = Number(args.sample) || 12;
    const out = resolve(ROOT, args.out || 'output/headshots/samples', styleName);
    rmSync(out, { recursive: true, force: true });
    mkdirSync(out, { recursive: true });
    const f = buildGroup(styleName, 'staff-f', Math.ceil(n / 3));
    const m = buildGroup(styleName, 'staff-m', Math.ceil(n / 3));
    const p = buildGroup(styleName, 'prospect-m', n - 2 * Math.ceil(n / 3));
    const faces = [...f.map((x) => ({ ...x, gender: 'female' })), ...m.map((x) => ({ ...x, gender: 'male' })), ...p.map((x) => ({ ...x, gender: 'male' }))];
    faces.forEach((face) => writeFileSync(join(out, face.id.replace('/', '-') + '.svg'), face.svg));
    writeFileSync(join(out, 'sample.json'), JSON.stringify({ style: styleName, licence: recipe.licence, faces: faces.map(({ id, gender, senior }) => ({ id, gender, senior, file: id.replace('/', '-') + '.svg' })) }, null, 1));
    console.log(`${styleName}: ${faces.length} sample faces in ${out}`);
    return;
  }
  const out = resolve(ROOT, args.out || 'src/nba_gm_data/gui/assets/headshots/generated', styleName);
  rmSync(out, { recursive: true, force: true });
  const manifest = { style: styleName, licence: recipe.licence, built_by: 'scripts/build_face_library.mjs', dicebear: '9.2.4', groups: {} };
  let bytes = 0;
  for (const [group, count] of Object.entries(COUNTS)) {
    const faces = buildGroup(styleName, group, count);
    mkdirSync(join(out, group), { recursive: true });
    for (const face of faces) {
      writeFileSync(join(out, face.id + '.svg'), face.svg);
      bytes += Buffer.byteLength(face.svg);
    }
    manifest.groups[group] = {
      gender: group.endsWith('-f') ? 'female' : 'male',
      count: faces.length,
      senior: faces.map((face, i) => (face.senior ? i + 1 : 0)).filter(Boolean),
    };
  }
  writeFileSync(join(out, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n');
  console.log(`${styleName}: ${Object.values(manifest.groups).reduce((s, g) => s + g.count, 0)} faces, ${(bytes / 1048576).toFixed(1)} MB in ${out}`);
}

main();
