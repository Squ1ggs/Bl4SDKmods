(function(){
  'use strict';
  /**
   * Spawn-code → player-facing display name overrides.
   * Prefer correcting generated extract/supplement names here when the in-game
   * legendary title differs from the internal inv slug (e.g. dahlfather → Heimdahl).
   */
  var MAP = {
    'tor_hw.comp_05_legendary_dahlfather': 'Heimdahl',
    'tor_hw.part_barrel_dahlfather': 'Heimdahl',
    'tor_hw.comp_05_legendary_loiter': 'Loiter Sploiter',
    'tor_hw.part_barrel_loiter': 'Loiter Sploiter',
    'tor_hw.comp_05_legendary_javelin': 'Sprezzatura',
    'tor_hw.part_barrel_javelin': 'Sprezzatura',
    'tor_hw.comp_05_legendary_ravenfire': 'Ravenfire',
    'tor_hw.part_unique_barrel_02_ravenfire': 'Ravenfire',
    'tor_hw.comp_05_legendary_sidewinder': 'Sidewinder',
    'tor_hw.part_unique_barrel_01_sidewinder': 'Sidewinder',
    'bor_hw.comp_05_legendary_draupner': 'Draupner',
    'bor_hw.part_barrel_02_draupner': 'Draupner',
    'bor_hw.comp_05_legendary_discjockey': 'Disc Jockey',
    'bor_hw.part_barrel_02_discjockey': 'Disc Jockey',
    'bor_hw.comp_05_legendary_jetset': 'Jetsetter',
    'bor_hw.part_barrel_02_jetset': 'Jetsetter',
    'bor_hw.comp_05_legendary_streamer': 'Streamer',
    'bor_hw.part_barrel_01_streamer': 'Streamer',
    'mal_hw.comp_05_legendary_barrel': 'Cooper Duper',
    'mal_hw.part_barrel_02_barrel': 'Cooper Duper',
    'mal_hw.comp_05_legendary_ichor': 'Ichor',
    'mal_hw.part_barrel_01_ichor': 'Ichor',
    'mal_hw.comp_05_legendary_bottledlightning': 'Bottled Lightning',
    'mal_hw.part_barrel_02_bottledlightning': 'Bottled Lightning',
    'mal_hw.comp_05_legendary_gammavoid': 'Gamma Void',
    'mal_hw.part_barrel_02_gammavoid': 'Gamma Void',
    'vla_hw.comp_05_legendary_flak': 'Flak Cannon',
    'vla_hw.part_barrel_02_flak': 'Flak Cannon',
    'vla_hw.comp_05_legendary_quattro': 'Quadratus',
    'vla_hw.part_barrel_02_quattro': 'Quadratus',
    'vla_hw.comp_05_legendary_atlinggun': 'Atling Gun',
    'vla_hw.part_unique_barrel_01_atlinggun': 'Atling Gun',
    'vla_hw.comp_05_legendary_splatoon': 'Inkling',
    'vla_hw.part_barrel_02_splatoon': 'Inkling'
  };
  function normSpawn(code){
    return String(code||'').replace(/^\\"|\\"$/g,'').replace(/^"|"$/g,'').trim().toLowerCase();
  }
  function applyPartDisplayOverrides(){
    var ds = window.STX_DATASET && window.STX_DATASET.ALL_PARTS;
    if (!ds || !ds.length) return 0;
    var n = 0;
    for (var i = 0; i < ds.length; i++){
      var p = ds[i];
      if (!p) continue;
      var key = normSpawn(p.code || p.spawnCode || '');
      var want = MAP[key];
      if (!want) continue;
      if (String(p.name || '').trim() !== want){
        p.name = want;
        n++;
      }
      if (!String(p.effects || '').trim() || /^(legendary|part|barrel)\b/i.test(String(p.effects || ''))){
        p.effects = want;
      }
      if (!String(p.legendaryName || '').trim()) p.legendaryName = want;
    }
    return n;
  }
  window.__STX_PART_DISPLAY_OVERRIDES = MAP;
  window.applyPartDisplayOverrides = applyPartDisplayOverrides;
  function tryApply(){
    try{
      if (applyPartDisplayOverrides()) {
        try{ if (typeof window.ensurePartPools === 'function') window.ensurePartPools(); }catch(_e){}
        try{ window.__ccStablePartRenderStateV1 = null; }catch(_e){}
      }
    }catch(_e){}
  }
  tryApply();
  try{ window.addEventListener('stx:dataset-growth', tryApply); }catch(_e){}
  try{ setTimeout(tryApply, 50); setTimeout(tryApply, 250); setTimeout(tryApply, 1000); }catch(_e){}
})();
