#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto').webcrypto;
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { TextEncoder } = require('node:util');

class ClassList {
  constructor(owner) { this.owner = owner; }
  _tokens() { return new Set(this.owner.className.split(/\s+/).filter(Boolean)); }
  _write(tokens) { this.owner.className = [...tokens].join(' '); }
  add(...names) { const tokens = this._tokens(); names.forEach(name => tokens.add(name)); this._write(tokens); }
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
    this.parentElement = null;
    this.classList = new ClassList(this);
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(value) { this._innerHTML = String(value); if (value === '') this.children = []; }
  appendChild(child) { child.parentElement = this; this.children.push(child); return child; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  click() { assert.equal(typeof this.onclick, 'function'); return this.onclick(); }
}

const selectors = [
  '#wells', '#status', '#primaryCount', '#baselineCount', '#predictions',
  '#explain', '#wellCount', '.result-title', '#commitBtn', '#missingBtn',
  '#recoverBtn', '#completeBtn', '#resetBtn'
];
const elements = Object.fromEntries(selectors.map(selector => [selector, new Element()]));
const outputPanel = new Element();
outputPanel.appendChild(elements['#status']);
const document = {
  querySelector(selector) { assert.ok(elements[selector], `unknown selector ${selector}`); return elements[selector]; },
  createElement() { return new Element(); }
};
const frozenSchedule = Array.from({ length: 64 }, (_, index) => ({
  drug: `drug_${String(index).padStart(2, '0')}`,
  dose: String((index + 1) * 10),
  native: `q${String(index + 1).padStart(3, '0')}`,
  a: index % 2,
  b: 1 - (index % 2)
}));
const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
vm.runInNewContext(source, { document, frozenSchedule, crypto, TextEncoder, Math, Number, Array, String, Object, JSON, Uint8Array });

const trace = () => outputPanel.children.find(item => item.className === 'demo-trace');
const predictions = () => elements['#predictions'].children;
const countState = state => predictions().filter(item => item.dataset.outputState === state).length;
const assertHash = value => assert.match(value, /^[0-9a-f]{64}$/);
const assertNoHash = value => assert.equal(value, '');
const assertTraceRecord = (state, plan, measurement, result, kind) => {
  assert.match(trace().innerHTML, /Inspect full evidence record/);
  assert.match(trace().innerHTML, new RegExp(`"state": "${state}"`));
  assert.match(trace().innerHTML, new RegExp(`"plan_sha256": ${plan ? `"${plan}"` : 'null'}`));
  assert.match(trace().innerHTML, new RegExp(`"measurement_sha256": ${measurement ? `"${measurement}"` : 'null'}`));
  assert.match(trace().innerHTML, new RegExp(`"result_sha256": ${result ? `"${result}"` : 'null'}`));
  assert.match(trace().innerHTML, new RegExp(`"result_kind": "${kind}"`));
};
const assertNoNumericalLeak = items => items.forEach(item => {
  assert.equal(item.dataset.outputState, 'withheld');
  assert.equal(Object.hasOwn(item.dataset, 'value'), false);
  assert.doesNotMatch(item.innerHTML, /\b0\.\d{3}\b/);
  assert.doesNotMatch(item.innerHTML, /width:\d+%/);
  assert.match(item.innerHTML, /<code>WITHHELD<\/code>/);
});
async function independentSha256(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Buffer.from(digest).toString('hex');
}
function independentSeeded(index) {
  const x = Math.sin((index + 1) * 91.733 + 7.2) * 43758.5453;
  return x - Math.floor(x);
}
function independentResponses(mode) {
  const drugs = ['5-FU', 'AZD7762', 'Afatinib', 'Alisertib', 'Atorvastatin', 'Bemcentinib', 'Encorafenib', 'Gedatolisib', 'Gemcitabine', 'Idasanutlin', 'LCL161', 'LGK974', 'Lapatinib', 'Luminespib', 'Methotrexate', 'Napabucasin', 'Palbociclib', 'Panobinostat', 'Pevonedistat', 'Regorafenib', 'SN-38', 'TAS-102', 'Trametinib', 'Volasertib'];
  return drugs.flatMap((drug, index) => {
    if (mode === 'baseline' && index === 2) return [];
    const value = .24 + .56 * independentSeeded(index + 100) + (mode === 'primary' ? .035 * (independentSeeded(index + 300) - .5) : 0);
    return [{ drug, value: value.toFixed(3) }];
  });
}
async function waitTrace(expected) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (trace().dataset.traceState === expected) return;
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  assert.fail(`trace did not reach ${expected}`);
}

