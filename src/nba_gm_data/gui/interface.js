/* Shared interaction layer. Commands invoke the same controls as pointer input. */
const GameInterface = (() => {
  let config;
  let prefix = "";
  let prefixTimer;
  let overlay;
  let origin;
  let modalOrigin;
  let lastModal = null;
  const history = [];
  let restoring = false;
  let restoreView;
  let commands = [];
  let shown = [];
  let selected = 0;
  const focusable = 'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]';
  const visible = el => Boolean(el?.isConnected && !el.closest('[hidden], [inert]') && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
  const editable = el => Boolean(el?.closest('input, textarea, select, [contenteditable="true"]'));
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const root = () => document.querySelector('#modalRoot:not([hidden])') || document.querySelector('#startupScreen:not([hidden])') || document.getElementById('content');
  const activeControls = scope => [...scope.querySelectorAll(focusable)].filter(visible);
  const findControl = selector => [...(root()?.querySelectorAll(selector) || [])].find(el => visible(el) && !el.disabled);
  const label = el => el.getAttribute('aria-label') || el.textContent.trim().replace(/\s+/g, ' ') || el.title;
  function captureDialogView() {
    const dialog = document.querySelector('#modalRoot [role="dialog"]');
    if (!dialog) return null;
    const controls = activeControls(dialog);
    const focused = document.activeElement;
    return {index:controls.indexOf(focused), id:focused?.id, label:focused ? label(focused) : '',
      scroll:[...dialog.querySelectorAll('*')].map((el,index)=>({index,top:el.scrollTop,left:el.scrollLeft})).filter(s=>s.top || s.left)};
  }

  function clearPrefix() {
    prefix = "";
    clearTimeout(prefixTimer);
    document.getElementById('keySequence')?.remove();
  }

  function availableCommands() {
    const registered = config.commands().filter(c => !c.available || c.available());
    const local = [...(root()?.querySelectorAll('button, [role="button"]') || [])]
      .filter(el => visible(el) && !el.disabled && label(el))
      .map((el, index) => ({id: `control-${index}`, label: label(el), group: 'On this screen', run: () => el.click()}));
    const known = new Set(registered.map(c => c.label.toLowerCase()));
    return [...registered, ...local.filter(c => !known.has(c.label.toLowerCase()))];
  }

  function execute(command) {
    clearPrefix();
    if (config.busy() || (command.available && !command.available())) return;
    Promise.resolve().then(command.run).catch(config.error);
  }

  function closePalette(restore = true) {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    if (restore && visible(origin)) origin.focus({preventScroll: true});
  }

  function renderResults(query = '') {
    const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    shown = commands.filter(c => words.every(w => `${c.label} ${c.group || ''} ${c.keys || ''}`.toLowerCase().includes(w)));
    selected = Math.min(selected, Math.max(0, shown.length - 1));
    const list = overlay.querySelector('[role="listbox"]');
    list.innerHTML = shown.length ? shown.map((c, i) => `<div role="option" id="command-${i}" aria-selected="${i === selected}" data-command-index="${i}"><span>${esc(c.label)}</span><span class="command-trailing">${c.keys ? c.keys.split(' ').map(k => `<kbd>${esc(k)}</kbd>`).join('') : esc(c.group || '')}</span></div>`).join('') : '<p class="command-empty">No matching commands</p>';
    const input = overlay.querySelector('input');
    if (shown.length) input.setAttribute('aria-activedescendant', `command-${selected}`);
    else input.removeAttribute('aria-activedescendant');
    list.querySelector('[aria-selected="true"]')?.scrollIntoView({block:'nearest'});
  }

  function openPalette(help = false) {
    clearPrefix();
    if (overlay) return closePalette();
    origin = document.activeElement;
    commands = help ? [
      ...config.commands().filter(c => c.keys).map(c => ({...c, group:'Shortcuts'})),
      {label:'Move between table rows', keys:'↑ ↓', group:'Tables'},
      {label:'Move across a row / change a slider', keys:'← →', group:'Tables'},
      {label:'Open or select the focused item', keys:'Enter', group:'Tables'},
      {label:'Next / previous control', keys:'Tab Shift+Tab', group:'Navigation'},
      {label:'Close or return to parent dialog', keys:'Esc', group:'Navigation'},
      {label:'Search the current table', keys:'/', group:'Tables'},
    ] : availableCommands();
    selected = 0;
    overlay = document.createElement('div');
    overlay.className = 'command-overlay';
    overlay.innerHTML = `<section class="command-menu" role="dialog" aria-modal="true" aria-label="${help ? 'Keyboard shortcuts' : 'Commands'}"><header><span>${help ? 'Keyboard shortcuts' : 'Commands'}</span><button type="button" aria-label="Close commands">×</button></header><input type="search" role="combobox" aria-expanded="true" aria-controls="command-list" aria-autocomplete="list" aria-label="Search commands" placeholder="${help ? 'Find a shortcut' : 'Go to a screen or run an action'}" autocomplete="off"><div id="command-list" role="listbox" aria-label="Commands"></div></section>`;
    document.body.append(overlay);
    overlay.querySelector('header button').onclick = () => closePalette();
    overlay.addEventListener('click', e => {
      if (e.target === overlay) return closePalette();
      const item = e.target.closest('[data-command-index]');
      if (!item) return;
      const command = shown[Number(item.dataset.commandIndex)];
      if (!command?.run || (command.available && !command.available())) return;
      closePalette(); execute(command);
    });
    overlay.querySelector('input').addEventListener('input', e => {selected = 0; renderResults(e.target.value);});
    renderResults();
    overlay.querySelector('input').focus();
  }

  function trapTab(event, scope) {
    const controls = activeControls(scope);
    if (!controls.length) return;
    const index = controls.indexOf(document.activeElement);
    if (event.shiftKey && index <= 0) { event.preventDefault(); controls.at(-1).focus(); }
    else if (!event.shiftKey && (index === controls.length - 1 || index < 0)) { event.preventDefault(); controls[0].focus(); }
  }

  function moveInTable(event) {
    if (!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)) return false;
    const target = document.activeElement;
    if (editable(target) && !(target.matches('input[type="range"]') && ['ArrowUp','ArrowDown'].includes(event.key))) return false;
    const rowSelector = 'tbody > tr, .season-minute-row, .season-standing-row, .season-prospect-row, .fantasy-player-row, .trade-asset-card';
    const row = target?.closest(rowSelector);
    if (!row) return false;
    const horizontal = ['ArrowLeft','ArrowRight'].includes(event.key);
    const direction = ['ArrowUp','ArrowLeft'].includes(event.key) ? -1 : 1;
    const controls = activeControls(row);
    let next;
    if (horizontal) next = controls[controls.indexOf(target) + direction];
    else {
      const rows = [...row.parentElement.children].filter(el => el.matches(rowSelector) && visible(el));
      const nextRow = rows[rows.indexOf(row) + direction];
      if (nextRow) next = activeControls(nextRow)[Math.max(0, controls.indexOf(target))] || activeControls(nextRow)[0] || nextRow;
    }
    if (!next) {
      if (!horizontal && target.matches('input[type="range"]')) {event.preventDefault();return true;}
      return false;
    }
    event.preventDefault();
    if (!next.matches(focusable)) next.tabIndex = -1;
    next.focus({preventScroll:true}); next.scrollIntoView({block:'nearest',inline:'nearest'});
    return true;
  }

  function keydown(event) {
    if (event.isComposing || event.defaultPrevented) return;
    const key = event.key.toLowerCase();
    if ((event.metaKey || event.ctrlKey) && !event.altKey && key === 'k') {
      event.preventDefault(); if (!event.repeat) openPalette(); return;
    }
    if (overlay) {
      if (event.key === 'Escape') { event.preventDefault(); closePalette(); }
      else if (event.key === 'Tab') trapTab(event, overlay);
      else if (['ArrowDown','ArrowUp'].includes(event.key)) {
        event.preventDefault(); selected = Math.max(0, Math.min(shown.length - 1, selected + (event.key === 'ArrowDown' ? 1 : -1)));
        renderResults(overlay.querySelector('input').value);
      } else if (event.key === 'Enter' && document.activeElement.matches('input')) {
        event.preventDefault(); const command = shown[selected];
        if (!event.repeat && command?.run && (!command.available || command.available())) { closePalette(); execute(command); }
      }
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault(); if (prefix) clearPrefix(); else if (config.modal()) config.closeModal(); return;
    }
    if (event.key === 'Tab' && config.modal()) { trapTab(event, root()); return; }
    if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key) && event.target.matches('[role="tab"]')) {
      const tabs = [...event.target.closest('[role="tablist"]').querySelectorAll('[role="tab"]')].filter(el=>visible(el) && !el.disabled);
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : (tabs.indexOf(event.target)+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      event.preventDefault();
      const name=label(tabs[index]);tabs[index]?.focus();tabs[index]?.click();
      requestAnimationFrame(()=>{const scope=root();if(!scope)return;enhance(scope);[...scope.querySelectorAll('[role="tab"]')].find(el=>label(el)===name)?.focus({preventScroll:true});});
      return;
    }
    if (moveInTable(event)) return;
    if (editable(event.target) || event.metaKey || event.ctrlKey || event.altKey || event.repeat) { clearPrefix(); return; }
    if (!config.modal() && ['ArrowLeft','ArrowRight'].includes(event.key) && config.desktop?.(event.key === 'ArrowRight' ? 1 : -1)) {
      event.preventDefault();clearPrefix();return;
    }
    if (key === '?') {event.preventDefault(); openPalette(true); return;}
    if (key === '/') {
      const search = findControl('input[type="search"], #fantasySearch, #playerFinderFilterValue');
      if (search) {event.preventDefault(); search.focus();} return;
    }
    if (config.busy()) return;
    if (prefix) {
      const sequence = `${prefix} ${key}`; clearPrefix();
      const command = config.commands().find(c => c.keys === sequence && (!c.available || c.available()));
      if (command) {event.preventDefault(); execute(command);} return;
    }
    if (['g','s'].includes(key)) {
      event.preventDefault(); prefix = key;
      const indicator = document.createElement('div'); indicator.id = 'keySequence'; indicator.setAttribute('role','status');
      indicator.innerHTML = `<kbd>${key.toUpperCase()}</kbd> ${key === 'g' ? 'Go to' : 'Simulate'}`;
      document.body.append(indicator); prefixTimer = setTimeout(clearPrefix, 1500);
    }
  }

  function modalWillRender(modal) {
    if (modal && !lastModal) modalOrigin = document.activeElement;
    if (!restoring && modal && lastModal) {
      if (modal.kind !== lastModal.kind) history.push({modal:lastModal, view:captureDialogView()});
      else restoreView = captureDialogView();
    }
    restoring = false;
    lastModal = modal;
    const app = document.getElementById('app');
    if (app) app.inert = Boolean(modal);
    if (!modal) {
      history.length = 0;
      restoreView = null;
      if (visible(modalOrigin)) modalOrigin.focus({preventScroll:true});
      else document.querySelector('.season-command-actions button, #startupLoadSave')?.focus({preventScroll:true});
    }
  }

  function modalDidRender() {
    const dialog = document.querySelector('#modalRoot [role="dialog"]');
    if (!dialog) return;
    dialog.setAttribute('aria-labelledby','game-dialog-title');
    dialog.querySelector('.modal-head h3')?.setAttribute('id','game-dialog-title');
    const close = dialog.querySelector('[data-close-modal]');
    if (close) {close.title = history.length ? 'Back (Esc)' : 'Close (Esc)';close.setAttribute('aria-label',close.title);}
    const preferred = activeControls(dialog).find(el=>el.matches('[autofocus], input[type="search"], .modal-body input:not([type="range"]):not([type="checkbox"]), .modal-body select'));
    enhance(dialog);
    const view = restoreView; restoreView = null;
    const controls = activeControls(dialog);
    const previous = view && (controls.find(el=>view.id && el.id===view.id) || controls.find(el=>view.label && label(el)===view.label) || controls[view.index]);
    (previous || preferred || close || dialog).focus({preventScroll:true});
    if (view) {
      const elements = dialog.querySelectorAll('*');
      view.scroll.forEach(s=>{if(elements[s.index]){elements[s.index].scrollTop=s.top;elements[s.index].scrollLeft=s.left;}});
    }
  }

  function previousModal() { const entry=history.pop(); restoring = true; restoreView=entry?.view; return entry?.modal || null; }

  function sortLocalTable(button) {
    const th = button.closest('th'); const table = th.closest('table');
    const index = [...th.parentElement.children].indexOf(th);
    const asc = th.getAttribute('aria-sort') !== 'ascending';
    table.querySelectorAll('th[aria-sort]').forEach(el => el.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
    const parse = row => {
      const text = row.cells[index]?.textContent.trim() || '';
      if (/^[+−\-$\d.,%M/\s]+$/.test(text)) {const n = Number(text.replace(/[$,%M]/g,'').replace('−','-')); if (Number.isFinite(n)) return n;}
      return text;
    };
    const rows = [...table.tBodies[0].rows];
    rows.sort((a,b) => {const av=parse(a),bv=parse(b);return (typeof av==='number' && typeof bv==='number' ? av-bv : String(av).localeCompare(String(bv),undefined,{numeric:true}))*(asc?1:-1);});
    table.tBodies[0].append(...rows);
  }

  function enhance(scope = document) {
    scope.querySelectorAll('table[data-local-sort], .free-agency-roster-table').forEach(table => {
      table.querySelectorAll('thead th').forEach(th => {
        if (th.querySelector('button') || !th.textContent.trim()) return;
        const button = document.createElement('button'); button.type='button';button.className='local-sort';button.textContent=th.textContent;
        button.title=`Sort by ${th.textContent}`;th.replaceChildren(button);button.onclick=()=>sortLocalTable(button);
      });
    });
    scope.querySelectorAll('input[type="range"]').forEach(input => {
      if (!input.getAttribute('aria-label')) input.setAttribute('aria-label', `Minutes: ${input.closest('.season-minute-row, tr')?.querySelector('button')?.textContent.trim() || 'Player'}`);
    });
    scope.querySelectorAll('.tabs, .free-agency-market-scopes').forEach(tabs => {
      tabs.setAttribute('role','tablist');
      tabs.querySelectorAll('button').forEach(button=>{button.setAttribute('role','tab');button.setAttribute('aria-selected', String(button.matches('.active, .is-active')));});
    });
    scope.querySelectorAll('.fantasy-player-row[role="button"]').forEach(row => {
      if (row.dataset.keyBound) return;
      row.dataset.keyBound='true';row.addEventListener('keydown',e=>{if(e.target===row && ['Enter',' '].includes(e.key)){e.preventDefault();row.click();}});
    });
    // Headers carry commands; data rows remain text, with no button chrome.
    scope.querySelectorAll('.section-head button, .season-panel-header button, .season-command-actions button, .season-sim-actions button, .phase-workspace-controls button, .playoff-command-controls button, .modal-head button, .toolbar button').forEach(button => button.classList.add('ui-command'));
    const hints = [
      ['[data-dashboard-trade]:not([data-dashboard-trade="finder"]), [data-fa-open-trade]', 'G T'],
      ['[data-dashboard-trade="finder"]', 'G B'],
      ['[data-assets-trade="builder"]','G T'], ['[data-assets-trade="finder"]','G B'],
      ['[data-dashboard-offers], [data-assets-offers]', 'G O'], ['[data-dashboard-player-finder]', 'G F'],
      ['[data-dashboard-view="draft"], [data-dashboard-prospects], [data-season-prospects]', 'G P'],
      ['[data-dashboard-view="calendar"]', 'G C'], ['[data-dashboard-view="staff"]', 'G S'],
      ['[data-team-development]', 'G D'],
      ['[data-dashboard-settings], [data-assets-settings]', 'G ,'],
      ['[data-interface-home]', 'G H'],
      ['[data-advance="next-event"], [data-playoff-sim="game"], #fantasySimOne, #draftSimCurrent, #faAdvanceDay, #reSignAdvanceDay', 'S E'],
      ['[data-advance="week"]', 'S W'], ['[data-advance="month"]', 'S M'],
      ['#draftToUser, #fantasyToUser', 'S P'], ['[data-playoff-sim="round"]', 'S R'],
      ['#playoffAdvanceStage, #draftAdvanceStage, #faAdvanceStage, [data-advance="next-season"]', 'S N'],
      ['[data-close-modal]', 'Esc'],
    ];
    hints.forEach(([selector,keys])=>scope.querySelectorAll(selector).forEach(button=>{
      if (button.querySelector('[data-key-hint]')) return;
      const name=label(button);button.setAttribute('aria-label',name);
      button.title=`${name} (${keys})`;
      const hint=document.createElement('span');hint.dataset.keyHint=keys;hint.className='shortcut-hint';hint.setAttribute('aria-hidden','true');hint.textContent=keys;
      button.append(hint);
    }));
  }

  function init(options) {
    config=options;
    document.addEventListener('keydown',keydown);
    document.addEventListener('click',e=>{
      const sort=e.target.closest('[data-sort-table]');
      if (!sort || !sort.closest('table')?.tBodies.length) return;
      e.preventDefault();e.stopImmediatePropagation();sortLocalTable(sort);
    },true);
    document.addEventListener('click',e=>{
      const tab=e.target.closest('[role="tab"]');
      if(tab) tab.closest('[role="tablist"]')?.querySelectorAll('[role="tab"]').forEach(t=>t.setAttribute('aria-selected',String(t===tab)));
    });
    let queued=false;
    const observer=new MutationObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;enhance();});});
    observer.observe(document.getElementById('app'),{childList:true,subtree:true});
    enhance();
  }

  return {init, enhance, openPalette, modalWillRender, modalDidRender, previousModal, findControl, visible};
})();
