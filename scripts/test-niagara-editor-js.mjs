#!/usr/bin/env node
// Extracts pure editor-form functions from frontend/static/niagara.html and
// asserts their behavior against realistic form-value shapes, with no
// browser/DOM dependency -- matching this repo's "no pytest, real
// assertions" convention (see docs/superpowers/specs/
// synchrony-style-operator-ui-design.md §10).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HTML_PATH = path.join(__dirname, '..', 'frontend', 'static', 'niagara.html');

function extractFunction(source, name) {
  // Naive brace counter: no guard against '{'/'}' occurring inside a
  // string or template literal. Fine for the current 7 target functions
  // (no such literals in their bodies) -- revisit if reused on functions
  // that contain brace characters inside strings/templates.
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  if (start === -1) {
    throw new Error('function ' + name + ' not found in ' + HTML_PATH);
  }
  let depth = 0;
  for (let i = start; i < source.length; i++) {
    if (source[i] === '{') {
      depth++;
    } else if (source[i] === '}') {
      depth--;
      if (depth === 0) {
        return source.slice(start, i + 1);
      }
    }
  }
  throw new Error('unbalanced braces extracting ' + name);
}

const html = readFileSync(HTML_PATH, 'utf-8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
  throw new Error('no <script> block found in ' + HTML_PATH);
}
const scriptSource = scriptMatch[1];

const functionNames = ['apiErrorText', 'backupOptionLabel', 'writeStatusLabel', 'pxWidgetFromForm', 'wireSheetConfigFieldFor', 'wireSheetBlockFromForm', 'wireSheetLinkFromForm'];
const extracted = functionNames.map((name) => extractFunction(scriptSource, name)).join('\n\n');

const sandbox = new Function(
  extracted + '\nreturn {apiErrorText, backupOptionLabel, writeStatusLabel, pxWidgetFromForm, wireSheetConfigFieldFor, wireSheetBlockFromForm, wireSheetLinkFromForm};'
);
const { apiErrorText, backupOptionLabel, writeStatusLabel, pxWidgetFromForm, wireSheetConfigFieldFor, wireSheetBlockFromForm, wireSheetLinkFromForm } = sandbox();

let failures = 0;

function check(label, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    console.error('FAIL: ' + label + '\n  got:      ' + a + '\n  expected: ' + e);
    failures++;
  } else {
    console.log('ok: ' + label);
  }
}

check(
  'pxWidgetFromForm builds a widget with parsed coordinates',
  pxWidgetFromForm({ widget_id: 'w1', kind: 'value', point: 'RTU1_SAT', label: 'SAT', x: '120', y: '45' }),
  { widget_id: 'w1', kind: 'value', point: 'RTU1_SAT', label: 'SAT', x: 120, y: 45 }
);

check(
  'wireSheetBlockFromForm builds a block with empty config and parsed coordinates',
  wireSheetBlockFromForm({ block_id: 'B1', type: 'Not', x: '10', y: '20' }),
  { block_id: 'B1', type: 'Not', config: {}, x: 10, y: 20 }
);

// Layer 1.5: config is built from the per-type config inputs, and inputs
// that don't belong to the chosen type are ignored.
const allConfigInputs = { config_value: '55', config_point: 'RTU1_SAT', config_schedule: 'OFFICE_OCCUPANCY', config_op: '<=' };

check(
  'wireSheetBlockFromForm: Constant parses a numeric value',
  wireSheetBlockFromForm({ block_id: 'C1', type: 'Constant', x: '0', y: '0', ...allConfigInputs }),
  { block_id: 'C1', type: 'Constant', config: { value: 55 }, x: 0, y: 0 }
);

check(
  'wireSheetBlockFromForm: Constant parses negative decimals',
  wireSheetBlockFromForm({ block_id: 'C1', type: 'Constant', x: '0', y: '0', config_value: ' -0.01 ' }).config,
  { value: -0.01 }
);

check(
  'wireSheetBlockFromForm: Constant parses true/false as booleans',
  [wireSheetBlockFromForm({ block_id: 'C1', type: 'Constant', x: '0', y: '0', config_value: 'true' }).config,
   wireSheetBlockFromForm({ block_id: 'C1', type: 'Constant', x: '0', y: '0', config_value: 'FALSE' }).config],
  [{ value: true }, { value: false }]
);

