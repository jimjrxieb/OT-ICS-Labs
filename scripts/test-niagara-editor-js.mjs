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
  // string or template literal. Fine for the current 3 target functions
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

const functionNames = ['pxWidgetFromForm', 'wireSheetBlockFromForm', 'wireSheetLinkFromForm'];
const extracted = functionNames.map((name) => extractFunction(scriptSource, name)).join('\n\n');

const sandbox = new Function(
  extracted + '\nreturn {pxWidgetFromForm, wireSheetBlockFromForm, wireSheetLinkFromForm};'
);
const { pxWidgetFromForm, wireSheetBlockFromForm, wireSheetLinkFromForm } = sandbox();

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

check(
  'wireSheetLinkFromForm builds a link with from/to/slot fields',
  wireSheetLinkFromForm({ from_block: 'A', from_slot: 'out', to_block: 'B', to_slot: 'a' }),
  { from: 'A', from_slot: 'out', to: 'B', to_slot: 'a' }
);

if (failures > 0) {
  console.error(failures + ' assertion(s) failed');
  process.exit(1);
}
console.log('niagara editor JS self-test passed');
