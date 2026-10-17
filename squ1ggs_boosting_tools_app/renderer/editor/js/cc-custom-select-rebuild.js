/**
 * cc-custom-select-rebuild.js
 * Replaces native select dropdowns with custom-styled ones so the options list
 * has a dark background (native select options are often white and unstyled).
 */
(function () {
  'use strict';

  function byId(id) { return document.getElementById(id); }

  var DROPDOWN_BG = 'linear-gradient(135deg, rgba(8, 24, 38, 1) 0%, rgba(20, 12, 34, 1) 100%)';
  var DROPDOWN_HOVER = 'linear-gradient(135deg, rgba(14, 40, 58, 1) 0%, rgba(28, 16, 44, 1) 100%)';
  var LIST_CHUNK_THRESHOLD = 18;
  var LIST_CHUNK_SIZE = 16;
  var BUILDER_SELECT_IDS = ['stx_itemType', 'stx_manufacturer', 'weaponType', 'rarity', 'mainPart'];
  var GUIDED_SLOT_SELECT_IDS = [
    'ccRaritySelect', 'ccBodySelect', 'ccBarrelSelect', 'ccMagazineSelect',
    'ccGrenadeRaritySelect', 'ccRepkitRaritySelect', 'ccEnhancementRaritySelect',
    'ccGadgetRaritySelect', 'ccHeavyRaritySelect', 'cmRaritySelect'
  ];
  var LARGE_SKIN_SELECT_IDS = [
    'toolsSkinSelect', 'toolsCamoSelect',
    'ccGuidedSkinSelect', 'ccGuidedCamoSelect',
    'skinSelect', 'camoSelect'
  ];
  var iconWarmCache = Object.create(null);

  function isGuidedSlotGridSelect(sel) {
    try {
      return !!(sel && sel.closest && sel.closest('#rebuildGuidedBuilderSection .cc-guided-slots-grid'));
    } catch (_) {
      return false;
    }
  }

  function isBuilderSelect(sel) {
    if (isGuidedSlotGridSelect(sel)) return true;
    var id = sel && sel.id ? String(sel.id) : '';
    for (var i = 0; i < BUILDER_SELECT_IDS.length; i++) {
      if (BUILDER_SELECT_IDS[i] === id) return true;
    }
    for (var j = 0; j < GUIDED_SLOT_SELECT_IDS.length; j++) {
      if (GUIDED_SLOT_SELECT_IDS[j] === id) return true;
    }
    for (var k = 0; k < LARGE_SKIN_SELECT_IDS.length; k++) {
      if (LARGE_SKIN_SELECT_IDS[k] === id) return true;
    }
    return false;
  }

  function countSelectOptions(sel) {
    var n = 0;
    var ch = sel && sel.children ? sel.children : [];
    for (var i = 0; i < ch.length; i++) {
      if (ch[i].tagName === 'OPTION') n++;
      else if (ch[i].tagName === 'OPTGROUP' && ch[i].querySelectorAll) {
        n += ch[i].querySelectorAll('option').length;
      }
    }
    return n;
  }

  /** Builder dropdowns prebuild synchronously up to 96 opts; large lists chunk via rAF while open. */
  function getListBuildPolicy(sel, optionCount) {
    if (isBuilderSelect(sel)) {
      if (optionCount <= 96) return { sync: true, threshold: 96, chunkSize: 48, useRaf: true };
      return { sync: false, threshold: 96, chunkSize: 48, useRaf: true };
    }
    if (isLiteUi() || touchSelectUi()) {
      if (optionCount <= 36) return { sync: true, threshold: 36, chunkSize: 32, useRaf: true };
      return { sync: false, threshold: 36, chunkSize: 32, useRaf: true };
    }
    return { sync: optionCount <= LIST_CHUNK_THRESHOLD, threshold: LIST_CHUNK_THRESHOLD, chunkSize: LIST_CHUNK_SIZE, useRaf: false };
  }

  function isLiteUi() {
    try {
      if (typeof window.stxIsLiteUi === 'function' && window.stxIsLiteUi()) return true;
    } catch (_) {}
    return document.documentElement.classList.contains('stx-lite-ui');
  }

  function touchSelectUi() {
    try {
      if (typeof window.stxIsTouchUi === 'function') return window.stxIsTouchUi();
    } catch (_) {}
    return document.documentElement.classList.contains('stx-touch-ui');
  }

  function selectHostNeedsTopStack(sel) {
    try {
      if (!sel || !sel.closest) return false;
      return !!(
        sel.closest('#rp-saveyaml-drawer') ||
        sel.closest('#ccMissionsEditor') ||
        sel.closest('#ccExtraYamlEditors')
      );
    } catch (_) {
      return false;
    }
  }

  function floatingListZIndex(sel) {
    // Drawer/tab use ~2147483645; default float (2147483001) opens under them and looks "dead".
    return selectHostNeedsTopStack(sel) ? '2147483647' : '2147483001';
  }

  function floatingBackdropZIndex(sel) {
    return selectHostNeedsTopStack(sel) ? '2147483646' : '2147482000';
  }

  function ensureSelectBackdrop() {
    var bd = document.getElementById('stxSelectBackdrop');
    if (!bd) {
      bd = document.createElement('div');
      bd.id = 'stxSelectBackdrop';
      bd.setAttribute('aria-hidden', 'true');
      bd.style.cssText = 'position:fixed;inset:0;z-index:2147482000;background:transparent;touch-action:none;display:none;';
      document.body.appendChild(bd);
    }
    bd.style.display = 'block';
    return bd;
  }

  function hideSelectBackdrop(delayMs) {
    var bd = document.getElementById('stxSelectBackdrop');
    if (!bd) return;
    var ms = Number(delayMs) || 0;
    window.setTimeout(function () {
      if (bd && !document.querySelector('.custom-select-wrapper.is-open')) {
        bd.style.display = 'none';
        bd.style.pointerEvents = 'none';
      }
    }, ms);
  }

  function closeOtherOpenCustomSelects(exceptWrapper) {
    var nodes = document.querySelectorAll('.custom-select-wrapper.is-open');
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i] === exceptWrapper) continue;
      var fn = nodes[i].__ccFinishClose;
      if (typeof fn === 'function') {
        try { fn(); } catch (_) {}
      }
    }
  }

  function backdropClosesDropdown(ev, finishClose) {
    if (typeof finishClose !== 'function') return;
    var guard = window.__stxCustomSelectOpenGuardUntil || 0;
    if (guard && Date.now() < guard) {
      if (ev) {
        try { ev.preventDefault(); ev.stopPropagation(); } catch (_) {}
      }
      return;
    }
    finishClose();
  }

  function warmIconSrc(src) {
    src = String(src || '').trim();
    if (!src) return;
    if (iconWarmCache[src] === 1) return;
    if (iconWarmCache[src] === 'pending') return;
    iconWarmCache[src] = 'pending';
    var im = new Image();
    im.decoding = 'async';
    im.onload = im.onerror = function () { iconWarmCache[src] = 1; };
    im.src = src;
  }

  function assignIconSrc(im, src) {
    src = String(src || '').trim();
    if (!im || !src) return;
    if (iconWarmCache[src] === 1) {
      im.src = src;
      return;
    }
    warmIconSrc(src);
    im.src = src;
  }

  function shouldSkipEarlyWrap(sel) {
    return isGuidedSlotGridSelect(sel);
  }

  function shouldUseNativeSelect(sel) {
    if (!sel) return true;
    if (String(sel.getAttribute('data-native-select') || '').trim().toLowerCase() === 'yes') return true;
    try {
      // Mission / YAML editor lists are long and live in a top-layer drawer — keep OS native.
      if (sel.closest && sel.closest('#ccMissionsEditor, #ccExtraYamlEditors')) return true;
    } catch (_) {}
    return false;
  }

  function unwrapNativeSelect(sel) {
    if (!sel || sel.dataset.customSelect !== 'yes') return;
    var wrapper = sel.closest ? sel.closest('.custom-select-wrapper') : null;
    if (!wrapper || !wrapper.parentNode) return;
    try {
      sel.style.position = '';
      sel.style.left = '';
      sel.style.width = '';
      sel.style.height = '';
      sel.style.opacity = '';
      sel.style.pointerEvents = '';
    } catch (_) {}
    delete sel.dataset.customSelect;
    wrapper.parentNode.insertBefore(sel, wrapper);
    wrapper.parentNode.removeChild(wrapper);
  }

  function wrapSelect(sel) {
      if (!sel || sel.tagName !== 'SELECT' || sel.dataset.customSelect === 'yes') return;
      if (shouldUseNativeSelect(sel)) {
        unwrapNativeSelect(sel);
        return;
      }
      if (sel.size > 1) return;
      if (String(sel.getAttribute('data-native-select') || '').trim().toLowerCase() === 'yes') return;
      var originalRect = null;
      var originalStyle = null;
      try {
        originalRect = sel.getBoundingClientRect();
        originalStyle = window.getComputedStyle(sel);
      } catch (_) {}
      sel.dataset.customSelect = 'yes';

      var wrapper = document.createElement('div');
      wrapper.className = 'custom-select-wrapper';
      wrapper.style.cssText = 'position:relative; width:100%;';
      try {
        if (sel.style.flex) wrapper.style.flex = sel.style.flex;
        if (sel.style.minWidth) wrapper.style.minWidth = sel.style.minWidth;
        if (sel.style.flexGrow) wrapper.style.flexGrow = sel.style.flexGrow;
        if (sel.style.flexShrink) wrapper.style.flexShrink = sel.style.flexShrink;
        if (sel.style.flexBasis) wrapper.style.flexBasis = sel.style.flexBasis;
      } catch (_) {}
      if (originalStyle) {
        /* Replacing the native control asynchronously must preserve its outer box.
           Otherwise every lost select margin/height moves all following panels. */
        wrapper.style.marginTop = originalStyle.marginTop;
        wrapper.style.marginRight = originalStyle.marginRight;
        wrapper.style.marginBottom = originalStyle.marginBottom;
        wrapper.style.marginLeft = originalStyle.marginLeft;
        wrapper.style.alignSelf = originalStyle.alignSelf;
        wrapper.style.verticalAlign = originalStyle.verticalAlign;
        wrapper.style.maxWidth = originalStyle.maxWidth;
      }

      var display = document.createElement('div');
      display.className = 'custom-select-display editor-select';
      display.style.cssText = 'width:100%; padding:5px 8px; border-radius:6px; border:1px solid rgba(255, 120, 220, 0.45); background:' + DROPDOWN_BG + '; color:var(--text-primary); font-size:12px; line-height:1.3; cursor:pointer; min-height:28px; display:flex; align-items:center; gap:6px; box-sizing:border-box;';
      /* Keep compact — do not inherit tall native <select> box height into the custom chrome. */
      display.setAttribute('aria-haspopup', 'listbox');
      display.setAttribute('role', 'combobox');

      var list = document.createElement('div');
      list.className = 'custom-select-list';
      list.style.cssText = 'display:none; position:absolute; left:0; right:0; top:100%; margin-top:2px; max-height:180px; overflow-y:auto; overscroll-behavior:contain; -webkit-overflow-scrolling:touch; z-index:9999; border-radius:6px; border:1px solid rgba(255, 120, 220, 0.45); box-shadow:0 8px 24px rgba(0,0,0,1); background:' + DROPDOWN_BG + ';';
      list.addEventListener('wheel', function (e) {
        e.stopPropagation();
        // Keep page from scrolling while the user scrolls a long option list.
        var el = list;
        var delta = e.deltaY;
        if (!delta) return;
        var atTop = el.scrollTop <= 0;
        var atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
        if ((delta < 0 && atTop) || (delta > 0 && atBottom)) {
          e.preventDefault();
        }
      }, { passive: false });
      list.addEventListener('touchstart', function (e) { e.stopPropagation(); }, { passive: true });
      list.addEventListener('touchmove', function (e) { e.stopPropagation(); }, { passive: true });
      list.addEventListener('pointerdown', function (e) { e.stopPropagation(); }, { passive: true });

      var wrapperListDirty = true;
      var listIconObserver = null;
      var prebuildTimer = 0;

      function schedulePrebuild() {
        if (wrapper.classList.contains('is-open')) return;
        if (prebuildTimer) clearTimeout(prebuildTimer);
        prebuildTimer = window.setTimeout(function () {
          prebuildTimer = 0;
          if (!wrapper.classList.contains('is-open') && wrapperListDirty) buildList();
        }, isLiteUi() ? 48 : 20);
      }

    function iconSrcForOption(o) {
      if (!o || !o.getAttribute) return '';
      return String(o.getAttribute('data-cc-icon') || '').trim();
    }

    function iconFilterForOption(o) {
      if (!o || !o.getAttribute) return '';
      if (document.documentElement.classList.contains('stx-lite-ui')) return '';
      return String(o.getAttribute('data-cc-icon-filter') || '').trim();
    }

    function iconAltSrcForOption(o) {
      if (!o || !o.getAttribute) return '';
      return String(o.getAttribute('data-cc-icon-alt') || '').trim();
    }

    function bindIconErrorFallback(im, o) {
      if (!im || !o) return;
      var alt = iconAltSrcForOption(o);
      var triedAlt = false;
      var triedGeneric = false;
      im.addEventListener('load', function onIconOk() {
        try {
          im.style.visibility = '';
          im.style.opacity = '';
        } catch (_) {}
      });
      im.addEventListener('error', function onIconErr() {
        if (!triedAlt && alt) {
          triedAlt = true;
          im.src = alt;
          return;
        }
        /* Last resort: keep a chip visible for firmware / perk misses instead of a blank gap. */
        if (!triedGeneric) {
          triedGeneric = true;
          var src0 = iconSrcForOption(o);
          if (/classmod-firmware|dlc-firmware/i.test(src0) || /part_firmware/i.test(String(o.value || '') + String(o.textContent || ''))) {
            im.src = './assets/img/classmod-firmware/jacked.png';
            return;
          }
          if (/classmod-perks|classmod-passive/i.test(src0)) {
            im.src = './assets/img/guided-dropdowns/legendary-augments/ico_legendary_aug_classmod.png';
            return;
          }
        }
        try {
          im.style.visibility = 'hidden';
          im.style.opacity = '0';
          im.removeAttribute('src');
        } catch (_) {}
        im.removeEventListener('error', onIconErr);
      });
    }

    /** Always use a real <img>; CSS mask/multiply/filter on tier tints broke in Chromium/Electron. */
    function appendOptionIcon(topRow, o, imgClass, deferSrc) {
      if (!topRow || !o) return;
      var src = iconSrcForOption(o);
      if (!src) return;
      var flt = iconFilterForOption(o);
      var chip = document.createElement('span');
      chip.className = 'custom-select-icon-chip';

      var im = document.createElement('img');
      im.className = imgClass;
      im.alt = '';
      im.decoding = 'async';
      bindIconErrorFallback(im, o);
      if (deferSrc) {
        im.setAttribute('data-cc-defer-src', src);
      } else {
        assignIconSrc(im, src);
        im.loading = 'lazy';
      }
      if (flt) {
        var inner = document.createElement('span');
        inner.className = 'custom-select-icon-filter-wrap';
        inner.style.filter = flt;
        try { inner.style.setProperty('-webkit-filter', flt); } catch (_) {}
        inner.appendChild(im);
        chip.appendChild(inner);
      } else {
        chip.appendChild(im);
      }
      topRow.appendChild(chip);
    }

    function updateDisplay() {
      // Defer UI update to next frame to keep interaction responsive
      requestAnimationFrame(function () {
        var opt = sel.options[sel.selectedIndex];
        var src = opt ? iconSrcForOption(opt) : '';
        var flt = opt ? iconFilterForOption(opt) : '';
        var sub = opt && opt.getAttribute ? String(opt.getAttribute('data-cc-barrel-sub') || '').trim() : '';
        var descSub = opt && opt.getAttribute ? String(opt.getAttribute('data-cc-part-desc-sub') || '').trim() : '';
        var spawnSub = opt && opt.getAttribute ? String(opt.getAttribute('data-cc-spawn-sub') || '').trim() : '';
        var tone = opt && opt.getAttribute ? String(opt.getAttribute('data-cc-primary-tone') || '').trim() : '';
        var txt = (opt && opt.text) ? opt.text.trim() : (sel.placeholder || '—');

        if (display.dataset.lastTxt === txt && display.dataset.lastSrc === src && display.dataset.lastFlt === flt && display.dataset.lastSub === sub && display.dataset.lastDescSub === descSub && display.dataset.lastSpawnSub === spawnSub && display.dataset.lastTone === tone) return;
        display.dataset.lastTxt = txt;
        display.dataset.lastSrc = src;
        display.dataset.lastFlt = flt;
        display.dataset.lastSub = sub;
        display.dataset.lastDescSub = descSub;
        display.dataset.lastSpawnSub = spawnSub;
        display.dataset.lastTone = tone;

        display.innerHTML = '';
        if (sub || descSub || spawnSub) {
          display.style.flexDirection = 'column';
          display.style.alignItems = 'stretch';
          display.style.gap = '3px';
        } else {
          display.style.flexDirection = 'row';
          display.style.alignItems = 'center';
          display.style.gap = '8px';
        }
        var topRow = document.createElement('div');
        topRow.style.cssText = 'display:flex;align-items:center;gap:8px;width:100%;min-width:0;';
        if (src) {
          appendOptionIcon(topRow, opt, 'custom-select-display-icon', false);
        }
        var span = document.createElement('span');
        span.className = 'custom-select-display-text';
        span.style.cssText = sub
          ? 'flex:1;min-width:0;word-break:break-word;line-height:1.25;'
          : '';
        span.textContent = txt;
        if (tone === 'legendary') {
          try { span.style.setProperty('color', '#ffcc70', 'important'); } catch (_) { span.style.color = '#ffcc70'; }
        }
        topRow.appendChild(span);
        display.appendChild(topRow);
        if (spawnSub) {
          var spawnEl = document.createElement('div');
          spawnEl.className = 'custom-select-display-spawn';
          spawnEl.textContent = spawnSub.length > 72 ? spawnSub.slice(0, 69) + '…' : spawnSub;
          display.appendChild(spawnEl);
        }
        if (descSub) {
          var descEl = document.createElement('div');
          descEl.className = 'custom-select-display-desc';
          descEl.style.cssText = 'font-size:11px;line-height:1.3;word-break:break-word;padding-left:0;';
          descEl.textContent = descSub.length > 160 ? descSub.slice(0, 157) + '…' : descSub;
          display.appendChild(descEl);
        }
        if (sub) {
          var subEl = document.createElement('div');
          subEl.className = 'custom-select-display-sub';
          subEl.style.cssText = 'font-size:11px;line-height:1.25;opacity:1;word-break:break-word;padding-left:0;';
          try { subEl.style.setProperty('color', '#ff7b7b', 'important'); } catch (_) { subEl.style.color = '#ff7b7b'; }
          subEl.textContent = sub.length > 140 ? sub.slice(0, 137) + '…' : sub;
          display.appendChild(subEl);
        }
      });
    }

    function clearSelectLift(w) {
      var nodes = w.__ccLiftNodes;
      if (!nodes || !nodes.length) return;
      for (var i = 0; i < nodes.length; i++) {
        try {
          nodes[i].classList.remove('cc-custom-select-lift');
        } catch (_) {}
      }
      w.__ccLiftNodes = null;
    }

    /** Raise ancestor panels / details so this dropdown stacks above following sections. */
    function applySelectLift(w) {
      clearSelectLift(w);
      var lift = [];
      var cur = w.parentElement;
      while (cur && cur !== document.body) {
        var cl = cur.classList;
        var tag = cur.tagName;
        if (cl && (cl.contains('rebuild-details') || cl.contains('rebuild-part-expandable'))) {
          cur.classList.add('cc-custom-select-lift');
          lift.push(cur);
        } else if (tag === 'DETAILS' && cur.closest && cur.closest('#rebuildGuidedBuilderSection, #stxSimpleBuilderPanel, #rebuildToolsPanel')) {
          cur.classList.add('cc-custom-select-lift');
          lift.push(cur);
        } else if (cl && cl.contains('cc-slot-panel')) {
          cur.classList.add('cc-custom-select-lift');
          lift.push(cur);
        }
        cur = cur.parentElement;
      }
      w.__ccLiftNodes = lift;
    }

    function restoreFloatedListHost() {
      if (!wrapper.__ccListFloated) return;
      wrapper.__ccListFloated = false;
      list.classList.remove('custom-select-list--floating');
      list.style.position = '';
      list.style.left = '';
      list.style.top = '';
      list.style.bottom = '';
      list.style.width = '';
      list.style.right = '';
      list.style.maxHeight = '';
      list.style.zIndex = '';
      list.style.pointerEvents = '';
      list.style.overflowY = '';
      if (list.parentNode !== wrapper) wrapper.appendChild(list);
    }
    // Back-compat alias for any external callers.
    function restoreMobileListHost() { restoreFloatedListHost(); }

    /**
     * Always float the open list onto document.body.
     * Desktop used a full-screen backdrop at z-index 2147482000 while the list
     * stayed position:absolute inside a low stacking context (details z-index
     * ~100–220), so wheel/click never reached the options. Floating fixes that
     * for skin mixer, tools skins, guided slots, etc.
     */
    function floatOpenList() {
      var r = display.getBoundingClientRect();
      wrapper.__ccListFloated = true;
      if (list.parentNode !== document.body) document.body.appendChild(list);
      list.classList.add('custom-select-list--floating');
      var pad = 8;
      var width = Math.min(Math.max(r.width, 160), window.innerWidth - pad * 2);
      var left = Math.max(pad, Math.min(r.left, window.innerWidth - width - pad));
      var spaceBelow = window.innerHeight - r.bottom - pad;
      var spaceAbove = r.top - pad;
      var preferred = touchSelectUi() ? 320 : 360;
      var maxH = Math.min(preferred, Math.max(160, Math.max(spaceBelow, spaceAbove) - 6));
      list.style.position = 'fixed';
      list.style.left = left + 'px';
      list.style.width = width + 'px';
      list.style.right = 'auto';
      list.style.maxHeight = maxH + 'px';
      list.style.overflowY = 'auto';
      list.style.zIndex = floatingListZIndex(sel);
      list.style.pointerEvents = 'auto';
      if (spaceBelow >= 120 || spaceBelow >= spaceAbove) {
        list.style.top = (r.bottom + 2) + 'px';
        list.style.bottom = 'auto';
      } else {
        list.style.top = 'auto';
        list.style.bottom = (window.innerHeight - r.top + 2) + 'px';
      }
    }
    function floatMobileList() { floatOpenList(); }

    var openGuardUntil = 0;
    var closeHandlerTimer = 0;

    function targetInDropdown(target) {
      if (!target) return false;
      try {
        if (display === target || display.contains(target)) return true;
        if (list === target || list.contains(target)) return true;
        if (wrapper.contains(target)) return true;
      } catch (_) {}
      return false;
    }

    function armOutsideCloseListeners() {
      if (closeHandlerTimer) {
        clearTimeout(closeHandlerTimer);
        closeHandlerTimer = 0;
      }
      document.removeEventListener('click', closeHandler, false);
      var guardMs = touchSelectUi() ? 520 : 120;
      var attachMs = touchSelectUi() ? guardMs + 24 : 0;
      closeHandlerTimer = window.setTimeout(function () {
        closeHandlerTimer = 0;
        document.addEventListener('click', closeHandler, false);
      }, attachMs);
    }

    function finishCloseDropdown() {
      if (closeHandlerTimer) {
        clearTimeout(closeHandlerTimer);
        closeHandlerTimer = 0;
      }
      try {
        var searchEl = list.querySelector('.custom-select-search');
        if (searchEl) {
          searchEl.value = '';
          applySearchFilter('');
        }
      } catch (_) {}
      list.style.display = 'none';
      restoreFloatedListHost();
      wrapper.classList.remove('is-open');
      wrapper.style.zIndex = '';
      clearSelectLift(wrapper);
      openGuardUntil = 0;
      try { window.__stxCustomSelectOpenGuardUntil = 0; } catch (_) {}
      document.removeEventListener('click', closeHandler, false);
      document.removeEventListener('scroll', onViewportChange, true);
      window.removeEventListener('resize', onViewportChange, false);
      hideSelectBackdrop(0);
    }

    function onViewportChange() {
      if (!wrapper.classList.contains('is-open')) return;
      floatOpenList();
    }
    wrapper.__ccFinishClose = finishCloseDropdown;

    function buildList() {
      if (!wrapperListDirty) return;
      list.innerHTML = '';

      if (listIconObserver) {
        try { listIconObserver.disconnect(); } catch (_) {}
        listIconObserver = null;
      }

      listIconObserver = new IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          var en = entries[i];
          if (!en.isIntersecting) continue;
          var row = en.target;
          var imgs = row.querySelectorAll ? row.querySelectorAll('img[data-cc-defer-src]') : [];
          for (var j = 0; j < imgs.length; j++) {
            var im = imgs[j];
            var ds = im.getAttribute('data-cc-defer-src');
            if (!ds) continue;
            assignIconSrc(im, ds);
            im.removeAttribute('data-cc-defer-src');
          }
          try { listIconObserver.unobserve(row); } catch (_) {}
        }
      }, { root: null, rootMargin: '120px 0px 120px 0px', threshold: 0 });

      var children = Array.prototype.slice.call(sel.children || []);
      var optionCount = countSelectOptions(sel);
      var policy = getListBuildPolicy(sel, optionCount);
      var chunkThreshold = policy.threshold;
      var chunkSize = policy.chunkSize;

      function addOption(o, target) {
        var val = (o.value || '').trim();
        var txt = (o.text || val || '—').trim();
        var sub = o.getAttribute ? String(o.getAttribute('data-cc-barrel-sub') || '').trim() : '';
        var descSub = o.getAttribute ? String(o.getAttribute('data-cc-part-desc-sub') || '').trim() : '';
        var spawnSub = o.getAttribute ? String(o.getAttribute('data-cc-spawn-sub') || '').trim() : '';
        var tone = o.getAttribute ? String(o.getAttribute('data-cc-primary-tone') || '').trim() : '';
        var tip = o.getAttribute('title') || (o.title || '');
        if (spawnSub) tip = tip ? (tip + ' | ' + spawnSub) : spawnSub;
        if (descSub) tip = tip ? (tip + ' | ' + descSub) : descSub;
        if (sub) {
          tip = tip ? (tip + ' | ' + sub) : sub;
        }
        var item = document.createElement('div');
        item.className = 'custom-select-option';
        item.style.cssText = 'padding:5px 8px; cursor:pointer; color:#fff; font-size:12px; display:flex; flex-direction:column; align-items:stretch; gap:2px; min-height:0;';
        item.dataset.value = val;
        var topRow = document.createElement('div');
        topRow.style.cssText = 'display:flex;align-items:flex-start;gap:8px;width:100%;min-width:0;';
        var src = iconSrcForOption(o);
        if (src) {
          appendOptionIcon(topRow, o, 'custom-select-option-icon', true);
          try { listIconObserver.observe(item); } catch (_) {
            var im0 = item.querySelector && item.querySelector('img[data-cc-defer-src]');
            if (im0) {
              assignIconSrc(im0, src);
              im0.removeAttribute('data-cc-defer-src');
            }
          }
        }
        var span = document.createElement('span');
        span.style.cssText = 'flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;';
        span.textContent = txt;
        if (tone === 'legendary') {
          try { span.style.setProperty('color', '#ffcc70', 'important'); } catch (_) { span.style.color = '#ffcc70'; }
        }
        topRow.appendChild(span);
        item.appendChild(topRow);
        if (spawnSub) {
          var spawnRow = document.createElement('div');
          spawnRow.className = 'custom-select-option-spawn';
          spawnRow.style.cssText = 'font-size:10px;line-height:1.25;font-family:Consolas,ui-monospace,monospace;word-break:break-all;white-space:normal;width:100%;';
          spawnRow.textContent = spawnSub.length > 96 ? spawnSub.slice(0, 93) + '…' : spawnSub;
          item.appendChild(spawnRow);
        }
        if (descSub) {
          var descRow = document.createElement('div');
          descRow.className = 'custom-select-option-desc';
          descRow.style.cssText = 'font-size:11px;line-height:1.3;word-break:break-word;white-space:normal;width:100%;';
          descRow.textContent = descSub.length > 220 ? descSub.slice(0, 217) + '…' : descSub;
          item.appendChild(descRow);
        }
        if (sub) {
          var subRow = document.createElement('div');
          subRow.className = 'custom-select-option-sub';
          subRow.style.cssText = 'font-size:11px;line-height:1.3;color:#ff7b7b;word-break:break-word;white-space:normal;width:100%;';
          subRow.textContent = sub.length > 220 ? sub.slice(0, 217) + '…' : sub;
          item.appendChild(subRow);
        }
        if (tip) item.setAttribute('title', tip);
        item.addEventListener('mouseenter', function () { this.style.setProperty('background', DROPDOWN_HOVER, 'important'); });
        item.addEventListener('mouseleave', function () { this.style.removeProperty('background'); });
        var pickLocked = false;
        function pickOptionItem(e) {
          if (pickLocked) return;
          if (e) {
            e.preventDefault();
            e.stopPropagation();
          }
          pickLocked = true;
          sel.value = item.dataset.value;
          updateDisplay();
          finishCloseDropdown();
          setTimeout(function () {
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            pickLocked = false;
          }, 1);
        }
        item.addEventListener('click', pickOptionItem);
        if (touchSelectUi()) {
          item.addEventListener('touchend', pickOptionItem, { passive: false });
        }
        target.appendChild(item);
      }

      if (!policy.sync && children.length > chunkThreshold) {
        if (!list.querySelector('.custom-select-option') && !list.querySelector('.custom-select-group-header')) {
          list.innerHTML = '<div class="cc-custom-select-loading" style="padding:10px;color:var(--text-muted);font-size:11px;">Loading options…</div>';
        }

        var buildState = { childIdx: 0, optIdx: 0 };
        function nextChunk() {
          var loading = list.querySelector('.cc-custom-select-loading');
          if (loading) loading.remove();
          var frag = document.createDocumentFragment();
          var added = 0;
          while (buildState.childIdx < children.length && added < chunkSize) {
            var c = children[buildState.childIdx];
            if (c.tagName === 'OPTGROUP') {
              if (buildState.optIdx === 0) {
                var header = document.createElement('div');
                header.className = 'custom-select-group-header';
                header.style.cssText = 'padding:6px 10px 4px; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:rgba(0,243,255,0.9); border-bottom:1px solid rgba(0,243,255,0.2);' + (buildState.childIdx > 0 ? ' margin-top:8px;' : '');
                header.textContent = c.label || '';
                frag.appendChild(header);
              }
              var opts = c.querySelectorAll ? c.querySelectorAll('option') : [];
              while (buildState.optIdx < opts.length && added < chunkSize) {
                addOption(opts[buildState.optIdx], frag);
                buildState.optIdx++;
                added++;
              }
              if (buildState.optIdx >= opts.length) {
                buildState.childIdx++;
                buildState.optIdx = 0;
              }
            } else if (c.tagName === 'OPTION') {
              addOption(c, frag);
              buildState.childIdx++;
              added++;
            } else {
              buildState.childIdx++;
            }
          }
          list.appendChild(frag);
          if (buildState.childIdx < children.length) {
            var cont = nextChunk;
            if (policy.useRaf || wrapper.classList.contains('is-open')) {
              requestAnimationFrame(cont);
            } else if (typeof window.stxYieldToMain === 'function') {
              window.stxYieldToMain(cont);
            } else if (typeof window.stxScheduleIdle === 'function') {
              window.stxScheduleIdle(cont, 16);
            } else {
              requestAnimationFrame(cont);
            }
          } else {
            wrapperListDirty = false;
            ensureSearchUi();
          }
        }
        nextChunk();
        return;
      }

      list.innerHTML = '';
      var fragment = document.createDocumentFragment();
      for (var i = 0; i < children.length; i++) {
        var c = children[i];
        if (c.tagName === 'OPTGROUP') {
          var header = document.createElement('div');
          header.className = 'custom-select-group-header';
          header.style.cssText = 'padding:6px 10px 4px; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:rgba(0,243,255,0.9); border-bottom:1px solid rgba(0,243,255,0.2);' + (i > 0 ? ' margin-top:8px;' : '');
          header.textContent = c.label || '';
          fragment.appendChild(header);
          var opts = c.querySelectorAll ? c.querySelectorAll('option') : [];
          for (var j = 0; j < opts.length; j++) addOption(opts[j], fragment);
        } else if (c.tagName === 'OPTION') {
          addOption(c, fragment);
        }
      }
      list.appendChild(fragment);
      wrapperListDirty = false;
      ensureSearchUi();
    }

    function applySearchFilter(q) {
      var needle = String(q || '').trim().toLowerCase();
      var opts = list.querySelectorAll('.custom-select-option');
      var i;
      for (i = 0; i < opts.length; i++) {
        var item = opts[i];
        if (!needle) {
          item.style.display = '';
          continue;
        }
        var blob = (
          String(item.dataset.value || '') + ' ' +
          String(item.textContent || '') + ' ' +
          String(item.getAttribute('title') || '')
        ).toLowerCase();
        item.style.display = blob.indexOf(needle) >= 0 ? '' : 'none';
      }
      var headers = list.querySelectorAll('.custom-select-group-header');
      for (i = 0; i < headers.length; i++) {
        var h = headers[i];
        var next = h.nextElementSibling;
        var any = false;
        while (next && !next.classList.contains('custom-select-group-header')) {
          if (next.classList.contains('custom-select-option') && next.style.display !== 'none') {
            any = true;
            break;
          }
          next = next.nextElementSibling;
        }
        h.style.display = (!needle || any) ? '' : 'none';
      }
    }

    function ensureSearchUi() {
      var n = countSelectOptions(sel);
      var existing = list.querySelector('.custom-select-search');
      if (n < 12) {
        if (existing) existing.remove();
        return;
      }
      if (!existing) {
        existing = document.createElement('input');
        existing.type = 'search';
        existing.className = 'custom-select-search';
        existing.setAttribute('placeholder', 'Search…');
        existing.setAttribute('autocomplete', 'off');
        existing.setAttribute('aria-label', 'Filter options');
        existing.style.cssText = 'position:sticky;top:0;z-index:3;width:100%;box-sizing:border-box;padding:8px 10px;margin:0;border:0;border-bottom:1px solid rgba(255,120,220,0.35);border-radius:6px 6px 0 0;background:' + DROPDOWN_BG + ';color:var(--text-primary);font-size:13px;outline:none;';
        existing.addEventListener('click', function (e) { e.stopPropagation(); });
        existing.addEventListener('pointerdown', function (e) { e.stopPropagation(); });
        existing.addEventListener('touchstart', function (e) { e.stopPropagation(); }, { passive: true });
        existing.addEventListener('keydown', function (e) {
          e.stopPropagation();
          if (e.key === 'Escape') {
            existing.value = '';
            applySearchFilter('');
            finishCloseDropdown();
          }
        });
        existing.addEventListener('input', function () {
          applySearchFilter(existing.value);
        });
      }
      /* Chrome Issues: form fields need id or name (autofill / a11y). */
      if (!existing.id && !existing.name) {
        var base = String(sel.id || sel.name || 'select').replace(/[^a-zA-Z0-9_-]/g, '_') || 'select';
        var sid = 'cc-cs-search-' + base;
        if (document.getElementById(sid) && document.getElementById(sid) !== existing) {
          sid = sid + '-' + Math.random().toString(36).slice(2, 7);
        }
        existing.id = sid;
        existing.name = sid;
      } else if (!existing.name && existing.id) {
        existing.name = existing.id;
      } else if (!existing.id && existing.name) {
        existing.id = existing.name;
      }
      if (list.firstChild !== existing) {
        list.insertBefore(existing, list.firstChild);
      }
    }

    function openList(e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      if (wrapper.classList.contains('is-open')) return;
      closeOtherOpenCustomSelects(wrapper);
      var sid = sel && sel.id ? String(sel.id) : '';
      var lazyOpen = function (fn) {
        if (typeof fn !== 'function') return;
        if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(fn);
        else setTimeout(fn, 0);
      };
      if (sid === 'skinSelect' || sid === 'camoSelect') {
        lazyOpen(function () {
          try {
            if (typeof window.__stxArmSkinCamoSync === 'function') window.__stxArmSkinCamoSync({ immediate: true });
          } catch (_) {}
        });
      } else if (sid === 'ccGuidedSkinSelect' || sid === 'ccGuidedCamoSelect') {
        lazyOpen(function () {
          try {
            if (typeof window.loadGuidedSkinCamo === 'function') window.loadGuidedSkinCamo();
          } catch (_) {}
        });
      } else if (sid === 'toolsSkinSelect' || sid === 'toolsCamoSelect') {
        lazyOpen(function () {
          try {
            if (typeof window.populateSkinCamo === 'function') {
              window.populateSkinCamo(byId('toolsSkinSelect'), byId('toolsCamoSelect'));
            }
          } catch (_) {}
        });
      } else if (sid === 'toolsElementSelect' || sid === 'toolsDualElementSelect' || sid === 'toolsPearlElementSelect') {
        lazyOpen(function () {
          try {
            if (typeof window.refreshToolsStandaloneElementDropdowns === 'function') {
              window.refreshToolsStandaloneElementDropdowns();
            }
          } catch (_) {}
        });
      }
      var bd = ensureSelectBackdrop();
      bd.style.pointerEvents = 'auto';
      bd.style.zIndex = floatingBackdropZIndex(sel);
      bd.onclick = function (ev) {
        if (ev) {
          try { ev.preventDefault(); ev.stopPropagation(); } catch (_) {}
        }
        backdropClosesDropdown(ev, finishCloseDropdown);
      };
      wrapper.classList.add('is-open');
      wrapper.style.zIndex = selectHostNeedsTopStack(sel) ? '2147483647' : '2147483000';
      list.style.display = 'block';
      if (wrapperListDirty && !list.querySelector('.custom-select-option')) {
        list.innerHTML = '<div class="cc-custom-select-loading" style="padding:10px;color:var(--text-muted);font-size:11px;">Loading options…</div>';
      }
      applySelectLift(wrapper);
      floatOpenList();
      document.addEventListener('scroll', onViewportChange, true);
      window.addEventListener('resize', onViewportChange, false);
      var guardMs = touchSelectUi() ? 520 : 120;
      openGuardUntil = Date.now() + guardMs;
      try { window.__stxCustomSelectOpenGuardUntil = openGuardUntil; } catch (_) {}
      armOutsideCloseListeners();
      // Never build the full option DOM on the click frame — paint open shell first (INP).
      if (wrapperListDirty) {
        var deferBuild = function () {
          if (!wrapper.classList.contains('is-open')) return;
          buildList();
          floatOpenList();
        };
        if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(deferBuild);
        else requestAnimationFrame(function () { setTimeout(deferBuild, 0); });
      } else {
        ensureSearchUi();
      }
      requestAnimationFrame(function () {
        floatOpenList();
        try {
          var searchFocus = list.querySelector('.custom-select-search');
          if (searchFocus && !touchSelectUi()) searchFocus.focus();
        } catch (_) {}
      });
    }

    function closeHandler(e) {
      if (openGuardUntil && Date.now() < openGuardUntil) return;
      if (targetInDropdown(e && e.target)) return;
      finishCloseDropdown();
    }

    if (touchSelectUi()) {
      var openedViaPointer = false;
      display.addEventListener('pointerdown', function (e) {
        if (e.pointerType !== 'touch') return;
        if (wrapper.classList.contains('is-open')) {
          e.preventDefault();
          e.stopPropagation();
          finishCloseDropdown();
          return;
        }
        openedViaPointer = true;
        openList(e);
      }, { passive: false });
      display.addEventListener('click', function (e) {
        if (openedViaPointer) {
          openedViaPointer = false;
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        if (wrapper.classList.contains('is-open')) {
          e.preventDefault();
          e.stopPropagation();
          finishCloseDropdown();
          return;
        }
        openList(e);
      });
      display.style.touchAction = 'manipulation';
      display.addEventListener('pointerdown', function (e) {
        if (e.pointerType === 'touch') e.stopPropagation();
      }, { passive: true });
    } else {
      display.addEventListener('click', openList);
    }

    sel.style.position = 'absolute';
    sel.style.left = '-9999px';
    sel.style.width = '1px';
    sel.style.height = '1px';
    sel.style.opacity = '0';
    sel.style.pointerEvents = 'none';

    wrapper.appendChild(display);
    wrapper.appendChild(list);
    sel.parentNode.insertBefore(wrapper, sel);
    wrapper.appendChild(sel);

    updateDisplay();

    try {
      var selOpt = sel.options[sel.selectedIndex];
      var warmSrc = selOpt ? iconSrcForOption(selOpt) : '';
      if (warmSrc) warmIconSrc(warmSrc);
    } catch (_) {}

    var origChange = sel.onchange;
    sel.addEventListener('change', function () {
      updateDisplay();
      if (typeof origChange === 'function') origChange.call(sel);
    });

    var selObs = new MutationObserver(function () {
      updateDisplay();
      wrapperListDirty = true;
      if (wrapper.classList.contains('is-open')) {
        requestAnimationFrame(function () { buildList(); });
      } else {
        schedulePrebuild();
      }
    });
    selObs.observe(sel, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['data-cc-barrel-sub', 'data-cc-part-desc-sub', 'data-cc-spawn-sub', 'data-cc-primary-tone', 'data-cc-icon', 'data-cc-icon-alt', 'data-cc-icon-filter']
    });

    sel.__customSelectSync = function ccSelectSyncInvalidate() {
      try {
        if (display && display.dataset) {
          delete display.dataset.lastTxt;
          delete display.dataset.lastSrc;
          delete display.dataset.lastFlt;
          delete display.dataset.lastSub;
          delete display.dataset.lastDescSub;
          delete display.dataset.lastSpawnSub;
          delete display.dataset.lastTone;
        }
      } catch (_) {}
      updateDisplay();
    };
    sel.__customSelectForceRebuild = function ccSelectForceRebuild() {
      wrapperListDirty = true;
      if (prebuildTimer) {
        clearTimeout(prebuildTimer);
        prebuildTimer = 0;
      }
      buildList();
      updateDisplay();
    };
    sel.__customSelectPrebuild = function forcePrebuild() {
      if (wrapper.classList.contains('is-open')) return;
      if (prebuildTimer) {
        clearTimeout(prebuildTimer);
        prebuildTimer = 0;
      }
      wrapperListDirty = true;
      buildList();
    };

    if (isBuilderSelect(sel)) {
      var initCount = countSelectOptions(sel);
      if (initCount) {
        var initPolicy = getListBuildPolicy(sel, initCount);
        if (initPolicy.sync) buildList();
        else schedulePrebuild();
      }
    }
  }

  function selectIsInClosedDetails(sel) {
    try {
      var det = sel && sel.closest ? sel.closest('details') : null;
      return !!(det && !det.open);
    } catch (_) {
      return false;
    }
  }

  function wireDetailsSelectWrap(sel) {
    if (!sel || sel.__ccDetailsWrapBound) return;
    var det = sel.closest ? sel.closest('details') : null;
    if (!det) return;
    sel.__ccDetailsWrapBound = true;
    det.addEventListener('toggle', function () {
      if (!det.open) return;
      var wrapAll = function () {
        var kids = det.querySelectorAll ? det.querySelectorAll('select.editor-select, select') : [];
        for (var i = 0; i < kids.length; i++) {
          if (isGuidedSlotGridSelect(kids[i])) wrapGuidedSelect(kids[i]);
          else wrapSelect(kids[i]);
        }
      };
      if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(wrapAll);
      else setTimeout(wrapAll, 0);
    });
  }

  function wrapGuidedSelect(sel) {
    if (!sel || sel.tagName !== 'SELECT') return;
    if (selectIsInClosedDetails(sel)) return;
    wireDetailsSelectWrap(sel);
    wrapSelect(sel);
    if (typeof sel.__customSelectForceRebuild === 'function') {
      try { sel.__customSelectForceRebuild(); } catch (_) {}
    } else if (typeof sel.__customSelectPrebuild === 'function') {
      try { sel.__customSelectPrebuild(); } catch (_) {}
    } else if (typeof sel.__customSelectSync === 'function') {
      try { sel.__customSelectSync(); } catch (_) {}
    }
  }

  function bootGuidedSlotSelects(root) {
    var sels;
    if (root && root.querySelectorAll) {
      sels = root.querySelectorAll('.cc-guided-slots-grid select');
    } else {
      sels = document.querySelectorAll('#rebuildGuidedBuilderSection .cc-guided-slots-grid select');
    }
    for (var i = 0; i < sels.length; i++) wrapGuidedSelect(sels[i]);
  }

  function init() {
    try {
      if (typeof window.stxMarkGuidedSlotNativeSelects === 'function') window.stxMarkGuidedSlotNativeSelects();
    } catch (_) {}

    // Mission / YAML-field selects may already be wrapped from an older boot — force native.
    try {
      var nativeRoots = document.querySelectorAll('#ccMissionsEditor select, #ccExtraYamlEditors select');
      for (var ni = 0; ni < nativeRoots.length; ni++) {
        nativeRoots[ni].setAttribute('data-native-select', 'yes');
        unwrapNativeSelect(nativeRoots[ni]);
      }
    } catch (_) {}

    var selects = Array.prototype.slice.call(document.querySelectorAll('select.editor-select, .editor-page select, .app-shell select'));
    for (var si = 0; si < selects.length; si++) wireDetailsSelectWrap(selects[si]);
    var idx = 0;
    var chunk = isLiteUi() || touchSelectUi() ? 2 : 5;
    function wrapChunk() {
      var wrapped = 0;
      while (idx < selects.length && wrapped < chunk) {
        var candidate = selects[idx++];
        if (shouldSkipEarlyWrap(candidate)) continue;
        if (selectIsInClosedDetails(candidate)) continue;
        wrapSelect(candidate);
        wrapped++;
      }
      if (idx < selects.length) {
        var delay = (isLiteUi() || touchSelectUi()) ? 24 : 16;
        setTimeout(wrapChunk, delay);
      } else {
        bootGuidedSlotSelects();
      }
    }
    if (selects.length) wrapChunk();
    else bootGuidedSlotSelects();

    var observeRoot = document.querySelector('.app-shell') || document.querySelector('.editor-page') || document.body;
    var moRaf = 0;
    var pendingMo = [];
    var observer = new MutationObserver(function (mutations) {
      for (var mi = 0; mi < mutations.length; mi++) pendingMo.push(mutations[mi]);
      if (moRaf) return;
      moRaf = requestAnimationFrame(function () {
        moRaf = 0;
        var batch = pendingMo;
        pendingMo = [];
        try {
          for (var m = 0; m < batch.length; m++) {
            var added = batch[m].addedNodes;
            for (var j = 0; j < added.length; j++) {
              var n = added[j];
              if (n.nodeType === 1) {
                if (n.tagName === 'SELECT' && (n.classList.contains('editor-select') || n.closest('.editor-page') || n.closest('.app-shell'))) {
                  if (!shouldSkipEarlyWrap(n)) wrapSelect(n);
                }
                var kids = n.querySelectorAll && n.querySelectorAll('select.editor-select, select');
                if (kids) for (var k = 0; k < kids.length; k++) {
                  if (!shouldSkipEarlyWrap(kids[k])) wrapSelect(kids[k]);
                }
              }
            }
          }
        } catch (_) {}
      });
    });
    observer.observe(observeRoot, { childList: true, subtree: true });
  }

  function wrapAnyPendingSelects(root) {
    var sels;
    if (root && root.querySelectorAll) {
      sels = root.querySelectorAll('select:not([data-custom-select="yes"])');
    } else {
      sels = document.querySelectorAll('select.editor-select:not([data-custom-select="yes"]), .app-shell select:not([data-custom-select="yes"])');
    }
    for (var i = 0; i < sels.length; i++) {
      if (shouldSkipEarlyWrap(sels[i])) continue;
      if (selectIsInClosedDetails(sels[i])) continue;
      wrapSelect(sels[i]);
    }
  }

  var BUILDER_PRIORITY_SELECT_IDS = [
    'stx_itemType', 'stx_manufacturer', 'weaponType', 'rarity', 'mainPart'
  ];

  function bootPriorityBuilderSelects() {
    if (window.__ccCustomSelectPriorityBoot) return;
    window.__ccCustomSelectPriorityBoot = true;
    try {
      if (typeof window.stxMarkGuidedSlotNativeSelects === 'function') window.stxMarkGuidedSlotNativeSelects();
    } catch (_) {}
    for (var i = 0; i < BUILDER_PRIORITY_SELECT_IDS.length; i++) {
      var sel = byId(BUILDER_PRIORITY_SELECT_IDS[i]);
      if (!sel) continue;
      wireDetailsSelectWrap(sel);
      wrapSelect(sel);
    }
  }

  function bootCustomSelectRebuild() {
    if (window.__ccCustomSelectRebuildBoot) {
      wrapAnyPendingSelects();
      return;
    }
    window.__ccCustomSelectRebuildBoot = true;
    init();
  }
  function scheduleBootCustomSelectRebuild() {
    if (window.__ccCustomSelectRebuildBoot) return;
    var boot = bootCustomSelectRebuild;
    var lite = isLiteUi() || touchSelectUi();
    function armBoot() {
      if (window.__ccCustomSelectRebuildBoot) return;
      if (typeof window.stxScheduleIdle === 'function') {
        window.stxScheduleIdle(boot, lite ? 500 : 220);
      } else if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(boot, { timeout: lite ? 800 : 400 });
      } else {
        setTimeout(boot, lite ? 320 : 120);
      }
    }
    if (document.documentElement.classList.contains('stx-splash-dismissed')) {
      if (typeof window.stxYieldToMain === 'function') window.stxYieldToMain(armBoot);
      else setTimeout(armBoot, 32);
      return;
    }
    if (typeof window.stxWhenSplashDismissed === 'function') {
      window.stxWhenSplashDismissed(function () {
        if (typeof window.stxQueueIdleWork === 'function') {
          window.stxQueueIdleWork(armBoot, lite ? 120 : 48);
        } else if (typeof window.stxScheduleIdle === 'function') {
          window.stxScheduleIdle(armBoot, lite ? 120 : 48);
        } else {
          setTimeout(armBoot, lite ? 100 : 40);
        }
      });
    } else {
      armBoot();
    }
  }
  function schedulePriorityBuilderSelectWrap() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bootPriorityBuilderSelects, { once: true });
    } else {
      bootPriorityBuilderSelects();
    }
  }
  schedulePriorityBuilderSelectWrap();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleBootCustomSelectRebuild);
  } else {
    scheduleBootCustomSelectRebuild();
  }

  try {
    window.__ccForceCustomSelectSync = function (sel) {
      if (!sel || typeof sel.__customSelectSync !== 'function') return;
      sel.__customSelectSync();
    };
    window.__ccCustomSelectPrebuild = function (sel) {
      if (!sel || typeof sel.__customSelectPrebuild !== 'function') return;
      sel.__customSelectPrebuild();
    };
    window.__ccBootCustomSelectRebuild = bootCustomSelectRebuild;
    window.__ccBootPriorityBuilderSelects = bootPriorityBuilderSelects;
    window.__ccBootGuidedSlotSelects = bootGuidedSlotSelects;
    window.__ccWrapGuidedSelect = wrapGuidedSelect;
  } catch (_) {}
})();
