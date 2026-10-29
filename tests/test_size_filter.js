const assert = require('node:assert/strict');
const { range, matches, selected, format } = require('../app/static/size-filter.js');
const file = (size) => ({ id: size, size, kind: 'other', include: true });
let checks = 0;
function test(name, run) { run(); checks++; console.log('PASS ' + name); }
test('blank bounds include empty and unknown files', () => {
  const bounds = range('', '', 'MB');
  assert(matches(file(0), bounds));
  assert(matches({ kind: 'app' }, bounds));
});
test('inclusive MB boundaries', () => {
  const bounds = range('1', '2', 'MB');
  assert(!matches(file(999999), bounds));
  assert(matches(file(1000000), bounds));
  assert(matches(file(2000000), bounds));
  assert(!matches(file(2000001), bounds));
});
test('fractional GB and open maximum', () => {
  const bounds = range('0.5', '', 'GB');
  assert(!matches(file(499999999), bounds));
  assert(matches(file(500000000), bounds));
  assert(matches(file(2e9), bounds));
});
test('zero maximum selects empty files only', () => {
  const bounds = range('', '0', 'MB');
  assert(matches(file(0), bounds));
  assert(!matches(file(1), bounds));
});
test('invalid ranges select nothing', () => {
  for (const [min, max] of [['-1', ''], ['4', '2'], ['abc', ''], ['', 'Infinity'], ['1e309', '']]) {
    const bounds = range(min, max, 'MB');
    assert(!bounds.valid);
    assert(!matches(file(0), bounds));
  }
});
test('unknown app bundle sizes excluded with active bounds', () => {
  assert(!matches({ kind: 'app', size: 0 }, range('0', '', 'MB')));
});
test('sort selections exclude hidden files and retain checkbox choices on clear', () => {
  const original = file(2e6);
  assert(!selected(original, {}, range('', '1', 'MB')).include);
  assert(selected(original, {}, range('', '', 'MB')).include);
  assert(!selected(original, { include: false }, range('', '', 'MB')).include);
  assert.equal(original.include, true);
  const items = [file(1e6), file(2e6), file(3e6)].map(i => selected(i, {}, range('2', '2', 'MB')));
  assert.deepEqual(items.filter(i => i.include).map(i => i.id), [2e6]);
});
test('readable byte sizes', () => {
  assert.equal(format(file(0)), '0 B');
  assert.equal(format(file(1500000)), '1.5 MB');
  assert.equal(format(file(2e9)), '2 GB');
  assert.equal(format({ kind: 'app', size: 0 }), 'Size unknown');
});
console.log(`${checks} size filter tests passed`);
