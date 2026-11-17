const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

test('draft trade alerts stack once, expand, open the selected League Wire post, and close', async () => {
  let nextTimer = 1;
  const timers = new Map();
  const setTimeoutFake = (callback, delay) => {
    const id = nextTimer++;
    timers.set(id, {callback, delay});
    return id;
  };
  const clearTimeoutFake = id => timers.delete(id);
  class FakeElement {
    constructor(selector = '') {
      this.selector = selector;
      this.listeners = {};
      this.classes = new Set();
      this.classList = {add: name => this.classes.add(name)};
      this.dataset = {};
      this.attributes = {};
      this.children = new Map();
      this.childLists = new Map();
      this.removed = false;
    }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    querySelector(selector) {
      if (!this.children.has(selector)) this.children.set(selector, new FakeElement(selector));
      return this.children.get(selector);
    }
    querySelectorAll(selector) {
      if (selector !== '.assistant-notification-item') return [];
      if (this.childLists.has(selector)) return this.childLists.get(selector);
      const count = (this.innerHTML.match(/class="assistant-notification-item"/g) || []).length;
      const items = Array.from({length:count}, (_, index) => {
        const item = new FakeElement(selector);
        item.dataset.notificationIndex = String(index);
        return item;
      });
      this.childLists.set(selector, items);
      return items;
    }
    append() {}
    remove() { this.removed = true; }
  }
  const body = new FakeElement();
  body.append = node => { body.child = node; };
  const scope = {
    window: {},
    document: {createElement: () => new FakeElement(), body},
    localStorage: {getItem: () => null, setItem() {}},
    setTimeout: setTimeoutFake,
    clearTimeout: clearTimeoutFake,
  };
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/assistant-phone.js'), 'utf8'), scope);
  scope.window.AssistantGMPhone.setDraftPlaybackActive(true);
  scope.window.AssistantGMPhone.sync({saveKey:'fixture',enabled:true,messages:[{id:'normal-message',date:'2027-06-24',text:'A regular assistant message.'}]});
  assert.equal(body.child, undefined, 'regular phone messages wait until draft playback finishes');
  let opened;
  scope.window.AssistantGMPhone.sync({saveKey:'fixture',enabled:true,messages:[],onOpen:async message=>{opened=message;}});
  const alert = scope.window.AssistantGMPhone.presentDraftTrades([
    {id:'trade-1',date:'2027-06-24',headline:'Trade completed: Pick #3 for Pick #8.',social_post:{id:'post-1',author:'Maya Chen',handle:'@maya_hoops',text:'The pick math just got interesting.'}},
    {id:'trade-2',date:'2027-06-24',headline:'Another pick moved before the turn.',social_post:{id:'post-2',author:'Noah Reed',handle:'@noahreports',text:'A second team jumps into the first round.'}},
  ]);
  assert.match(body.child.innerHTML, /Trade completed: Pick #3 for Pick #8/);
  assert.match(body.child.innerHTML, /@maya_hoops/);
  assert.match(body.child.innerHTML, /The pick math just got interesting/);
  assert.match(body.child.innerHTML, /Another pick moved before the turn/);
  assert.match(body.child.innerHTML, /assistant-notification-count[^>]*>2</);
  assert.equal([...timers.values()].filter(timer => timer.delay === 2500).length, 1, 'the batch raises the phone only once');
  const stack = body.child.querySelector('.assistant-notification-stack');
  stack.listeners.click({currentTarget:stack});
  assert.ok(body.child.querySelector('.assistant-phone-screen').classes.has('has-expanded-draft-messages'));
  const firstMessage = body.child.querySelectorAll('.assistant-notification-item')[0];
  firstMessage.listeners.click();
  await Promise.resolve();
  assert.equal(opened.target, 'league-wire');
  assert.equal(opened.event_id, 'post-1');
  const transition = [...timers.values()].find(timer => timer.delay === 450);
  assert.ok(transition, 'opening a text closes the phone');
  transition.callback();
  await alert;
  assert.equal(body.child.removed, true);
  scope.window.AssistantGMPhone.setDraftPlaybackActive(false);
  assert.match(body.child.innerHTML, /Assistant GM/, 'queued messages resume after the pick sequence');
});

test('draft trade batch auto-dismisses without requiring interaction', async () => {
  const timers = new Map();
  let nextTimer = 1;
  class FakeElement {
    constructor() { this.listeners = {}; this.classList = {add() {}}; this.children = new Map(); this.removed = false; }
    setAttribute() {}
    addEventListener(name, callback) { this.listeners[name] = callback; }
    querySelector(selector) { if (!this.children.has(selector)) this.children.set(selector, new FakeElement()); return this.children.get(selector); }
    querySelectorAll() { return []; }
    append() {}
    remove() { this.removed = true; }
  }
  const body = new FakeElement();
  body.append = node => { body.child = node; };
  const scope = {
    window:{}, document:{createElement:()=>new FakeElement(),body}, localStorage:{getItem:()=>null,setItem(){}},
    setTimeout:(callback,delay)=>{const id=nextTimer++;timers.set(id,{callback,delay});return id;},
    clearTimeout:id=>timers.delete(id),
  };
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/assistant-phone.js'), 'utf8'), scope);
  const alert = scope.window.AssistantGMPhone.presentDraftTrades([{headline:'Draft-night trade.'}]);
  const autoDismiss = [...timers.values()].find(timer=>timer.delay===2500);
  assert.ok(autoDismiss, 'phone batch closes automatically');
  autoDismiss.callback();
  const transition = [...timers.values()].find(timer=>timer.delay===450);
  assert.ok(transition);
  transition.callback();
  await alert;
  assert.equal(body.child.removed,true);
});

test('multi-pick draft playback waits for each trade alert before revealing the next pick', async () => {
  const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
  const start = app.indexOf('async function playDraftSimulation(');
  const end = app.indexOf('\nfunction updateDraftPlaybackCard()', start);
  const order = [];
  const scope = {
    state: {currentSave:'fixture', data:{draft:null}, busyDepth:0, hydrating:false},
    GameSimulation: {
      draftPlaybackFrame: (_room, _events, count) => ({state:{current_index:count}}),
      reducedMotion: () => true,
      wait: async () => {},
    },
    window: {AssistantGMPhone:{presentDraftTrades:async trades=>{order.push(`trade-batch:${trades.length}`);}}},
    setBusy: value => order.push(`busy:${value}`),
    refreshDashboardAfterPhaseMutation: async (_phase, room) => { scope.state.data.draft=room; order.push('refresh'); },
    updateDraftPlaybackCard: () => order.push(scope.state.draftPlaybackReveal ? `pick:${scope.state.data.draft.state.current_index}` : 'final'),
    showToast: () => order.push('complete'),
    Math,
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(start,end),scope);
  const events=[
    {type:'trade',social_post:{handle:'@before_pick_2'}},
    {type:'pick',overall_pick:2},
    {type:'trade',social_post:{handle:'@before_pick_3'}},
    {type:'pick',overall_pick:3},
  ];
  await scope.playDraftSimulation({state:{current_index:3}},events,2);
  assert.deepEqual(order.filter(value=>value.startsWith('trade-batch:')||value.startsWith('pick:')), [
    'trade-batch:2','pick:1','pick:2',
  ]);
  assert.ok(order.indexOf('final') > order.indexOf('pick:2'));
  assert.equal(scope.state.draftPlaybackRunning,false);
  assert.equal(scope.state.busyDepth,0);
});
