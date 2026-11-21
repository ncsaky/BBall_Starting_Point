const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const saveFunctions = source.slice(source.indexOf('async function loadSaves()'), source.indexOf('async function createSave()'))
  + '\n' + source.slice(source.indexOf('function formatWrittenDate('), source.indexOf('function formatDashboardShortDate('));

function element() {
  return {value: '', textContent: '', hidden: false, disabled: false, files: [], classList: {toggle() {}}, focus() {}};
}

function harness(saves = []) {
  const calls = [];
  const downloads = [];
  const elements = Object.fromEntries([
    'startupSaveSelect', 'startupLoadSave', 'startupExportSave', 'startupRecoverSave',
    'startupSaveHealth', 'startupSaveMessage', 'startupRestoreFile', 'startupRestoreName',
  ].map(id => [id, element()]));
  Object.defineProperty(elements.startupSaveSelect, 'innerHTML', {
    set(markup) {this.markup = markup; this.value = markup.match(/value="([^"]*)"/)?.[1] || '';},
    get() {return this.markup;},
  });
  const context = {
    state: {saves: [], currentSave: '', busy: false, busyDepth: 0, hydrating: false, home: null},
    els: elements,
    localStorage: {setItem() {}, removeItem() {}},
    LAST_SAVE_KEY: 'last',
    action: async (name, payload) => {
      calls.push({name, payload});
      if (name === 'list_saves') return {saves};
      if (name === 'export_save') return {filename: 'complete.zip', archive_base64: btoa('archive-bytes')};
      if (name === 'restore_save') {
        const restored = {path: '/temporary/restored.json', name: payload.save_name, status: 'ok'};
        saves.push(restored);
        return {save_path: restored.path};
      }
      if (name === 'recover_save') {
        saves.find(save => save.path === payload.save_path).status = 'ok';
        return {save_path: payload.save_path};
      }
      throw new Error(`Unexpected action: ${name}`);
    },
    refreshHome: async () => {},
    render() {},
    showToast(message, error) {context.toast = {message, error};},
    setBusy(value) {context.state.busy = value;},
    escapeHtml: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
    escapeAttr: value => String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;'),
    window: {confirm: () => true},
    atob, Blob, Uint8Array,
    URL: {createObjectURL: blob => {context.downloadBlob = blob; return 'blob:backup';}, revokeObjectURL() {}},
    document: {body: {append() {}}, createElement: () => ({click() {downloads.push({href: this.href, filename: this.download});}, remove() {}})},
    setTimeout(callback) {callback();},
    FileReader: class {
      readAsDataURL(file) {this.result = `data:application/zip;base64,${btoa(file.contents)}`; this.onload();}
    },
  };
  vm.createContext(context);
  vm.runInContext(saveFunctions, context);
  return {context, elements, calls, downloads};
}

test('unreadable saves stay selectable with their error and recovery action', async () => {
  const broken = {path: '/temporary/missing.json', name: 'Missing History', status: 'unreadable', error: 'History file missing.', recovery_available: true};
  const {context, elements} = harness([broken]);
  context.state.currentSave = broken.path;
  await context.loadSaves();
  assert.equal(context.state.saves.length, 1);
  assert.equal(context.state.currentSave, '');
  assert.equal(elements.startupSaveSelect.value, broken.path);
  assert.match(elements.startupSaveSelect.innerHTML, /Missing History.*Needs recovery/);
  assert.match(elements.startupSaveHealth.textContent, /History file missing.*Recover Previous/);
  assert.equal(elements.startupLoadSave.disabled, true);
  assert.equal(elements.startupExportSave.disabled, true);
  assert.equal(elements.startupRecoverSave.disabled, false);
});

test('selection survives refresh and corrupt saves without recovery have actionable instructions', async () => {
  const {context, elements} = harness([
    {path: '/temporary/good.json', name: 'Good', status: 'ok'},
    {path: '/temporary/bad.json', name: '<Broken>', status: 'unreadable', error: 'Unsupported future format.'},
  ]);
  elements.startupSaveSelect.value = '/temporary/bad.json';
  await context.loadSaves();
  assert.equal(elements.startupSaveSelect.value, '/temporary/bad.json');
  assert.match(elements.startupSaveSelect.innerHTML, /&lt;Broken&gt;/);
  assert.match(elements.startupSaveHealth.textContent, /Unsupported future format.*Restore an exported backup/);
  assert.equal(elements.startupRecoverSave.disabled, true);
});

test('export downloads the complete API archive without reconstructing save components', async () => {
  const {context, downloads, calls} = harness([{path: '/temporary/good.json', name: 'Good', status: 'ok'}]);
  await context.loadSaves();
  await context.exportStartupSave();
  assert.equal(calls.at(-1).name, 'export_save');
  assert.equal(calls.at(-1).payload.save_path, '/temporary/good.json');
  assert.deepEqual(downloads, [{href: 'blob:backup', filename: 'complete.zip'}]);
  assert.equal(await context.downloadBlob.text(), 'archive-bytes');
});

