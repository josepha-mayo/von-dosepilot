const wellsEl = document.querySelector('#wells');
const statusEl = document.querySelector('#status');
const primaryEl = document.querySelector('#primaryCount');
const baselineEl = document.querySelector('#baselineCount');
const predEl = document.querySelector('#predictions');
const explainEl = document.querySelector('#explain');
const countEl = document.querySelector('#wellCount');
const resultTitleEl = document.querySelector('.result-title');
const drugs = ['5-FU', 'AZD7762', 'Afatinib', 'Alisertib', 'Atorvastatin', 'Bemcentinib', 'Encorafenib', 'Gedatolisib', 'Gemcitabine', 'Idasanutlin', 'LCL161', 'LGK974', 'Lapatinib', 'Luminespib', 'Methotrexate', 'Napabucasin', 'Palbociclib', 'Panobinostat', 'Pevonedistat', 'Regorafenib', 'SN-38', 'TAS-102', 'Trametinib', 'Volasertib'];
const missingBaselineTarget = 2;
const traceEl = document.createElement('section');
traceEl.className = 'demo-trace';
traceEl.setAttribute('aria-live', 'polite');
traceEl.setAttribute('aria-label', 'Browser-local evidence trace preview');
statusEl.parentElement.appendChild(traceEl);

let state = 'fresh';
let missing = -1;
let values = [];
let traceEpoch = 0;

function seeded(i) {
  const x = Math.sin((i + 1) * 91.733 + 7.2) * 43758.5453;
  return x - Math.floor(x);
}

function makeValues() {
  values = Array.from({ length: 64 }, (_, i) => Number((.12 + .78 * seeded(i)).toFixed(4)));
}

function responseValue(index, mode) {
  return .24 + .56 * seeded(index + 100) + (mode === 'primary' ? .035 * (seeded(index + 300) - .5) : 0);
}

function responseRows(mode) {
  return drugs.flatMap((drug, index) => {
    if (mode === 'baseline' && index === missingBaselineTarget) return [];
    return [{ drug, value: responseValue(index, mode).toFixed(3) }];
  });
}

function renderWells() {
  wellsEl.innerHTML = '';
  for (let i = 0; i < 64; i += 1) {
    const well = document.createElement('div');
    well.className = `well ${i % 2 ? 'p2' : 'p1'}`;
    if (state !== 'fresh') well.classList.add('committed');
    if (i === missing) well.classList.add('missing');
    if (state === 'complete') well.classList.add('complete');
    well.textContent = String(i + 1).padStart(2, '0');
    well.title = `Fictional well ${i + 1} • ${i % 2 ? 'p2' : 'p1'}`;
    wellsEl.appendChild(well);
  }
  countEl.textContent = `${missing >= 0 ? '63 / 64' : '64 / 64'} present`;
}

function predictions(mode) {
  predEl.innerHTML = '';
  drugs.forEach((drug, index) => {
    const item = document.createElement('div');
    item.className = 'prediction';
    const withheld = mode === 'none' || (mode === 'baseline' && index === missingBaselineTarget);
    if (withheld) {
      item.classList.add('withheld');
      item.dataset.outputState = 'withheld';
      item.setAttribute('aria-label', `${drug}: withheld`);
      item.innerHTML = `<span>${drug}</span><span class="bar"><i></i></span><code>WITHHELD</code>`;
    } else {
      const value = responseValue(index, mode);
      item.dataset.outputState = mode;
      item.dataset.value = value.toFixed(3);
      item.setAttribute('aria-label', `${drug}: ${value.toFixed(3)}`);
      item.innerHTML = `<span>${drug}</span><span class="bar"><i style="width:${Math.round(value * 100)}%"></i></span><code>${value.toFixed(3)}</code>`;
    }
    predEl.appendChild(item);
  });
  predEl.classList.toggle('muted', mode === 'none');
  resultTitleEl.textContent = mode === 'primary'
    ? '24 fictional response summaries'
    : mode === 'baseline'
      ? '23 historical estimates • 1 withheld'
      : '24 fixed response-summary slots';
}

