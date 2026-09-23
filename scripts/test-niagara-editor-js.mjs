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
  // string or template literal. Fine for the current 5 target functions
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

const functionNames = ['apiErrorText', 'pxWidgetFromForm', 'wireSheetConfigFieldFor', 'wireSheetBlockFromForm', 'wireSheetLinkFromForm'];
const extracted = functionNames.map((name) => extractFunction(scriptSource, name)).join('\n\n');

const sandbox = new Function(
  extracted + '\nreturn {apiErrorText, pxWidgetFromForm, wireSheetConfigFieldFor, wireSheetBlockFromForm, wireSheetLinkFromForm};'
);
const { apiErrorText, pxWidgetFromForm, wireSheetConfigFieldFor, wireSheetBlockFromForm, wireSheetLinkFromForm } = sandbox();

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

if (failures > 0) {
  console.error(failures + ' assertion(s) failed');
  process.exit(1);
}
console.log('niagara editor JS self-test passed');
