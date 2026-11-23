/* House table system: one sort comparator, one header markup and one row/column state for every card table
   (Minutes + Availability, Player Development, Coaching Staff, Standings, Next Opponent). Styling lives in
   house-table.css; tables opt in with data attributes so their own class names stay unchanged:
     [data-house-table]   the table container (gets data-house-key / data-house-col for the active sort)
     [data-house-head]    the header row; sortable headers are [data-house-header] cells holding a button
     [data-house-row]     a body row (data-house-order = its deterministic tie-break position)
   Sorting only moves rows. It never changes the values in them. */
(() => {
  "use strict";

  const collator = typeof Intl === "object" && Intl.Collator
    ? new Intl.Collator("en", {sensitivity: "base", numeric: true})
    : {compare: (a, b) => (a < b ? -1 : a > b ? 1 : 0)};
  const fold = (text) => String(text ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
  const escapeAttr = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"})[c]);

  // A raw cell value as a sortable value. Blank, dash and non-numeric values are "missing" and always sort last.
  function sortValue(raw, type = "number") {
    if (type === "text") {
      const text = fold(raw);
      return {value: text, missing: !text || text === "—" || text === "-"};
    }
    if (raw === null || raw === undefined || typeof raw === "boolean") return {value: 0, missing: true};
    const text = typeof raw === "number" ? raw : String(raw).trim();
    if (text === "" || text === "—" || text === "-") return {value: 0, missing: true};
    const number = Number(text);
    return Number.isFinite(number) ? {value: number, missing: false} : {value: 0, missing: true};
  }

  // Compare two {value, missing, order} entries. Missing values sort last in both directions; equal values keep
  // their tie-break order (ascending in both directions), so a sort is deterministic and reversible.
  function compare(left, right, direction = "asc") {
    if (left.missing !== right.missing) return left.missing ? 1 : -1;
    let result = 0;
    if (!left.missing) {
      result = typeof left.value === "string" || typeof right.value === "string"
        ? collator.compare(String(left.value), String(right.value))
        : left.value - right.value;
      if (result && direction === "desc") result = -result;
    }
    return result || (Number(left.order) || 0) - (Number(right.order) || 0);
  }

  // Order items by one column. valueOf(item) returns the raw value; orderOf(item) the tie-break position.
  function order(items, {direction = "asc", type = "number", valueOf, orderOf = (_item, index) => index}) {
    return items
      .map((item, index) => ({item, ...sortValue(valueOf(item), type), order: orderOf(item, index)}))
      .sort((left, right) => compare(left, right, direction))
      .map((entry) => entry.item);
  }

  // Clicking the active column flips it; a new column starts in its natural direction.
  function nextSort(current, key, columns) {
    const column = columns[key];
    if (!column || column.sortable === false) return current;
    if (current?.key === key) return {key, direction: current.direction === "desc" ? "asc" : "desc"};
    return {key, direction: column.first || (column.type === "text" ? "asc" : "desc")};
  }

  const ariaSort = (direction) => direction === "desc" ? "descending" : direction === "asc" ? "ascending" : "none";

  // Header cell: a real button inside a columnheader, so Tab reaches it and Enter/Space sorts.
  // keys: one key, or several sub-sorts sharing a column (e.g. Season / Month).
  function headerCell({key, label, sort, title = "", className = "", extra = "", keys = null, attributes = ""}) {
    const subKeys = keys || [[key, label]];
    const activeKey = subKeys.find(([subKey]) => subKey === sort?.key)?.[0];
    const direction = activeKey ? sort.direction : "none";
    const buttons = subKeys.map(([subKey, subLabel, subTitle = ""]) => {
      const active = subKey === sort?.key;
      const hint = subTitle || title;
      return `<button type="button" class="house-sort${active ? " is-active" : ""}" data-house-sort="${escapeAttr(subKey)}"${hint ? ` title="${escapeAttr(hint)}"` : ""}>${subLabel}<i class="house-sort-arrow" aria-hidden="true">${active ? (sort.direction === "desc" ? "▼" : "▲") : ""}</i></button>`;
    }).join(subKeys.length > 1 ? `<i class="house-sort-divider" aria-hidden="true">·</i>` : "");
    return `<span role="columnheader" class="${className ? `${className} ` : ""}house-th${activeKey ? " is-sorted" : ""}" data-house-header="${escapeAttr(subKeys.map(([subKey]) => subKey).join(" "))}" aria-sort="${ariaSort(direction)}"${attributes ? ` ${attributes}` : ""}>${buttons}${extra}</span>`;
  }

  // Stripe rows in their on-screen order (first row white, second grey, ...). Rows may be reordered visually by
  // grid-row, so striping follows the given order, not the DOM order.
  function stripe(rows) {
    rows.filter((row) => !row.hidden).forEach((row, index) => row.toggleAttribute("data-house-alt", index % 2 === 1));
  }

  // Place the sorted-column fill: the column's left edge and width inside a row (half the column gap added on each
  // side), in the row's own unscaled pixels. Rows share one grid template, so the first row stands for all of them;
  // the header row is measured on its own.
  function measureRow(row, column) {
    const cell = row?.children?.[column - 1];
    if (!cell || typeof row.getBoundingClientRect !== "function") return null;
    const rowBox = row.getBoundingClientRect();
    const cellBox = cell.getBoundingClientRect();
    if (!rowBox.width || !cellBox.width) return null;
    const scale = row.offsetWidth ? rowBox.width / row.offsetWidth : 1;
    const gap = parseFloat(getComputedStyle(row).columnGap) || 0;
    const width = row.clientWidth || rowBox.width / scale;
    const left = Math.max(0, (cellBox.left - rowBox.left) / scale - (row.clientLeft || 0) - gap / 2);
    // The first and last columns run to the row's edges (past its padding), so the fill never stops a few pixels
    // short of the card border (taste deck round 2: Development's Change column).
    const last = column === row.children.length;
    const right = last ? width : Math.min(width, (cellBox.right - rowBox.left) / scale - (row.clientLeft || 0) + gap / 2);
    return {left: column === 1 ? 0 : left, width: Math.max(0, right - (column === 1 ? 0 : left))};
  }

  function measureSortColumn(table) {
    if (!table || typeof getComputedStyle !== "function") return;
    const column = Number(table.dataset.houseCol) || 0;
    const head = table.querySelector(":scope > [data-house-head]");
    if (!column) {
      table.style.removeProperty("--house-sort-left");
      table.style.removeProperty("--house-sort-width");
      head?.style.removeProperty("--house-sort-left");
      head?.style.removeProperty("--house-sort-width");
      return;
    }
    const row = [...table.querySelectorAll(":scope > [data-house-row]")].find((item) => item.offsetParent !== null || item.getClientRects().length);
    const body = measureRow(row, column);
    if (body) {
      table.style.setProperty("--house-sort-left", `${body.left.toFixed(1)}px`);
      table.style.setProperty("--house-sort-width", `${body.width.toFixed(1)}px`);
    }
    const header = measureRow(head, column);
    if (header && head) {
      head.style.setProperty("--house-sort-left", `${header.left.toFixed(1)}px`);
      head.style.setProperty("--house-sort-width", `${header.width.toFixed(1)}px`);
    }
  }

  const observed = typeof WeakSet === "function" ? new WeakSet() : null;
  function observe(table) {
    if (!observed || observed.has(table) || typeof ResizeObserver !== "function") return;
    observed.add(table);
    new ResizeObserver(() => measureSortColumn(table)).observe(table);
  }

  // Mark the header and column for the active sort. columnOf(key) returns the 1-based column index.
  function markSort(table, sort, columnOf) {
    if (!table) return;
    table.dataset.houseKey = sort?.key || "";
    const column = sort ? columnOf(sort.key) : 0;
    if (column) table.dataset.houseCol = String(column);
    else delete table.dataset.houseCol;
    measureSortColumn(table);
    observe(table);
    table.querySelectorAll("[data-house-header]").forEach((cell) => {
      const keys = cell.dataset.houseHeader.split(" ");
      const active = Boolean(sort) && keys.includes(sort.key);
      cell.classList.toggle("is-sorted", active);
      cell.setAttribute("aria-sort", active ? ariaSort(sort.direction) : "none");
      cell.querySelectorAll("[data-house-sort]").forEach((button) => {
        const on = Boolean(sort) && button.dataset.houseSort === sort.key;
        button.classList.toggle("is-active", on);
        const arrow = button.querySelector(".house-sort-arrow");
        if (arrow) arrow.textContent = on ? (sort.direction === "desc" ? "▼" : "▲") : "";
      });
    });
  }

  // Reorder a table's rows in the DOM (keeps keyboard focus inside the table) and restripe.
  function placeRows(table, rows) {
    const focused = typeof document === "object" ? document.activeElement : null;
    const keepFocus = focused && table.contains(focused) ? focused : null;
    rows.forEach((row) => { row.style.gridRow = ""; table.append(row); });
    if (keepFocus && keepFocus !== document.activeElement && typeof keepFocus.focus === "function") keepFocus.focus({preventScroll: true});
    stripe(rows);
  }

  window.HouseTable = Object.freeze({sortValue, compare, order, nextSort, ariaSort, headerCell, stripe, markSort, measureSortColumn, placeRows, fold});
})();