function planPayload() {
  return {
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
  };
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

function displayHash(value) {
  return value ? `sha256:${value.slice(0, 12)}…${value.slice(-8)}` : 'WITHHELD';
}

async function renderTrace(mode) {
  const epoch = ++traceEpoch;
  const committed = mode !== 'fresh';
  const planHash = committed ? await sha256(planPayload()) : '';
  let measurementHash = '';
  let resultHash = '';
  let resultKind = 'withheld';

  if (mode === 'recovered') {
    resultHash = await sha256({
      schema: 'dosepilot.browser_demo_baseline.v1',
      plan_sha256: planHash,
      outputs: responseRows('baseline'),
      withheld: [drugs[missingBaselineTarget]]
    });
    resultKind = 'historical baseline • 23 outputs';
  } else if (mode === 'complete') {
    measurementHash = await sha256({
      schema: 'dosepilot.browser_demo_measurements.v1',
      plan_sha256: planHash,
      values
    });
    resultHash = await sha256({
      schema: 'dosepilot.browser_demo_primary.v1',
      plan_sha256: planHash,
      measurement_sha256: measurementHash,
      outputs: responseRows('primary')
    });
    resultKind = 'bandwidth-0.7 primary • 24 outputs';
  }

  if (epoch !== traceEpoch) return;
  traceEl.dataset.traceState = mode;
  traceEl.dataset.planSha256 = planHash;
  traceEl.dataset.measurementSha256 = measurementHash;
  traceEl.dataset.resultSha256 = resultHash;
  traceEl.dataset.resultKind = resultKind;
  traceEl.innerHTML = `
    <div class="trace-title"><b>Browser-local evidence preview</b><span>${mode}</span></div>
    <div class="trace-row"><span>Plan commitment</span><code title="${planHash}">${displayHash(planHash)}</code></div>
    <div class="trace-row"><span>Measurement record</span><code title="${measurementHash}">${displayHash(measurementHash)}</code></div>
    <div class="trace-row"><span>Result record</span><code title="${resultHash}">${displayHash(resultHash)}</code></div>
    <div class="trace-kind">${resultKind}</div>
    <p>SHA-256 over fictional browser payloads. This preview is not signed, WORM storage, physical provenance, or control validation.</p>`;
}

function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = `status ${kind}`;
}

function reset() {
  state = 'fresh';
  missing = -1;
  makeValues();
  renderWells();
  setStatus('Not committed', 'neutral');
  primaryEl.textContent = '0';
  baselineEl.textContent = '0';
  predictions('none');
  explainEl.textContent = 'Commit the layout before generating any fictional response values.';
  renderTrace('fresh');
}

document.querySelector('#commitBtn').onclick = () => {
  state = 'committed';
  missing = -1;
  renderWells();
  setStatus('Committed • identities locked', 'good');
  primaryEl.textContent = '0';
  baselineEl.textContent = '0';
  predictions('none');
  explainEl.textContent = 'The fictional 64-well plan is fixed before responses arrive.';
  renderTrace('committed');
};

document.querySelector('#missingBtn').onclick = () => {
  if (state === 'fresh') document.querySelector('#commitBtn').click();
  state = 'missing';
  missing = 17;
  renderWells();
  setStatus('Primary withheld • one required value missing', 'bad');
  primaryEl.textContent = '0';
  baselineEl.textContent = '0';
  predictions('none');
  explainEl.textContent = 'The bandwidth-0.7 model does not receive an imputed stand-in. Primary output count stays zero.';
  renderTrace('missing');
};

document.querySelector('#recoverBtn').onclick = () => {
  if (missing < 0) document.querySelector('#missingBtn').click();
  state = 'recovered';
  renderWells();
  setStatus('Baseline-only recovery • explicitly labelled', 'warn');
  primaryEl.textContent = '0';
  baselineEl.textContent = '23';
  predictions('baseline');
  explainEl.textContent = '23 historical own-drug estimates remain available. The affected head and all bandwidth-0.7 primary outputs remain withheld.';
  renderTrace('recovered');
};

document.querySelector('#completeBtn').onclick = () => {
  if (state === 'fresh') document.querySelector('#commitBtn').click();
  state = 'complete';
  missing = -1;
  renderWells();
  setStatus('Complete • 24 bandwidth-0.7 outputs recorded', 'good');
  primaryEl.textContent = '24';
  baselineEl.textContent = '0';
  predictions('primary');
  explainEl.textContent = 'Previously observed fictional readings are preserved; the missing reading is now present, so the complete current-model path can run.';
  renderTrace('complete');
};

document.querySelector('#resetBtn').onclick = reset;
reset();
