const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const SizeFilter = require('../app/static/size-filter.js');
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.listeners = {}; this.disabled = false; this.style = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
    this.validity = { valid: true }; this.value = ''; this.checked = false;
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
  remove() {}
}
const ids = new Map();
const all = [];
const document = {
  getElementById(id) { if (!ids.has(id)) ids.set(id, new Element('div')); return ids.get(id); },
  createElement(tag) { const node = new Element(tag); all.push(node); return node; },
  querySelectorAll() { return all.filter(n => ['button', 'input', 'select'].includes(n.tag)); },
};
const context = vm.createContext({ document, SizeFilter, console, confirm: () => false, alert: () => {} });
let source = fs.readFileSync('app/static/app.js', 'utf8');
source = source.slice(0, source.indexOf('\nfunction ruleRow'));
vm.runInContext(source, context);
vm.runInContext(`
renderFolders = () => {}; renderPile = () => {}; setPhaseUI = () => {};
refresh = async () => S;
let requests = [];
api = async (path, body) => {
  requests.push({path, body});
  S.plan = S.plan.filter(i => !body.ids.includes(i.id));
  return { trashed: body.ids.length, trashedIds: body.ids, errors: [] };
};
S = { config: {rules: []}, categories: [['Duplicates', 'Everything else']], phase: 'ready', plan: [
  {id: 1, name:'a.txt', category:'Duplicates', size: 1000000, include: true, trashable:true},
  {id: 2, name:'b.txt', category:'Duplicates', size: 2000000, include: false, trashable:true},
  {id: 3, name:'c.txt', category:'Duplicates', size: 5000000, include: true, trashable:true},
  {id: 4, name:'safe.txt', category:'Duplicates', size: 1000000, include: true, trashable:false}
] };
`, context);
document.getElementById('sizeMax').value = '2';
document.getElementById('sizeUnit').value = 'MB';
vm.runInContext("openFolder('Duplicates')", context);
const toolbar = document.getElementById('drawerList').children[0];
const selectAll = toolbar.children[0].children[0];
const summary = toolbar.children[1];
const submit = toolbar.children[2];
(async () => {
  assert(submit.disabled, 'no selection initially');
  selectAll.checked = true;
  selectAll.listeners.change();
  assert.equal(summary.textContent, '2 selected · 3 MB');
  assert.equal(submit.disabled, false);
  assert.equal(vm.runInContext('S.plan[1].include', context), false, 'sorting choice remains unchanged');
  await submit.listeners.click();
  assert.equal(vm.runInContext('requests.length', context), 0, 'cancellation sends nothing');
  selectAll.checked = false;
  selectAll.listeners.change();
  assert(submit.disabled, 'deselect all');
  const choice = all.find(n => n['aria-label'] === 'Select a.txt for Trash');
  choice.checked = true;
  choice.listeners.change();
  assert.equal(selectAll.indeterminate, true);
  context.confirm = () => true;
  await submit.listeners.click();
  assert.equal(vm.runInContext('JSON.stringify(requests[0].body.ids)', context), '[1]');
  assert.equal(vm.runInContext('JSON.stringify(S.plan.map(i=>i.id))', context), '[2,3,4]');
  assert.equal(vm.runInContext('trashing', context), false);
  console.log('Bulk Trash UI checks passed: independent selection, filtered select-all, deselect, count/size, cancellation, submission and refresh.');
})().catch(e => { console.error(e); process.exitCode = 1; });
