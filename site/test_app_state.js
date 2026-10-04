#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class ClassList {
  constructor(owner) { this.owner = owner; }
  _tokens() { return new Set(this.owner.className.split(/\s+/).filter(Boolean)); }
  _write(tokens) { this.owner.className = [...tokens].join(' '); }
  add(...names) { const tokens = this._tokens(); names.forEach((name) => tokens.add(name)); this._write(tokens); }
  toggle(name, force) {
    const tokens = this._tokens();
    const enabled = force === undefined ? !tokens.has(name) : Boolean(force);
    if (enabled) tokens.add(name); else tokens.delete(name);
    this._write(tokens);
    return enabled;
  }
}

class Element {
  constructor() {
    this._innerHTML = '';
    this.textContent = '';
    this.className = '';
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.onclick = null;
    this.classList = new ClassList(this);
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(value) { this._innerHTML = String(value); if (value === '') this.children = []; }
  appendChild(child) { this.children.push(child); return child; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  click() { assert.equal(typeof this.onclick, 'function'); this.onclick(); }
}

const selectors = [
  '#wells', '#status', '#primaryCount', '#baselineCount', '#predictions',
  '#explain', '#wellCount', '.result-title', '#commitBtn', '#missingBtn',
  '#recoverBtn', '#completeBtn', '#resetBtn'
];
const elements = Object.fromEntries(selectors.map((selector) => [selector, new Element()]));
const document = {
  querySelector(selector) { assert.ok(elements[selector], `unknown selector ${selector}`); return elements[selector]; },
  createElement() { return new Element(); }
};
const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
vm.runInNewContext(source, { document, Math, Number, Array, String });

const predictions = () => elements['#predictions'].children;
const countState = (state) => predictions().filter((item) => item.dataset.outputState === state).length;
const assertNoNumericalLeak = (items) => items.forEach((item) => {
  assert.equal(item.dataset.outputState, 'withheld');
  assert.equal(Object.hasOwn(item.dataset, 'value'), false);
  assert.doesNotMatch(item.innerHTML, /\b0\.\d{3}\b/);
  assert.doesNotMatch(item.innerHTML, /width:\d+%/);
  assert.match(item.innerHTML, /<code>WITHHELD<\/code>/);
});

assert.equal(predictions().length, 24);
assertNoNumericalLeak(predictions());
assert.equal(elements['#primaryCount'].textContent, '0');
assert.equal(elements['#baselineCount'].textContent, '0');
assert.equal(elements['.result-title'].textContent, '24 fixed response-summary slots');

elements['#commitBtn'].click();
assertNoNumericalLeak(predictions());
assert.equal(elements['#status'].textContent, 'Committed • identities locked');

elements['#missingBtn'].click();
assertNoNumericalLeak(predictions());
assert.equal(elements['#wellCount'].textContent, '63 / 64 present');
assert.equal(elements['#primaryCount'].textContent, '0');

elements['#recoverBtn'].click();
assert.equal(predictions().length, 24);
assert.equal(countState('baseline'), 23);
assert.equal(countState('withheld'), 1);
assert.equal(predictions()[2].dataset.outputState, 'withheld');
assert.match(predictions()[2].innerHTML, /Afatinib/);
assert.equal(elements['#primaryCount'].textContent, '0');
assert.equal(elements['#baselineCount'].textContent, '23');
assert.equal(elements['.result-title'].textContent, '23 historical estimates • 1 withheld');

elements['#completeBtn'].click();
assert.equal(countState('primary'), 24);
assert.equal(countState('withheld'), 0);
assert.equal(elements['#primaryCount'].textContent, '24');
assert.equal(elements['#baselineCount'].textContent, '0');
assert.equal(elements['.result-title'].textContent, '24 fictional response summaries');
predictions().forEach((item) => assert.match(item.dataset.value, /^0\.\d{3}$/));

elements['#resetBtn'].click();
assertNoNumericalLeak(predictions());
assert.equal(elements['#wellCount'].textContent, '64 / 64 present');

process.stdout.write(JSON.stringify({
  status: 'PASS',
  states: ['fresh', 'committed', 'missing', 'baseline_recovery', 'complete', 'reset'],
  withheld_before_complete: 24,
  baseline_outputs: 23,
  baseline_withheld: 1,
  primary_outputs: 24
}) + '\n');