check(
  'wireSheetBlockFromForm: Constant passes non-numeric text through for the server to reject by name',
  wireSheetBlockFromForm({ block_id: 'C1', type: 'Constant', x: '0', y: '0', config_value: 'abc' }).config,
  { value: 'abc' }
);

check(
  'wireSheetBlockFromForm: Constant with a blank value omits the key (server reports it missing)',
  wireSheetBlockFromForm({ block_id: 'C1', type: 'Constant', x: '0', y: '0', config_value: '  ' }).config,
  {}
);

check(
  'wireSheetBlockFromForm: PointRef takes the selected point',
  wireSheetBlockFromForm({ block_id: 'P1', type: 'PointRef', x: '0', y: '0', ...allConfigInputs }).config,
  { point: 'RTU1_SAT' }
);

check(
  'wireSheetBlockFromForm: PointWriteRef takes the selected point',
  wireSheetBlockFromForm({ block_id: 'W1', type: 'PointWriteRef', x: '0', y: '0', ...allConfigInputs }).config,
  { point: 'RTU1_SAT' }
);

check(
  'wireSheetBlockFromForm: ScheduleRef takes the selected schedule',
  wireSheetBlockFromForm({ block_id: 'S1', type: 'ScheduleRef', x: '0', y: '0', ...allConfigInputs }).config,
  { schedule_id: 'OFFICE_OCCUPANCY' }
);

check(
  'wireSheetBlockFromForm: Compare takes the selected operator',
  wireSheetBlockFromForm({ block_id: 'CMP', type: 'Compare', x: '0', y: '0', ...allConfigInputs }).config,
  { op: '<=' }
);

check(
  'wireSheetBlockFromForm: config-less types ignore stray config inputs',
  wireSheetBlockFromForm({ block_id: 'N1', type: 'Not', x: '0', y: '0', ...allConfigInputs }).config,
  {}
);

check(
  'wireSheetConfigFieldFor names the one config input each type shows',
  ['Constant', 'PointRef', 'PointWriteRef', 'ScheduleRef', 'Compare', 'Select', 'And'].map(wireSheetConfigFieldFor),
  ['value', 'point', 'point', 'schedule', 'op', null, null]
);

check(
  'wireSheetLinkFromForm builds a link with from/to/slot fields',
  wireSheetLinkFromForm({ from_block: 'A', from_slot: 'out', to_block: 'B', to_slot: 'a' }),
  { from: 'A', from_slot: 'out', to: 'B', to_slot: 'a' }
);

check(
  'apiErrorText joins validation errors, shows string details bare, falls back to JSON',
  [apiErrorText({ errors: ['a bad', 'b bad'] }),
   apiErrorText("Role 'viewer' is not authorized"),
   apiErrorText([{ loc: ['body'], msg: 'field required' }]),
   apiErrorText(undefined)],
  ['a bad; b bad', "Role 'viewer' is not authorized", '[{"loc":["body"],"msg":"field required"}]', 'request failed']
);

check(
  'backupOptionLabel shows UTC time, kind, and operator',
  backupOptionLabel({ backup_dir: 'data/output/platform-backups/x.dist', timestamp: '2026-09-23T16:16:15.787022+00:00',
                      kind: 'wiresheet-editor', operator_id: 'eng-workbench' }),
  '2026-09-23 16:16:15Z · wiresheet-editor · eng-workbench'
);

check(
  'backupOptionLabel tolerates rows without kind/operator (older platform entries)',
  backupOptionLabel({ backup_dir: 'd', timestamp: '2026-09-23T01:02:03+00:00' }),
  '2026-09-23 01:02:03Z · backup · unknown'
);

check(
  'writeStatusLabel describes each PointWriteRef state',
  [writeStatusLabel({ state: 'writing', point: 'VAV301_TEMP_SP', value: 72 }),
   writeStatusLabel({ state: 'released_null', point: 'VAV301_TEMP_SP' }),
   writeStatusLabel({ state: 'shadowed_by_override', point: 'VAV301_TEMP_SP' }),
   writeStatusLabel({ state: 'released_fault', point: 'VAV301_TEMP_SP' }),
   writeStatusLabel(null)],
  ['writing 72 -> VAV301_TEMP_SP',
   'null: released VAV301_TEMP_SP',
   'shadowed: operator override on VAV301_TEMP_SP',
   'FAULT: write to VAV301_TEMP_SP released',
   '']
);

