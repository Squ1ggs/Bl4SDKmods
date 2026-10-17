(function(){
  'use strict';
  var add = [

  ];
  function merge(){
    try{
      var ds = (window.STX_DATASET && Array.isArray(window.STX_DATASET.ALL_PARTS)) ? window.STX_DATASET.ALL_PARTS : null;
      if (!ds) { setTimeout(merge, 25); return; }
      var have = new Set();
      for (var i=0;i<ds.length;i++){
        var p = ds[i];
        var c = p && p.code ? String(p.code) : '';
        c = c.replace(/^\\"|\\"$/g,'').replace(/^"|"$/g,'').trim().toLowerCase();
        if (c) have.add(c);
      }
      for (var j=0;j<add.length;j++){
        var r = add[j];
        var rc = r && r.code ? String(r.code) : '';
        rc = rc.replace(/^\\"|\\"$/g,'').replace(/^"|"$/g,'').trim().toLowerCase();
        if (!rc || have.has(rc)) continue;
        ds.push(r);
        have.add(rc);
      }
      if (add.length){
        try{ window.GUN_PARTS = window.GRENADE_PARTS = window.SHIELD_PARTS = window.REPKIT_PARTS = window.ENHANCEMENT_PARTS = window.HEAVY_PARTS = window.CLASSMOD_PARTS = undefined; }catch(_e){}
        try{ if (typeof window.ensurePartPools === 'function') window.ensurePartPools(); }catch(_e){}
        try{ window.__ccStablePartRenderStateV1 = null; }catch(_e){}
      }
    }catch(_e){}
  }
  merge();
})();
