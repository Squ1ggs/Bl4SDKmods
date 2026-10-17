(function () {
  'use strict';
  function titleFromAugCode(code) {
    var c = String(code || '').replace(/^"+|"+$/g, '').toLowerCase();
    var m = c.match(/repair_kit\.part_aug_[a-z]_([a-z0-9_]+)/);
    if (!m) return '';
    return m[1].split('_').filter(Boolean).map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  }
  function patchRepkitPlaceholders() {
    var ds = window.STX_DATASET;
    var rows = ds && Array.isArray(ds.ALL_PARTS) ? ds.ALL_PARTS : null;
    if (!rows) return;
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (!row || String(row.category || '') !== 'Repkit') continue;
      if (String(row.name || '').trim().toUpperCase() !== 'PLACEHOLDER') continue;
      var title = titleFromAugCode(row.code);
      if (title) row.name = title;
      if (String(row.stats || '').trim().toUpperCase() === 'PLACEHOLDER') {
        row.stats = String(row.effects || 'No Stat Changes');
      }
    }
  }
  if (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)) {
    patchRepkitPlaceholders();
  } else {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(patchRepkitPlaceholders, 0);
    });
  }
})();
