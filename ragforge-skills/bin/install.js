#!/usr/bin/env node

'use strict';

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const SKILLS = [
  'rag-workflow',
  'rag-ingestion',
  'rag-retrieval',
  'rag-eval',
  'rag-observe',
];

const PKG_ROOT = path.join(__dirname, '..');
const DEST_DIR = path.join(os.homedir(), '.claude', 'skills');

function run() {
  fs.mkdirSync(DEST_DIR, { recursive: true });

  const results = { installed: [], skipped: [] };

  for (const skill of SKILLS) {
    const src  = path.join(PKG_ROOT, skill);
    const dest = path.join(DEST_DIR, skill);

    if (!fs.existsSync(src)) {
      results.skipped.push(skill);
      continue;
    }

    fs.cpSync(src, dest, { recursive: true, force: true });
    results.installed.push(skill);
  }

  console.log('\nRAG Skills installed\n');
  for (const s of results.installed) {
    console.log(`  + ${s}`);
  }
  if (results.skipped.length) {
    console.log('\n  skipped (not found in package):');
    for (const s of results.skipped) console.log(`  - ${s}`);
  }

  console.log(`\nLocation : ${DEST_DIR}`);
  console.log('Next     : restart Claude Code, then invoke skills with /rag-workflow, /rag-ingestion, etc.');
  console.log('Docs     : https://github.com/Devank-Garg/ragforge/tree/main/ragforge-skills\n');
}

run();
