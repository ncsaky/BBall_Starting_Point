// HEADSHOTS-V2: Settings > Photo credits lists every stock photo (author, licence, source) and every freely licensed
// real photo, in the house table style; reference-only real photos are counted by source.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const css = fs.readFileSync(path.join(gui, 'card-board.css'), 'utf8');
const credits = JSON.parse(fs.readFileSync(path.join(gui, 'assets/headshots/stock/credits.json'), 'utf8'));
const real = JSON.parse(fs.readFileSync(path.join(gui, 'assets/headshots/real/manifest.json'), 'utf8'));
const generated = JSON.parse(fs.readFileSync(path.join(gui, 'assets/headshots/generated/manifest.json'), 'utf8'));

async function openCredits(withGenerated = true) {
  const escape = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const files = {'/assets/headshots/stock/credits.json': credits, '/assets/headshots/real/manifest.json': real};
  if (withGenerated) files['/assets/headshots/generated/manifest.json'] = generated;
  const scope = {
    state: {}, escapeHtml: escape, escapeAttr: escape, renderModal: () => {}, showToast: () => {},
    fetch: async (url) => ({json: async () => files[url]}),
  };
  vm.createContext(scope);
  const start = app.indexOf('const PHOTO_CREDIT_COLUMNS');
  const end = app.indexOf('function sortPhotoCredits');
  assert.ok(start >= 0 && end > start, 'photo credits slice found');
  vm.runInContext(`${app.slice(start, end)}\nglobalThis.openPhotoCreditsModal = openPhotoCreditsModal;`, scope);
  await scope.openPhotoCreditsModal();
  return scope.state.modal;
}

test('settings offer a Photo credits view', () => {
  assert.match(app, /<button type="button" data-photo-credits>Photo credits<\/button>/);
  assert.match(app, /querySelector\("\[data-photo-credits\]"\)\?\.addEventListener\("click", openPhotoCreditsModal\)/);
});

test('every stock photo is listed with its author, licence and source', async () => {
  const modal = await openCredits();
  assert.equal(modal.kind, 'photoCredits');
  const freeReal = [...Object.values(real.coaches), ...Object.values(real.prospects)].filter((row) => row.status === 'real_photo' && row.licence);
  const rows = modal.body.match(/<tr data-credit-row/g) || [];
  assert.equal(rows.length, credits.photos.length + freeReal.length);
  assert.ok(credits.photos.length >= 300);
  for (const photo of credits.photos.slice(0, 40)) {
    assert.ok(modal.body.includes(photo.file), photo.face_id);
    assert.ok(modal.body.includes(String(photo.source_url).replace(/&/g, '&amp;')), photo.face_id);
  }
  assert.match(modal.body, /Shown for reference only/);
});

test('the credits table follows the house table style', () => {
  assert.match(css, /\.photo-credits-table thead th \{[^}]*border-bottom:3px double/);
  assert.match(css, /\.photo-credits-table tbody tr:nth-child\(even\)/);
  assert.match(css, /\.photo-credits-table tbody tr:hover/);
  assert.match(css, /\.photo-credits-table \.is-sorted/);
});

test('the AI-generated faces of fictional people are credited as one group', async () => {
  const modal = await openCredits();
  const people = Object.keys(generated.faces).length;
  const portraits = Object.values(generated.faces).reduce((total, face) => total + face.stages.length, 0);
  assert.ok(people >= 60);
  assert.match(modal.body, /AI-generated faces of fictional people/);
  assert.match(modal.body, /no real person is depicted/);
  assert.match(modal.body, /OpenAI's image tool/);
  assert.ok(modal.body.includes(`${people} fictional people, ${portraits} portraits`));
  assert.ok(!modal.body.includes('/assets/headshots/generated/'), 'no per-image rows for generated faces');
  // Without the generated library the view still lists the stock photos.
  const plain = await openCredits(false);
  assert.doesNotMatch(plain.body, /AI-generated/);
  assert.equal((plain.body.match(/<tr data-credit-row/g) || []).length, (modal.body.match(/<tr data-credit-row/g) || []).length);
});