async function main() {
  await waitTrace('fresh');
  assert.equal(predictions().length, 24);
  assertNoNumericalLeak(predictions());
  assertNoHash(trace().dataset.planSha256);
  assertNoHash(trace().dataset.measurementSha256);
  assertNoHash(trace().dataset.resultSha256);
  assertTraceRecord('fresh', '', '', '', 'withheld');

  elements['#commitBtn'].click();
  await waitTrace('committed');
  assertNoNumericalLeak(predictions());
  assertHash(trace().dataset.planSha256);
  const planHash = trace().dataset.planSha256;
  const expectedPlanHash = await independentSha256({
    schema: 'dosepilot.browser_demo_plan.v1',
    sample_id: 'fictional_PDO_017',
    run_id: 'demo_run_A',
    orientation: 'A',
    requests: frozenSchedule.map((row, index) => ({
      well: String(index + 1).padStart(2, '0'),
      drug: row.drug,
      dose_nM: row.dose,
      native_id: row.native,
      plate: row.a === 0 ? 'p1' : 'p2'
    }))
  });
  assert.equal(planHash, expectedPlanHash);
  assertNoHash(trace().dataset.measurementSha256);
  assertNoHash(trace().dataset.resultSha256);
  assertTraceRecord('committed', planHash, '', '', 'withheld');

  elements['#missingBtn'].click();
  await waitTrace('missing');
  assertNoNumericalLeak(predictions());
  assert.equal(elements['#wellCount'].textContent, '63 / 64 present');
  assert.equal(trace().dataset.planSha256, planHash);
  assertNoHash(trace().dataset.measurementSha256);
  assertNoHash(trace().dataset.resultSha256);
  assertTraceRecord('missing', planHash, '', '', 'withheld');

  elements['#recoverBtn'].click();
  await waitTrace('recovered');
  assert.equal(countState('baseline'), 23);
  assert.equal(countState('withheld'), 1);
  assert.equal(predictions()[2].dataset.outputState, 'withheld');
  assert.match(predictions()[2].innerHTML, /Afatinib/);
  assert.equal(trace().dataset.planSha256, planHash);
  assertNoHash(trace().dataset.measurementSha256);
  assertHash(trace().dataset.resultSha256);
  assert.equal(trace().dataset.resultKind, 'historical baseline • 23 outputs');
  const baselineHash = trace().dataset.resultSha256;
  assert.equal(baselineHash, await independentSha256({
    schema: 'dosepilot.browser_demo_baseline.v1',
    plan_sha256: planHash,
    outputs: independentResponses('baseline'),
    withheld: ['Afatinib']
  }));
  assertTraceRecord('recovered', planHash, '', baselineHash, 'historical baseline • 23 outputs');

  elements['#completeBtn'].click();
  await waitTrace('complete');
  assert.equal(countState('primary'), 24);
  assert.equal(countState('withheld'), 0);
  assert.equal(trace().dataset.planSha256, planHash);
  assertHash(trace().dataset.measurementSha256);
  assertHash(trace().dataset.resultSha256);
  assert.notEqual(trace().dataset.resultSha256, baselineHash);
  assert.equal(trace().dataset.resultKind, 'bandwidth-0.7 primary • 24 outputs');
  const expectedMeasurementHash = await independentSha256({
    schema: 'dosepilot.browser_demo_measurements.v1',
    plan_sha256: planHash,
    values: Array.from({ length: 64 }, (_, index) => Number((.12 + .78 * independentSeeded(index)).toFixed(4)))
  });
  assert.equal(trace().dataset.measurementSha256, expectedMeasurementHash);
  assert.equal(trace().dataset.resultSha256, await independentSha256({
    schema: 'dosepilot.browser_demo_primary.v1',
    plan_sha256: planHash,
    measurement_sha256: expectedMeasurementHash,
    outputs: independentResponses('primary')
  }));
  assertTraceRecord('complete', planHash, expectedMeasurementHash, trace().dataset.resultSha256, 'bandwidth-0.7 primary • 24 outputs');

  elements['#resetBtn'].click();
  await waitTrace('fresh');
  assertNoNumericalLeak(predictions());
  assertNoHash(trace().dataset.planSha256);
  assertNoHash(trace().dataset.measurementSha256);
  assertNoHash(trace().dataset.resultSha256);
  assertTraceRecord('fresh', '', '', '', 'withheld');

  process.stdout.write(JSON.stringify({
    status: 'PASS',
    states: ['fresh', 'committed', 'missing', 'baseline_recovery', 'complete', 'reset'],
    withheld_before_complete: 24,
    baseline_outputs: 23,
    baseline_withheld: 1,
    primary_outputs: 24,
    plan_hash_stable_across_committed_states: true,
    precompletion_measurement_hash_withheld: true,
    precompletion_primary_hash_withheld: true,
    baseline_result_hash_present: true,
    complete_measurement_hash_present: true,
    complete_primary_hash_present: true,
    full_record_inspectable: true,
    withheld_record_fields_are_null: true
  }) + '\n');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
