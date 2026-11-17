const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const transport = app.slice(app.indexOf('let apiSessionPromise = null;'), app.indexOf('function newIdempotencyKey('));

function harness(handler = () => ({ok: true, status: 200, json: async () => ({ok: true, result: {status: 'ok'}})})) {
  const requests = [];
  const context = {
    state: {busyDepth: 0, hydrating: false, tutorial: false, multiplayer: {session: null}},
    requiredClipboardDecision: () => false,
    setBusy() {},
    fetch: async (url, options) => {
      requests.push({url, options});
      return handler(url, options, requests);
    },
  };
  vm.createContext(context);
  vm.runInContext(transport, context);
  return {context, requests};
}

function success(url) {
  return {ok: true, status: 200, json: async () => url === '/api/session' ? {token: 'runtime-token'} : {ok: true, result: {status: 'ok'}}};
}

test('startup status and concurrent actions fetch one runtime session and attach its token', async () => {
  const {context, requests} = harness(success);
  await Promise.all([context.apiGet('/api/status'), context.action('teams'), context.action('list_saves')]);
  assert.equal(requests.filter(r => r.url === '/api/session').length, 1);
  const bootstrap = requests[0];
  assert.equal(bootstrap.options.cache, 'no-store');
  assert.equal(bootstrap.options.mode, 'same-origin');
  assert.equal(bootstrap.options.credentials, 'same-origin');
  for (const {options} of requests.slice(1)) {
    assert.equal(options.headers['X-NBA-GM-Token'], 'runtime-token');
    assert.equal(options.mode, 'same-origin');
  }
  assert.equal(context.state.busyDepth, 0);
});

test('save loading, export, restore, and recovery retain their payloads and authenticate', async () => {
  const {context, requests} = harness(success);
  const payload = {save_path: '/temporary/save.json'};
  for (const action of ['home', 'export_save', 'recover_save', 'restore_save']) {
    const sent = action === 'restore_save' ? {save_name: 'Imported', archive_base64: 'YWJj'} : payload;
    await context.action(action, sent);
    const request = requests.at(-1);
    assert.equal(request.url, '/api/action');
    assert.deepEqual(JSON.parse(request.options.body), {action, payload: sent});
    assert.equal(request.options.headers['Content-Type'], 'application/json');
    assert.equal(request.options.headers['X-NBA-GM-Token'], 'runtime-token');
    assert.equal(request.options.headers['X-NBA-GM-Backup-Upload'], action === 'restore_save' ? '1' : undefined);
  }
});

test('multiplayer sends both browser protection and the existing manager session', async () => {
  const {context, requests} = harness(success);
  context.state.multiplayer.session = {league_id: 'league', manager_id: 'gm', session_token: 'manager-token'};
  await context.multiplayerRequest('league_state');
  const request = requests.at(-1);
  assert.equal(request.url, '/api/multiplayer');
  assert.equal(request.options.headers['X-NBA-GM-Token'], 'runtime-token');
  assert.equal(request.options.headers['X-NBA-GM-Backup-Upload'], undefined);
  assert.deepEqual(JSON.parse(request.options.body).payload, context.state.multiplayer.session);
});

test('failed bootstrap prevents dispatch and a later attempt can acquire a session', async () => {
  let attempts = 0;
  const {context, requests} = harness(url => url === '/api/session' && ++attempts === 1
    ? {ok: false, status: 403} : success(url));
  await assert.rejects(context.action('recover_save', {save_path: '/temporary/save.json'}), /local game session was rejected/);
  assert.deepEqual(requests.map(r => r.url), ['/api/session']);
  assert.equal(context.state.busyDepth, 0);
  await context.action('teams');
  assert.deepEqual(requests.map(r => r.url), ['/api/session', '/api/session', '/api/action']);
});

test('invalid session responses prevent dispatch and token rejection is shown without replaying actions', async () => {
  const invalid = harness(() => ({ok: true, status: 200, json: async () => ({})}));
  await assert.rejects(invalid.context.action('teams'), /local game session could not be established/);
  assert.equal(invalid.requests.length, 1);
  const rejected = harness(url => url === '/api/session' ? success(url)
    : {ok: false, status: 403, json: async () => ({ok: false, error: 'The local game session is invalid. Refresh the page to reconnect.'})});
  await assert.rejects(rejected.context.action('create_save'), /local game session is invalid/);
  assert.equal(rejected.requests.filter(r => r.url === '/api/action').length, 1);
  assert.equal(rejected.context.state.busyDepth, 0);
});

test('server availability errors tell players to start the local game server', async () => {
  const {context} = harness(url => url === '/api/session'
    ? {ok: false, status: 404}
    : success(url));
  await assert.rejects(context.action('teams'), /local game server is not responding \(HTTP 404\).*Start the game server/);
});
