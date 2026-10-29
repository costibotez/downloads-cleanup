# Roadmap implementation plan

1. Add conservative PDF names from document type, labelled issuer and validated date; keep meaningful names and respect Rename by content.
2. Add an opt-in year/month setting. Preview the complete path, retain category editing, validate nested paths, and undo nested moves.
3. Add opt-in watch mode while the local server runs. Establish a baseline on enable/start/folder change; process only new files after two minutes of stability. Pause during manual previews. Record automatic sorts in history; pause watching on undo. Never automatically trash files.
4. Verify with temporary-file tests for naming, dates, destination traversal/symlinks, collisions, undo, watch baseline/stability and failures. Run syntax checks and update user documentation.

## Completed

All three features are implemented. Validation: 18 Python tests passed, JavaScript syntax and diff checks passed, Swift helper compiled (existing AVFoundation deprecation warnings only), and an isolated HTTP smoke check verified settings controls, authenticated configuration save and state readback. Tests used temporary folders; no personal downloads or saved user settings were changed. Watch mode and year/month folders default to off. A full interactive browser check and a real incoming-download session remain manual checks.

## File-size filtering

1. Add optional minimum/maximum size bounds with MB/GB units and a Clear action to manual scan previews. Bounds are inclusive; blank fields are unbounded. Reject negative, invalid, or reversed ranges.
2. Apply one consistent filter to folder counts, the file pile, review rows, and submitted sort selections. Keep checkbox choices when clearing/changing the filter. Files outside the range remain in place. Watch mode remains independent.
3. Display readable file sizes in review rows. App bundle sizes are not measured by the scanner, so show them as unknown and exclude them only while a size bound is active.
4. Test boundaries, units, empty files, invalid ranges, unknown sizes, and filtering of sort selections. Update README usage instructions.

File-size filtering is implemented. Eight JavaScript tests passed covering inclusive boundaries, decimal MB/GB, fractional sizes, empty files, invalid ranges, unknown bundle sizes, preserved checkbox choices and sort selection. All 18 Python regression tests, JavaScript syntax and diff checks also passed. No personal files were moved during validation.

## Bulk Move to Trash

Implemented separate Trash selection in eligible preview rows, Select all for Trash within the current size-filtered folder, and one confirmation with count and total size. Every eligible row is displayed so bulk selection does not silently target omitted rows. Sorting inclusion remains independent. Batch requests reuse each file's eligibility, path and snapshot checks, deduplicate IDs, and return successful IDs plus per-file failures. Failed files remain in the preview; successful ones are recoverable through Finder's Trash.

Validation: 24 Python tests passed, including six new batch cases; all eight size-filter tests passed; a Node DOM harness checked bulk-selection controls, filtered select-all, count/size, cancellation, request contents and refresh. JavaScript syntax and diff checks passed. Finder operations were mocked; no personal files were moved. Native Finder interaction remains a manual check.