test('upload restores into the explicitly named new save and leaves the selected save untargeted', async () => {
  const {context, elements, calls} = harness([{path: '/temporary/original.json', name: 'Original', status: 'ok'}]);
  await context.loadSaves();
  elements.startupRestoreName.value = 'Restored Copy';
  elements.startupRestoreFile.files = [{size: 12, contents: 'archive-bytes'}];
  await context.restoreStartupSave();
  const request = calls.find(call => call.name === 'restore_save');
  assert.equal(request.payload.save_name, 'Restored Copy');
  assert.equal(request.payload.archive_base64, btoa('archive-bytes'));
  assert.equal('save_path' in request.payload, false);
  assert.equal(elements.startupSaveSelect.value, '/temporary/restored.json');
  assert.equal(elements.startupLoadSave.disabled, false);
  assert.equal(context.state.busyDepth, 0);
  assert.match(elements.startupSaveMessage.textContent, /Restored as Restored Copy/);
});

test('malformed archive rejection remains visible and preserves picker state for retry', async () => {
  const {context, elements, calls} = harness([{path: '/temporary/original.json', name: 'Original', status: 'ok'}]);
  await context.loadSaves();
  const action = context.action;
  context.action = (name, payload) => name === 'restore_save' ? Promise.reject(new Error('Invalid backup: unsafe archive path.')) : action(name, payload);
  elements.startupRestoreName.value = 'Retry Name';
  elements.startupRestoreFile.files = [{size: 8, contents: 'bad-data'}];
  elements.startupRestoreFile.value = 'file.zip';
  await context.restoreStartupSave();
  assert.match(elements.startupSaveMessage.textContent, /unsafe archive path/);
  assert.equal(elements.startupSaveMessage.hidden, false);
  assert.equal(elements.startupSaveSelect.value, '/temporary/original.json');
  assert.equal(elements.startupRestoreName.value, 'Retry Name');
  assert.equal(elements.startupRestoreFile.value, '');
  assert.equal(context.state.busy, false);
  assert.equal(calls.filter(call => call.name === 'list_saves').length, 1);
});

test('oversized upload is rejected before reading or calling restore', async () => {
  const {context, elements, calls} = harness();
  elements.startupRestoreName.value = 'Too Large';
  elements.startupRestoreFile.files = [{size: 128 * 1024 * 1024 + 1}];
  await context.restoreStartupSave();
  assert.match(elements.startupSaveMessage.textContent, /maximum ZIP size is 128 MB/);
  assert.equal(calls.length, 0);
  assert.equal(context.state.busy, false);
});

test('recovery cancellation does not mutate; confirmation restores the selected unreadable save', async () => {
  const {context, elements, calls} = harness([{path: '/temporary/broken.json', name: 'Broken', status: 'unreadable', recovery_available: true}]);
  await context.loadSaves();
  context.window.confirm = () => false;
  await context.recoverStartupSave();
  assert.equal(calls.filter(call => call.name === 'recover_save').length, 0);
  context.window.confirm = () => true;
  await context.recoverStartupSave();
  assert.equal(calls.find(call => call.name === 'recover_save').payload.save_path, '/temporary/broken.json');
  assert.equal(elements.startupLoadSave.disabled, false);
  assert.match(elements.startupSaveMessage.textContent, /Previous complete backup restored/);
});

test('a component that fails after listing returns the user to a usable recovery picker', async () => {
  const save = {path: '/temporary/raced.json', name: 'Changed', status: 'ok'};
  const {context, elements} = harness([save]);
  await context.loadSaves();
  let loads = 0;
  context.refreshHome = async () => {
    if (!loads++) {save.status = 'unreadable'; save.error = 'History changed or missing.'; throw new Error(save.error);}
  };
  await context.loadStartupSave();
  assert.equal(context.state.currentSave, '');
  assert.equal(context.state.home, null);
  assert.equal(elements.startupLoadSave.disabled, true);
  assert.match(elements.startupSaveMessage.textContent, /History changed or missing/);
});

test('remembered-save automatic resume also exposes recovery when loading fails after listing', async () => {
  const save = {path: '/temporary/resume.json', name: 'Resume', status: 'ok', recovery_available: true};
  const {context, elements} = harness([save]);
  context.state.currentSave = save.path;
  context.state.hydrating = true;
  context.refreshHome = async () => {throw new Error('History became unreadable during resume.');};
  let renders = 0;
  context.render = () => {renders++; context.updateStartupSaveControls();};
  await assert.rejects(context.loadSaves(), /History became unreadable/);
  assert.equal(context.state.currentSave, '');
  assert.equal(context.state.home, null);
  assert.equal(context.state.hydrating, false);
  assert.equal(elements.startupSaveSelect.value, save.path);
  assert.equal(elements.startupLoadSave.disabled, true);
  assert.equal(elements.startupExportSave.disabled, true);
  assert.equal(elements.startupRecoverSave.disabled, false);
  assert.match(elements.startupSaveHealth.textContent, /Use Refresh/);
  assert.match(elements.startupSaveMessage.textContent, /History became unreadable/);
  assert.equal(renders, 1);
});
