/* Shared size semantics for previews and sort selection. Decimal units match Finder. */
(function (root) {
  function range(minText, maxText, unit) {
    const multiplier = unit === 'GB' ? 1e9 : 1e6;
    const min = minText.trim() === '' ? 0 : Number(minText);
    const max = maxText.trim() === '' ? Infinity : Number(maxText);
    const active = minText.trim() !== '' || maxText.trim() !== '';
    const valid = Number.isFinite(min) && min >= 0 &&
      (maxText.trim() === '' || Number.isFinite(max)) && max >= 0 && min <= max &&
      Number.isFinite(min * multiplier) && (max === Infinity || Number.isFinite(max * multiplier));
    return { min: min * multiplier, max: max * multiplier, active, valid };
  }
  function matches(item, bounds) {
    if (!bounds.valid) return false;
    if (!bounds.active) return true;
    if (item.kind === 'app' || !Number.isFinite(item.size)) return false;
    return item.size >= bounds.min && item.size <= bounds.max;
  }
  function selected(item, override, bounds) {
    const result = { ...item, ...override };
    result.include = Boolean(result.include) && matches(item, bounds);
    return result;
  }
  function format(item) {
    if (item.kind === 'app' || !Number.isFinite(item.size)) return 'Size unknown';
    if (item.size < 1000) return `${item.size} B`;
    const unit = item.size >= 1e9 ? 'GB' : item.size >= 1e6 ? 'MB' : 'KB';
    return `${(item.size / ({ KB: 1e3, MB: 1e6, GB: 1e9 }[unit])).toLocaleString('en-US', { maximumFractionDigits: 2 })} ${unit}`;
  }
  const api = { range, matches, selected, format };
  if (typeof module !== 'undefined') module.exports = api;
  else root.SizeFilter = api;
})(globalThis);
