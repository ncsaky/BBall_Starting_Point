/* Shared interaction layer. Commands invoke the same controls as pointer input. */
const GameInterface = (() => {
  let config;
  // An armed S/G prefix has no time limit; a click elsewhere, Escape, or focus entering a text field disarms it.
  let prefix = "";
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
  const MODIFIER_KEYS = new Set(['Shift','Control','Alt','Meta','CapsLock','OS','Fn']);
  const editable = el => Boolean(el?.closest('input, textarea, select, [contenteditable="true"]'));
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const root = () => document.querySelector('#modalRoot:not([hidden])') || document.querySelector('#startupScreen:not([hidden])') || document.getElementById('content');
  const activeControls = scope => [...scope.querySelectorAll(focusable)].filter(visible);
  const findControl = (selector, {includeHidden = false} = {}) => [...(root()?.querySelectorAll(selector) || [])].find(el => (includeHidden || visible(el)) && !el.disabled && !el.closest('.is-phase-locked'));
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
    overlay.innerHTML = `<section class="command-menu" role="dialog" aria-modal="true" aria-label="${help ? 'Keyboard shortcuts' : 'Commands'}"><header class="command-menu-titlebar"><div class="command-menu-title"><span class="card-board-window-mark" aria-hidden="true"></span><span>${help ? 'Keyboard shortcuts' : 'Commands'}</span></div><button type="button" class="command-menu-close" aria-label="Close commands">×</button></header><input type="search" role="combobox" aria-expanded="true" aria-controls="command-list" aria-autocomplete="list" aria-label="Search commands" placeholder="${help ? 'Find a shortcut' : 'Go to a screen or run an action'}" autocomplete="off"><div id="command-list" role="listbox" aria-label="Commands"></div></section>`;
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
      event.preventDefault();
      if (event.repeat) return;
      if (prefix) clearPrefix();
      else if (config.modal()) config.closeModal();
      else if (event.shiftKey) window.CardBoard?.toggleActiveMinimize();
      else window.CardBoard?.closeActive();
      return;
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
    if (editable(event.target)) { clearPrefix(); return; }
    // Browser shortcuts, held-key repeats and bare modifier presses pass through and leave the prefix armed.
    if (event.metaKey || event.ctrlKey || event.altKey || event.repeat || MODIFIER_KEYS.has(event.key)) return;
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
      const previousPrefix = prefix;
      const sequence = `${prefix} ${key}`; clearPrefix();
      const command = config.commands().find(c => c.keys === sequence && (!c.available || c.available()));
      if (command) {
        event.preventDefault();
        if (previousPrefix === 's' || previousPrefix === 'g') {
          const trigger = document.querySelector(previousPrefix === 's' ? '[data-sim-menu-trigger]' : '[data-trade-menu-trigger]');
          if (trigger?.getAttribute('aria-expanded') === 'true') trigger.click();
        }
        execute(command);
      }
      return;
    }
    if (!config.modal() && ['m', 'p', ' '].includes(key)) {
      const handled = key === 'm'
        ? window.CardBoard?.toggleActiveMinimize()
        : key === 'p'
          ? window.CardBoard?.toggleActivePin()
          : window.CardBoard?.toggleActiveExpansion();
      if (handled) event.preventDefault();
      if (handled) return;
    }
    if (key === 't' && !config.modal()) {
      const trigger = document.querySelector('[data-trade-menu-trigger]');
      if (trigger && !trigger.disabled) { event.preventDefault(); trigger.click(); }
      return;
    }
    if (['g','s'].includes(key)) {
      event.preventDefault(); prefix = key;
      const indicator = document.createElement('div'); indicator.id = 'keySequence'; indicator.setAttribute('role','status');
      indicator.innerHTML = `<kbd>${key.toUpperCase()}</kbd> ${key === 'g' ? 'Go to' : 'Simulate'}`;
      document.body.append(indicator);
      if (key === 's' && !config.modal()) {
        const trigger = document.querySelector('[data-sim-menu-trigger]');
        if (trigger && !trigger.disabled && trigger.getAttribute('aria-expanded') !== 'true') trigger.click();
      }
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

  function syncSortedTable(table) {
    const headerCells = table.tHead?.rows[0]?.cells || [];
    const activeIndex = [...headerCells].findIndex(th => ['ascending','descending'].includes(th.getAttribute('aria-sort')));
    [...table.tBodies].forEach(body => [...body.rows].forEach(row => [...row.cells].forEach((cell, index) => {
      cell.classList.toggle('is-sorted-value', activeIndex >= 0 && index === activeIndex);
    })));
  }

  function syncSortedValues(scope = document) {
    const tables = [...(scope.matches?.('table') ? [scope] : []), ...scope.querySelectorAll('table')];
    tables.forEach(syncSortedTable);
    const prospectTables = [...(scope.matches?.('.season-prospects-table') ? [scope] : []), ...scope.querySelectorAll('.season-prospects-table')];
    prospectTables.forEach(table => {
      const headers = table.querySelector('.season-prospects-head');
      const rows = table.querySelectorAll('.season-prospect-row');
      const activeIndex = [...(headers?.children || [])].findIndex(button => button.getAttribute('aria-pressed') === 'true');
      rows.forEach(row => [...row.children].forEach((cell, index) => {
        cell.classList.toggle('is-sorted-value', activeIndex >= 0 && index === activeIndex);
      }));
    });
  }

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
    syncSortedTable(table);
  }

  // Every table with a header row sorts on a header click (again to flip), unless it already has its own sorting or
  // is a year-by-year ledger (user playtest 2026-11-22). Ranks, names and positions start smallest-first; other
  // columns biggest-first. Rows that span the table (DNP lines) and blank cells stay at the bottom.
  const AUTO_SORT_SKIP = '.ss-table, .fa-cap-table, .trade-ledger, [data-no-sort], [data-local-sort], .free-agency-roster-table';
  const AUTO_SORT_ASCENDING = /^(#|rk|rank|seed|pick|team|player|name|prospect|pos|position|from|year|season|date|body part|opp|opponent|why|note|decision|option|who decides)\.?$/i;
  function autoSortValue(cell) {
    const text = (cell?.textContent || '').trim();
    if (!text || /^(—|-|–)$/.test(text)) return null;
    const record = text.match(/^(\d+)-(\d+)$/);
    if (record) return Number(record[1]) / Math.max(1, Number(record[1]) + Number(record[2]));
    const arrow = text.match(/^([▲▼↑↓+−-])\s*([\d.]+)/);
    if (arrow) return (/[▼↓−-]/.test(arrow[1]) ? -1 : 1) * Number(arrow[2]);
    const plain = text.replace(/[$,%M]/g, '').replace('−', '-').replace(/\.$/, '');
    if (/^-?[\d.]+$/.test(plain)) return Number(plain);
    return text.toLowerCase();
  }
  function sortAutoTable(th) {
    const table = th.closest('table'); const body = table.tBodies[0]; if (!body) return;
    const heads = [...th.parentElement.children]; const index = heads.indexOf(th);
    const current = th.getAttribute('aria-sort');
    const asc = current ? current !== 'ascending' : AUTO_SORT_ASCENDING.test(th.textContent.trim());
    heads.forEach(el => el.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
    const rows = [...body.rows];
    const full = rows.filter(row => row.cells.length === heads.length);
    const rest = rows.filter(row => row.cells.length !== heads.length);
    full.sort((a, b) => {
      const av = autoSortValue(a.cells[index]); const bv = autoSortValue(b.cells[index]);
      if (av === null || bv === null) return av === bv ? 0 : (av === null ? 1 : -1);
      const order = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv), undefined, {numeric: true});
      return asc ? order : -order;
    });
    body.append(...full, ...rest);
    syncSortedTable(table);
  }
  function enhanceAutoSort(scope) {
    const tables = [...(scope.matches?.('table') ? [scope] : []), ...scope.querySelectorAll('table')];
    tables.forEach(table => {
      if (table.dataset.autoSort || table.matches(AUTO_SORT_SKIP)) return;
      const heads = [...(table.tHead?.rows[0]?.cells || [])];
      if (!heads.length || table.tHead.querySelector('button, [data-ss-sort], [aria-sort]')) return;
      if (/^(year|season)$/i.test(heads[0].textContent.trim()) || (table.tBodies[0]?.rows.length || 0) < 3) return;
      table.dataset.autoSort = '1';
      heads.forEach(th => {
        const name = th.textContent.trim();
        if (!name || /^actions?$/i.test(name) || th.querySelector('.sr-only')) return;
        th.tabIndex = 0; th.classList.add('auto-sort-head'); if (!th.title) th.title = `Sort by ${name}`;
        th.addEventListener('click', () => sortAutoTable(th));
        th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); sortAutoTable(th); } });
      });
    });
  }

  function enhance(scope = document) {
    enhanceAutoSort(scope);
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
      ['[data-dashboard-settings], [data-assets-settings]', 'G ,'],
      ['[data-interface-home]', 'G H'],
      ['.card-board-gallery-toggle', 'G C'],
      ['[data-window-switcher-open]', 'G W'],
      ['[data-league-activity-view-all]', 'G V'],
      ['[data-board-snap]', 'G R'],
      ['[data-trade-menu-trigger]', 'T'],
      ['[data-trade-menu-item="finder"]', 'G B'], ['[data-trade-menu-item="builder"]', 'G T'], ['[data-trade-menu-item="offers"]', 'G O'],
      ['[data-sim-menu-trigger]', 'S'],
      ['[data-sim-menu-item="next-event"]', 'E'], ['[data-sim-menu-item="week"]', 'W'], ['[data-sim-menu-item="month"]', 'M'],
      ['[data-advance="next-event"], #fantasySimOne, #draftSimCurrent, #faAdvanceDay, #reSignAdvanceDay', 'S E'],
      ['[data-advance="week"]', 'S W'], ['[data-advance="month"]', 'S M'],
      ['#draftToUser, #fantasyToUser', 'S P'],
      ['#postseasonAdvance, #draftRevealLottery, #draftEnterNight, #draftAdvanceStage, #faAdvanceStage, [data-advance="next-season"]', 'S N'],
      ['[data-close-modal]', 'Esc'],
    ];
    hints.forEach(([selector,keys])=>scope.querySelectorAll(selector).forEach(button=>{
      if (button.querySelector('[data-key-hint]')) return;
      const name=label(button);button.setAttribute('aria-label',name);
      button.title=button.matches('[data-window-switcher-open]') ? `${name} (${keys}; Option/Alt+Tab forward, Option/Alt+${String.fromCharCode(96)} backward)` : name.endsWith(`(${keys})`) ? name : `${name} (${keys})`;
      const hint=document.createElement('span');hint.dataset.keyHint=keys;hint.className='shortcut-hint';hint.setAttribute('aria-hidden','true');hint.textContent=keys;
      button.append(hint);
    }));
    syncSortedValues(scope);
  }

  function init(options) {
    config=options;
    document.addEventListener('keydown',keydown);
    // Capture phase: open toolbar menus stop Escape before it bubbles to the document.
    document.addEventListener('keydown',event=>{
      if (event.key === 'Escape' && prefix && !overlay && !event.isComposing) { event.preventDefault(); clearPrefix(); }
    },true);
    document.addEventListener('pointerdown',()=>{ if (prefix) clearPrefix(); },true);
    document.addEventListener('focusin',event=>{ if (prefix && editable(event.target)) clearPrefix(); });
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