// --- Px page rendering: every SVG size is non-negative and the duct fits ----

const { renderPxSvg } = new Function(
  extractFunction(scriptSource, 'renderPxSvg') + '\n\n' + extractFunction(scriptSource, 'renderPxWidget') +
  '\nreturn {renderPxSvg};'
)();

function pxSvgGeometry(svg) {
  const [, , vbW, vbH] = svg.match(/viewBox="([^"]+)"/)[1].split(' ').map(Number);
  const duct = svg.match(/<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"/).slice(1).map(Number);
  const widths = [...svg.matchAll(/width="(-?[\d.]+)"/g)].map((m) => Number(m[1]));
  return { vbW, vbH, duct, widths };
}

for (const [label, widgets] of [
  ['empty page', []],
  ['one widget above the duct', [{ widget_id: 'w1', kind: 'value', point: 'RTU1_SAT', label: 'SAT', x: 100, y: 40, value: 55 }]],
  ['widget far right and below the duct', [{ widget_id: 'w2', kind: 'gauge', point: 'RTU1_DMPR', label: 'Damper', x: 600, y: 300, value: 40 }]],
]) {
  const g = pxSvgGeometry(renderPxSvg({ widgets }));
  const [x, y, w, h] = g.duct;
  check(
    'renderPxSvg (' + label + '): no negative widths, duct inside the viewBox',
    { negative: g.widths.filter((v) => v < 0), ductFits: x >= 0 && y >= 0 && x + w <= g.vbW && y + h <= g.vbH },
    { negative: [], ductFits: true }
  );
}

// --- Px page selection: a slower, older response never replaces a newer one --

function pxLoadHarness() {
  const pending = {};
  const els = { 'px-select': { value: '' }, 'px-canvas': { innerHTML: '' } };
  const fakeFetch = (url) => new Promise((resolve, reject) => { pending[url] = { resolve, reject }; });
  const fakeDocument = { getElementById: (id) => els[id] };
  const { loadPxPage } = new Function(
    'fetch', 'document', 'renderPxSvg', 'refreshEditorBackups',
    // extractFunction starts at 'function', so restore the async keyword.
    'let pxLoadSeq = 0;\nasync ' + extractFunction(scriptSource, 'loadPxPage') + '\nreturn {loadPxPage};'
  )(fakeFetch, fakeDocument, (page) => 'svg:' + page.px_id, async () => {});
  const respond = (id) => pending['/api/px/' + id].resolve({ ok: true, json: async () => ({ px_id: id, widgets: [] }) });
  const fail = (id) => pending['/api/px/' + id].reject(new Error('network down'));
  return { els, loadPxPage, respond, fail };
}

{
  const h = pxLoadHarness();
  const first = h.loadPxPage('RTU1_SCHEMATIC');   // initial load, slow
  const second = h.loadPxPage('CODEX_PX_CHECK');  // user picks another page meanwhile
  h.respond('CODEX_PX_CHECK');
  await second;
  h.respond('RTU1_SCHEMATIC');                    // the stale response lands last
  await first;
  check('loadPxPage: a stale response does not override the newer selection',
        [h.els['px-select'].value, h.els['px-canvas'].innerHTML],
        ['CODEX_PX_CHECK', 'svg:CODEX_PX_CHECK']);
}

{
  const h = pxLoadHarness();
  const first = h.loadPxPage('RTU1_SCHEMATIC');
  const second = h.loadPxPage('CODEX_PX_CHECK');
  h.respond('CODEX_PX_CHECK');
  await second;
  h.fail('RTU1_SCHEMATIC');                       // the stale request errors last
  await first;
  check('loadPxPage: a stale request error does not replace the newer page',
        h.els['px-canvas'].innerHTML, 'svg:CODEX_PX_CHECK');
}

{
  const h = pxLoadHarness();
  const only = h.loadPxPage('RTU1_SCHEMATIC');
  h.respond('RTU1_SCHEMATIC');
  await only;
  check('loadPxPage: a single load still renders its page',
        [h.els['px-select'].value, h.els['px-canvas'].innerHTML],
        ['RTU1_SCHEMATIC', 'svg:RTU1_SCHEMATIC']);
}

if (failures > 0) {
  console.error(failures + ' assertion(s) failed');
  process.exit(1);
}
console.log('niagara editor JS self-test passed');
