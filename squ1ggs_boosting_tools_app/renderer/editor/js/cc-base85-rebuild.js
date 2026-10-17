(function () {
  'use strict';

  var CUSTOM_B85_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~';
  var B85_CHAR_IDX = (function () {
    var map = new Int16Array(128);
    for (var i = 0; i < 128; i++) map[i] = -1;
    for (var j = 0; j < CUSTOM_B85_ALPHABET.length; j++) {
      var c = CUSTOM_B85_ALPHABET.charCodeAt(j);
      if (c < 128) map[c] = j;
    }
    return map;
  })();
  var DESER_CACHE_MAX = 64;
  var deserializeCache = Object.create(null);
  var deserializeCacheKeys = [];
  var BIT_REVERSE8 = (function () {
    var t = new Uint8Array(256);
    for (var b = 0; b < 256; b++) {
      var rev = 0;
      var v = b;
      for (var i = 0; i < 8; i++) {
        rev = (rev << 1) | (v & 1);
        v >>= 1;
      }
      t[b] = rev;
    }
    return t;
  })();

  function reverseBitsInByte(b) {
    return BIT_REVERSE8[b & 255];
  }

  function stripOuterQuotes(s) {
    s = String(s || '').trim();
    while (s.charAt(0) === '"' || s.charAt(0) === "'") {
      if ((s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') || (s.charAt(0) === "'" && s.charAt(s.length - 1) === "'")) break;
      s = s.slice(1).trim();
    }
    if ((s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') || (s.charAt(0) === "'" && s.charAt(s.length - 1) === "'")) {
      s = s.slice(1, -1).trim();
    }
    while (s.charAt(s.length - 1) === '"' || s.charAt(s.length - 1) === "'") s = s.slice(0, -1).trim();
    return s.trim();
  }

  function customBase85Decode(data) {
    data = String(data || '');
    if (data.charAt(0) === '@' && (data.charAt(1) === 'U' || data.charAt(1) === 'u')) data = data.slice(2);
    data = data.replace(/\s+/g, '');
    data = data.replace(/\//g, '|');
    if (!data) return new Uint8Array(0);
    for (var ci = 0; ci < data.length; ci++) {
      var ch = data.charCodeAt(ci);
      var ix = ch < 128 ? B85_CHAR_IDX[ch] : -1;
      if (ix < 0) {
        throw new Error('Invalid Base85 character at index ' + ci);
      }
    }
    var padLen = (5 - (data.length % 5)) % 5;
    var lastChar = CUSTOM_B85_ALPHABET.charAt(CUSTOM_B85_ALPHABET.length - 1);
    if (padLen) {
      for (var p = 0; p < padLen; p++) data += lastChar;
    }
    var rawLen = (data.length / 5) * 4;
    var out = new Uint8Array(rawLen);
    var o = 0;
    for (var i = 0; i < data.length; i += 5) {
      var acc = 0;
      for (var j = 0; j < 5; j++) {
        var code = data.charCodeAt(i + j);
        var idx = code < 128 ? B85_CHAR_IDX[code] : -1;
        if (idx < 0) throw new Error('Invalid Base85 character');
        acc = acc * 85 + idx;
      }
      out[o++] = (acc >>> 24) & 0xff;
      out[o++] = (acc >>> 16) & 0xff;
      out[o++] = (acc >>> 8) & 0xff;
      out[o++] = acc & 0xff;
    }
    var usable = padLen ? (rawLen - padLen) : rawLen;
    var mirrored = new Uint8Array(usable);
    for (var m = 0; m < usable; m++) mirrored[m] = BIT_REVERSE8[out[m]];
    return mirrored;
  }

  /** True when `s` is a safe BL4 `@U…` custom-Base85 serial (no deser markers / non-alphabet).
   *  `{`, `|`, `}` are in the BL4 alphabet — never reject those. Stored form uses `/` for `|`. */
  function ccIsValidStoredBase85(s) {
    var t = String(s || '').trim().replace(/^["']|["']$/g, '');
    if (!t) return false;
    if (t === '…' || t === '—' || t === '-' || t === '…') return false;
    if (t.indexOf('@U') !== 0 && t.indexOf('@u') !== 0) return false;
    if (t.length < 10) return false;
    /* Deserialized leftovers — not Base85. `{` is a legal alphabet char and must pass. */
    if (t.indexOf(',') >= 0 || t.indexOf('||') >= 0 || t.indexOf(' ') >= 0) return false;
    var body = t.slice(2).replace(/\//g, '|');
    if (!body) return false;
    for (var i = 0; i < body.length; i++) {
      var c = body.charCodeAt(i);
      if (c >= 128 || B85_CHAR_IDX[c] < 0) return false;
    }
    return true;
  }
  window.ccIsValidStoredBase85 = ccIsValidStoredBase85;

  /**
   * Reject truncated / header-only @U when deserialized payload is clearly larger.
   * Prevents sticky short packs (e.g. type-select header) from surviving a full part build.
   * Thresholds stay conservative so real full packs are not false-rejected.
   */
  function ccBase85PlausibleForDeser(b85, deser) {
    var t = String(b85 || '').trim();
    if (!ccIsValidStoredBase85(t)) return false;
    var d = String(deser || '').trim();
    if (!d || d.indexOf('||') < 0) return true;
    var w = deserializedPayloadWeight(d);
    var dbl = d.indexOf('||');
    var tail = d.slice(dbl + 2);
    var partCount = (tail.match(/\{/g) || []).length;
    var listVals = (w && typeof w.listValues === 'number') ? w.listValues : 0;
    /* Header-only / tiny tails — short @U is expected. */
    if (partCount <= 2 && listVals < 8 && d.length < 180) return true;
    /*
     * Floor only — a packed classmod @U is hundreds+ chars; a ~30-char header stub must not pass.
     * Keep floors low enough that legitimate full packs always clear them.
     */
    var minLen = 24;
    if (partCount > 5 || listVals > 10 || d.length > 400) {
      minLen = Math.max(40, 24 + Math.min(partCount, 80) + Math.min(Math.floor(listVals / 3), 40));
    }
    if (partCount > 40 || listVals > 30 || d.length > 1200) minLen = Math.max(minLen, 80);
    if (partCount > 100 || listVals > 60 || d.length > 2500) minLen = Math.max(minLen, 120);
    return t.length >= minLen;
  }
  window.ccBase85PlausibleForDeser = ccBase85PlausibleForDeser;

  function bytesToCustomB85(data) {
    var padLen = (4 - (data.length % 4)) % 4;
    var padded = new Uint8Array(data.length + padLen);
    for (var i = 0; i < data.length; i++) padded[i] = reverseBitsInByte(data[i]);
    var out = '';
    for (var i = 0; i < padded.length; i += 4) {
      var acc = 0;
      for (var j = 0; j < 4; j++) {
        acc = ((acc << 8) | (padded[i + j] || 0)) >>> 0;
      }
      var chars = [];
      for (var k = 0; k < 5; k++) {
        chars.push(CUSTOM_B85_ALPHABET.charAt(acc % 85));
        acc = Math.floor(acc / 85);
      }
      for (var r = chars.length - 1; r >= 0; r--) out += chars[r];
    }
    if (padLen > 0) {
      var charsToTrim = Math.floor((padLen * 5) / 4);
      out = out.slice(0, out.length - charsToTrim);
    }
    return out;
  }

  var TOK_SEP1 = 0;
  var TOK_SEP2 = 1;
  var TOK_VARINT = 2;
  var TOK_VARBIT = 3;
  var TOK_PART = 4;
  var TOK_STRING = 5;

  function BitReader(data, maxBits) {
    this.data = data;
    this.pos = 0;
    var cap = data.length * 8;
    this.maxBits = maxBits == null ? cap : Math.min(cap, maxBits >>> 0);
  }
  BitReader.prototype.read = function () {
    if (this.pos >= this.maxBits) return null;
    if (this.pos >= this.data.length * 8) return null;
    var byteIdx = this.pos >> 3;
    var bitIdx = 7 - (this.pos & 7);
    this.pos++;
    return (this.data[byteIdx] >> bitIdx) & 1;
  };
  BitReader.prototype.readN = function (n) {
    var v = 0;
    for (var i = 0; i < n; i++) {
      var b = this.read();
      if (b === null) return null;
      v = (v << 1) | b;
    }
    return v;
  };

  function mirror4(n) {
    return ((n >> 3) & 1) | ((n >> 1) & 2) | ((n << 1) & 4) | ((n << 3) & 8);
  }
  function mirror5(n) {
    var r = 0;
    for (var i = 0; i < 5; i++) r = (r << 1) | ((n >> i) & 1);
    return r;
  }

  function readVarint(br) {
    var output = 0;
    var dataRead = 0;
    for (var block = 0; block < 4; block++) {
      var nibble = br.readN(4);
      if (nibble === null) return null;
      output |= mirror4(nibble & 15) << dataRead;
      dataRead += 4;
      var cont = br.read();
      if (cont === null) return null;
      if (cont === 0) break;
    }
    return output;
  }

  function readVarbit(br) {
    var lenRaw = br.readN(5);
    if (lenRaw === null) return null;
    var length = mirror5(lenRaw & 31);
    if (length === 0) return 0;
    var v = 0;
    for (var i = 0; i < length; i++) {
      var b = br.read();
      if (b === null) return null;
      v |= b << i;
    }
    return v;
  }

  function nextToken(br) {
    var b1 = br.read();
    var b2 = br.read();
    if (b1 === null || b2 === null) return null;
    var tok = (b1 << 1) | b2;
    if (tok === 0) return TOK_SEP1;
    if (tok === 1) return TOK_SEP2;
    var b3 = br.read();
    if (b3 === null) return null;
    tok = (tok << 1) | b3;
    if (tok === 4) return TOK_VARINT;
    if (tok === 6) return TOK_VARBIT;
    if (tok === 5) return TOK_PART;
    if (tok === 7) return TOK_STRING;
    return null;
  }

  function readPart(br) {
    var index = readVarint(br);
    if (index === null) return null;
    var flag1 = br.read();
    if (flag1 === null) return null;
    if (flag1 === 1) {
      var value = readVarint(br);
      if (value === null) return null;
      br.read();
      br.read();
      br.read();
      return { index: index, subtype: 'int', value: value };
    }
    var flag2 = br.readN(2);
    if (flag2 === null) return null;
    if (flag2 === 2) return { index: index, subtype: 'none' };
    if (flag2 === 1) {
      var token = nextToken(br);
      if (token !== TOK_SEP2) return null;
      var values = [];
      while (true) {
        token = nextToken(br);
        if (token === TOK_SEP1) break;
        if (token === TOK_VARINT) {
          var v = readVarint(br);
          if (v === null) return null;
          values.push(v);
        } else if (token === TOK_VARBIT) {
          v = readVarbit(br);
          if (v === null) return null;
          values.push(v);
        } else return null;
      }
      return { index: index, subtype: 'list', values: values };
    }
    return null;
  }

  function readString(br) {
    var len = readVarint(br);
    if (len === null) return null;
    var s = '';
    for (var i = 0; i < len; i++) {
      var ch = 0;
      for (var b = 0; b < 7; b++) {
        var bit = br.read();
        if (bit === null) return null;
        ch |= bit << b;
      }
      s += String.fromCharCode(ch);
    }
    return s;
  }

  function bytesEqual(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  function normalizeDeserForCache(s) {
    return String(s || '')
      .trim()
      .replace(/\r\n/g, '\n')
      .replace(/[ \t]+/g, ' ')
      .replace(/\|\s*$/, '|');
  }

  function rememberDeserializeRoundtrip(b85In, deserOut) {
    try {
      if (!b85In || !deserOut) return;
      var b = String(b85In).trim();
      if (b.indexOf('@U') !== 0 && b.indexOf('@u') !== 0) return;
      window.__ccStxDeserializeCache = {
        b85In: b.indexOf('@U') === 0 ? b : ('@U' + b.replace(/^@U/i, '')),
        deserOut: normalizeDeserForCache(deserOut),
      };
    } catch (_) {}
  }

  function cachedBase85ForDeserialized(deser) {
    try {
      var cache = window.__ccStxDeserializeCache;
      if (!cache || !cache.b85In || !cache.deserOut) return '';
      if (normalizeDeserForCache(deser) === cache.deserOut) return cache.b85In;
    } catch (_) {}
    return '';
  }

  /** Rough weight for UI deferral — large list parts dominate pack time. */
  function deserializedPayloadWeight(s) {
    s = String(s || '');
    var listValues = 0;
    var re = /\{\d+:\[([^\]]*)\]\}/g;
    var m;
    while ((m = re.exec(s))) {
      var inner = (m[1] || '').trim();
      if (inner) listValues += inner.split(/\s+/).filter(Boolean).length;
    }
    return {
      len: s.length,
      listValues: listValues,
      heavy: s.length > 12000 || listValues > 400,
    };
  }

  function bitstreamToDeserialized(bytes, maxBits) {
    var br = new BitReader(bytes, maxBits);
    for (var i = 0; i < 7; i++) br.read();
    var parts = [];
    var current = [];
    var result = [];
    while (true) {
      var token = nextToken(br);
      if (token === null) break;
      if (token === TOK_SEP1) {
        if (current.length) result.push(current.join(', '));
        result.push('|');
        current = [];
        continue;
      }
      if (token === TOK_SEP2) {
        continue;
      }
      if (token === TOK_VARINT) {
        var v = readVarint(br);
        if (v === null) break;
        current.push(String(v));
        continue;
      }
      if (token === TOK_VARBIT) {
        v = readVarbit(br);
        if (v === null) break;
        current.push(String(v));
        continue;
      }
      if (token === TOK_PART) {
        var p = readPart(br);
        if (p === null) break;
        if (p.subtype === 'none') parts.push('{' + p.index + '}');
        else if (p.subtype === 'int') parts.push('{' + p.index + ':' + p.value + '}');
        else parts.push('{' + p.index + ':[' + p.values.join(' ') + ']}');
        continue;
      }
      if (token === TOK_STRING) {
        var str = readString(br);
        if (str === null) break;
        parts.push('"' + str + '"');
        continue;
      }
    }
    var blocks = [];
    for (var r = 0; r < result.length; r++) {
      if (result[r] !== '|') blocks.push(result[r]);
    }
    var out = blocks.filter(Boolean).join('| ');
    var emptyCount = 0;
    for (var e = 0; e < blocks.length; e++) if (blocks[e] === '') emptyCount++;
    for (var j = 0; j < emptyCount; j++) out += '|';
    if (parts.length) out += (out ? ' ' : '') + parts.join(' ');
    out += '|';
    return out.trim();
  }

  function ensureDoublePipeBeforeTailText(s) {
    s = String(s || '').trim();
    if (!s || s.indexOf('||') >= 0) return s;
    var m = s.match(/^([\s\S]+?)(\s+)(\{[\s\S]*)$/);
    if (!m) return s;
    var head = m[1];
    if (!/^[\d\s,|]+$/.test(head.replace(/\s+$/, ''))) return s;
    return head + '||' + m[2] + m[3];
  }

  function deserializeCacheKey(b85) {
    var s = stripOuterQuotes(b85);
    if (!s) return '';
    if (s.indexOf('@u') === 0) s = '@U' + s.slice(2);
    else if (s.indexOf('@U') !== 0 && /^[0-9A-Za-z!#$%&()*+;<=>?@^_`{|}~\/-]+$/.test(s)) s = '@U' + s;
    return s;
  }

  function rememberDeserializeCache(key, out) {
    if (!key || !out) return;
    if (deserializeCache[key]) return;
    deserializeCacheKeys.push(key);
    deserializeCache[key] = out;
    if (deserializeCacheKeys.length > DESER_CACHE_MAX) {
      var old = deserializeCacheKeys.shift();
      if (old) delete deserializeCache[old];
    }
  }

  function deserializeBase85(b85, headerWords) {
    headerWords = headerWords || 17;
    b85 = stripOuterQuotes(b85);
    if (!b85) return '';
    var cacheKey = deserializeCacheKey(b85);
    if (cacheKey && deserializeCache[cacheKey]) return deserializeCache[cacheKey];
    var bytes;
    try {
      bytes = customBase85Decode(b85);
    } catch (e) {
      console.warn('Failed to base85-decode:', e);
      return '';
    }
    try {
      var maxBits = null;
      var rt = null;
      try {
        rt = window.__ccStxRoundtrip;
        if (rt && typeof rt.bitsLen === 'number' && rt.bytes && bytesEqual(bytes, rt.bytes)) {
          maxBits = rt.bitsLen;
        }
      } catch (_) {}
      var out = ensureDoublePipeBeforeTailText(bitstreamToDeserialized(bytes, maxBits));
      if (maxBits != null && rt && bytesEqual(bytes, rt.bytes)) {
        try { delete window.__ccStxRoundtrip; } catch (_) {}
      }
      rememberDeserializeRoundtrip(b85, out);
      if (cacheKey) rememberDeserializeCache(cacheKey, out);
      return out;
    } catch (e) {
      console.warn('Failed to parse bitstream:', e);
      return b85;
    }
  }

  function serializeToBase85(deser, headerWords, trackRoundtrip) {
    headerWords = headerWords || 17;
    deser = stripOuterQuotes(deser);
    deser = ensureDoublePipeBeforeTailText(deser);
    if (!deser) return '';
    var cached = cachedBase85ForDeserialized(deser);
    if (cached) {
      if (typeof ccBase85PlausibleForDeser !== 'function' || ccBase85PlausibleForDeser(cached, deser)) return cached;
    }
    var alreadyU = String(deser).trim();
    if (/^@U/i.test(alreadyU)) {
      alreadyU = alreadyU.indexOf('@U') === 0 ? alreadyU : ('@U' + alreadyU.replace(/^@U/i, ''));
      if (alreadyU.length >= 10 && alreadyU.indexOf(',') < 0 && alreadyU.indexOf('||') < 0) return alreadyU;
    }
    function packOk(p) {
      p = String(p || '').trim();
      if (!p || p.indexOf('@U') !== 0) return '';
      if (typeof ccIsValidStoredBase85 === 'function' && !ccIsValidStoredBase85(p)) return '';
      return p;
    }
    var nicnlPacked = '';
    try {
      if (typeof window.__stxNicnlPackDeserialized === 'function') {
        try {
          nicnlPacked = packOk(window.__stxNicnlPackDeserialized(deser));
        } catch (_) { nicnlPacked = ''; }
      }
      var bits = deserializedToBitstream(deser);
      var bitsLen = bits.length;
      var bytes = bitsToBytes(bits);
      var mirrored = new Uint8Array(bytes.length);
      for (var i = 0; i < bytes.length; i++) mirrored[i] = reverseBitsInByte(bytes[i]);
      if (trackRoundtrip) {
        try {
          window.__ccStxRoundtrip = { bitsLen: bitsLen, bytes: new Uint8Array(mirrored) };
        } catch (_) {}
      }
      var b85 = bytesToCustomB85(mirrored);
      var bitPacked = '';
      if (b85) {
        bitPacked = packOk('@U' + String(b85).replace(/\|/g, '/'));
      }
      /* Prefer the longer valid pack so a header-only nicnl stub cannot beat a full bitstream. */
      if (nicnlPacked && bitPacked) return nicnlPacked.length >= bitPacked.length ? nicnlPacked : bitPacked;
      return nicnlPacked || bitPacked;
    } catch (e) {
      console.warn('Failed to serialize to base85:', e);
      try { if (window.__ccStxRoundtrip) delete window.__ccStxRoundtrip; } catch (_) {}
      return nicnlPacked || '';
    }
  }

  function bitsToBytes(bits) {
    while (bits.length % 8) bits += '0';
    var bytes = [];
    for (var i = 0; i < bits.length; i += 8) {
      bytes.push(parseInt(bits.slice(i, i + 8), 2));
    }
    return new Uint8Array(bytes);
  }

  function writeVarint(bits, value) {
    var v = value >>> 0;
    var nibbles = [];
    do {
      nibbles.push(v & 15);
      v >>>= 4;
    } while (v > 0);
    if (nibbles.length === 0) nibbles = [0];
    for (var i = 0; i < nibbles.length; i++) {
      var n = mirror4(nibbles[i] & 15);
      for (var b = 3; b >= 0; b--) bits += String((n >> b) & 1);
      bits += i < nibbles.length - 1 ? '1' : '0';
    }
    return bits;
  }

  function writeVarbit(bits, value) {
    var v = value >>> 0;
    var len = 0;
    var t = v;
    while (t) { len++; t >>= 1; }
    if (len === 0) len = 1;
    var len5 = mirror5(len);
    for (var i = 4; i >= 0; i--) bits += String((len5 >> i) & 1);
    for (var i = 0; i < len; i++) bits += String((v >> i) & 1);
    return bits;
  }

  function emitPartTokenBits(bits, braceTok) {
    var tok = String(braceTok || '').trim();
    var inner = tok.charAt(0) === '{' && tok.charAt(tok.length - 1) === '}' ? tok.slice(1, -1).trim() : tok;
    /* List form MUST be matched before `:digits` — `{234:[33 16]}` would otherwise
       take `:33` as an int subtype and drop the whole token. */
    var listM = inner.match(/^(\d+)\s*:\s*\[([^\]]*)\]\s*$/);
    var intM = !listM ? inner.match(/^(\d+)\s*:\s*(\d+)\s*$/) : null;
    var simpleM = (!listM && !intM) ? inner.match(/^(\d+)\s*$/) : null;
    if (!listM && !intM && !simpleM) return bits;
    bits += '101';
    if (listM) {
      bits = writeVarint(bits, parseInt(listM[1], 10));
      bits += '001';
      bits += '01';
      var vals = (listM[2] || '').match(/\d+/g) || [];
      for (var v = 0; v < vals.length; v++) {
        bits += '100';
        bits = writeVarint(bits, parseInt(vals[v], 10));
      }
      bits += '00';
    } else if (intM) {
      bits = writeVarint(bits, parseInt(intM[1], 10));
      bits += '1';
      bits = writeVarint(bits, parseInt(intM[2], 10));
      bits += '000';
    } else {
      bits = writeVarint(bits, parseInt(simpleM[1], 10));
      bits += '010';
    }
    return bits;
  }

  function emitStringTokenBits(bits, s) {
    bits += '111';
    bits = writeVarint(bits, s.length);
    for (var i = 0; i < s.length; i++) {
      var code = s.charCodeAt(i) & 0x7f;
      for (var b = 0; b < 7; b++) bits += String((code >> b) & 1);
    }
    return bits;
  }

  function emitNumericSegmentBits(bits, seg) {
    seg = String(seg || '').trim();
    if (!seg) {
      bits += '00';
      return bits;
    }
    var nums = seg.match(/\d+/g) || [];
    for (var n = 0; n < nums.length; n++) {
      bits += '100';
      bits = writeVarint(bits, parseInt(nums[n], 10));
      if (n < nums.length - 1) bits += '01';
    }
    bits += '00';
    return bits;
  }

  function tokenizeSegmentContent(seg) {
    var out = [];
    var re = /"([^"]*)"|(\{[^}]+\})|(\d+)/g;
    var m;
    while ((m = re.exec(seg))) {
      if (m[1] !== undefined) out.push({ type: 'str', v: m[1] });
      else if (m[2]) out.push({ type: 'part', v: m[2] });
      else if (m[3]) out.push({ type: 'num', v: parseInt(m[3], 10) });
    }
    return out;
  }

  function emitMixedSegmentBits(bits, seg) {
    var toks = tokenizeSegmentContent(seg);
    if (!toks.length) {
      bits += '00';
      return bits;
    }
    var i = 0;
    while (i < toks.length && toks[i].type === 'num') i++;
    var numRun = toks.slice(0, i);
    var rest = toks.slice(i);
    for (var n = 0; n < numRun.length; n++) {
      bits += '100';
      bits = writeVarint(bits, numRun[n].v);
      if (n < numRun.length - 1) bits += '01';
    }
    for (var j = 0; j < rest.length; j++) {
      if (rest[j].type === 'str') bits = emitStringTokenBits(bits, rest[j].v);
      else if (rest[j].type === 'part') bits = emitPartTokenBits(bits, rest[j].v);
    }
    bits += '00';
    return bits;
  }

  function emitTailAfterDoublePipe(bits, tail) {
    if (!tail || !String(tail).trim()) return bits;
    tail = String(tail).trim();
    var re = /"([^"]*)"|(\{[^}]+\})/g;
    var m;
    var any = false;
    while ((m = re.exec(tail))) {
      any = true;
      if (m[1] !== undefined) bits = emitStringTokenBits(bits, m[1]);
      else if (m[2]) bits = emitPartTokenBits(bits, m[2]);
    }
    if (any) {
      bits += '00';
      return bits;
    }
    return emitMixedSegmentBits(bits, tail);
  }

  function isNumericOnlySegment(seg) {
    var s = String(seg || '').trim();
    if (!s) return true;
    return /^\d+(\s*,\s*\d+)*\s*$/.test(s);
  }

  function deserializedToBitstream(deser) {
    var MAGIC = '0010000';
    var bits = MAGIC;
    deser = String(deser || '').replace(/\|\s*$/, '').trim();
    if (!deser) return bits;

    var dp = deser.indexOf('||');
    if (dp >= 0) {
      var left = deser.slice(0, dp).trim();
      var right = deser.slice(dp + 2).trim();
      var leftSegs = left.split('|').map(function (s) { return s.trim(); }).filter(function (s) { return s.length > 0; });
      for (var si = 0; si < leftSegs.length; si++) {
        bits = emitNumericSegmentBits(bits, leftSegs[si]);
      }
      if (right) bits = emitTailAfterDoublePipe(bits, right);
      return bits;
    }

    var segs = deser.split('|').map(function (s) { return s.trim(); }).filter(function (s) { return s.length > 0; });
    for (var i = 0; i < segs.length; i++) {
      var seg = segs[i];
      if (isNumericOnlySegment(seg)) bits = emitNumericSegmentBits(bits, seg);
      else bits = emitMixedSegmentBits(bits, seg);
    }
    return bits;
  }

  var LEVEL_PREFIX = '0110000000011001000001100';
  var MISSING_LEVEL_PATTERN = '0110000000011000100001';

  function parseVarintChunks(binaryStr) {
    var idx = binaryStr.indexOf(LEVEL_PREFIX);
    if (idx === -1) return null;
    var pos = idx + LEVEL_PREFIX.length;
    var valueBits = '';
    while (true) {
      var chunk = binaryStr.slice(pos, pos + 5);
      if (chunk.length < 5) return null;
      var dataBits = chunk.slice(0, 4);
      var cont = chunk[4] === '1';
      valueBits += dataBits;
      pos += 5;
      if (!cont) break;
    }
    var value = parseInt(valueBits.split('').reverse().join(''), 2);
    return { value: value, start: idx + LEVEL_PREFIX.length, end: pos };
  }

  function encodeVarintChunks(value) {
    var bits = value.toString(2).padStart(8, '0').split('').reverse().join('');
    bits = bits.replace(/0+$/, '');
    if (bits.length < 4) bits = bits.padEnd(4, '0');
    var chunks = [];
    for (var i = 0; i < bits.length; i += 4) chunks.push(bits.slice(i, i + 4));
    var out = '';
    for (var i = 0; i < chunks.length; i++) {
      var chunk = chunks[i].padEnd(4, '0');
      var cont = i < chunks.length - 1 ? '1' : '0';
      out += chunk + cont;
    }
    return out;
  }

  function updateSerialLevel(serial, newLevel) {
    if (!serial || typeof serial !== 'string') return serial;
    var decoded;
    try {
      decoded = customBase85Decode(serial);
    } catch (e) {
      console.warn('updateSerialLevel: decode failed', e);
      return serial;
    }
    var reversedBytes = new Uint8Array(decoded.length);
    for (var r = 0; r < decoded.length; r++) reversedBytes[r] = reverseBitsInByte(decoded[r]);
    var binaryStr = Array.from(reversedBytes).map(function (b) { return b.toString(2).padStart(8, '0'); }).join('');
    var newBinaryStr = null;
    var maxSerialLenDelta = 32;
    var parsed = parseVarintChunks(binaryStr);
    if (parsed) {
      newBinaryStr = binaryStr.slice(0, parsed.start) + encodeVarintChunks(newLevel) + binaryStr.slice(parsed.end);
    } else {
      var missIdx = binaryStr.indexOf(MISSING_LEVEL_PATTERN);
      if (missIdx !== -1) {
        var insertPos = missIdx + 12;
        var insertBits = '1001000001100' + encodeVarintChunks(newLevel) + '00';
        newBinaryStr = binaryStr.slice(0, insertPos) + insertBits + binaryStr.slice(insertPos);
        maxSerialLenDelta += 8;
      } else {
        return serial;
      }
    }
    if (newBinaryStr === null) return serial;
    var newBytes = bitsToBytes(newBinaryStr);
    var restoredBytes = new Uint8Array(newBytes.length);
    for (var i = 0; i < newBytes.length; i++) restoredBytes[i] = reverseBitsInByte(newBytes[i]);
    var b85Str = bytesToCustomB85(restoredBytes).replace(/\|/g, '/');
    var newSerial = '@U' + b85Str;
    if (Math.abs(newSerial.length - serial.length) > maxSerialLenDelta) {
      console.warn('Serial length differs by more than ' + maxSerialLenDelta + ' char(s) after level patch, keeping old value');
      return serial;
    }
    return newSerial;
  }

  function looksLikeDeserializedItemHeader(s) {
    s = String(s || '').trim().replace(/^["']|['"]$/g, '').replace(/^\uFEFF/, '');
    if (!s || s.indexOf('@U') === 0) return false;
    if (s.indexOf('||') >= 0) return true;
    return /^\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\|/.test(s);
  }

  function patchDeserializedHeaderLevel(raw, newLevel) {
    var s = String(raw || '').trim().replace(/^["']|['"]$/g, '').replace(/^\uFEFF/, '');
    var L = Math.floor(Number(newLevel));
    if (!Number.isFinite(L)) return null;
    var m = /^(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*)(\d+)(\s*\|[\s\S]*)$/.exec(s);
    if (!m) return null;
    return m[1] + String(L) + m[3];
  }

  function isLikelyPackedUserial(s) {
    s = String(s || '').trim().replace(/^["']|['"]$/g, '').replace(/^\uFEFF/, '');
    return s.indexOf('@U') === 0 && s.length > 8;
  }

  function deserializeSerialForLevelPatch(s0) {
    var deser = deserializeBase85(s0, 17);
    if (!deser || typeof deser !== 'string') return '';
    var dt = deser.trim();
    if (!dt) return '';
    if (/^@U/i.test(dt) && dt.indexOf(',') < 0 && dt.indexOf('|') < 0) return '';
    if (dt.indexOf('|') < 0 && !/^\s*\d+\s*,/.test(dt)) return '';
    return deser;
  }

  function updateSerialLevelFlexible(serial, newLevel) {
    if (!serial || typeof serial !== 'string') return serial;
    var L = Math.floor(Number(newLevel));
    if (!Number.isFinite(L)) return serial;
    var s0 = serial;
    var a = updateSerialLevel(s0, L);
    if (a !== s0) return a;

    var headerSource = null;
    if (looksLikeDeserializedItemHeader(s0)) {
      headerSource = s0;
    } else if (isLikelyPackedUserial(s0)) {
      headerSource = deserializeSerialForLevelPatch(s0);
      if (!headerSource) return s0;
    } else {
      return s0;
    }

    var patched = patchDeserializedHeaderLevel(headerSource, L);
    if (!patched) return s0;
    var normHeader = String(headerSource).trim().replace(/^["']|['"]$/g, '').replace(/^\uFEFF/, '');
    if (patched === normHeader) return s0;

    var b = serializeToBase85(patched, 17, false);
    if (!b || b.length < 7) {
      b = serializeToBase85(patched, 17, true);
      try {
        if (window.__ccStxRoundtrip) delete window.__ccStxRoundtrip;
      } catch (_) {}
    }
    if (!b || b.length < 7 || b === s0) return s0;
    return b;
  }

  function isSerialKey(k) {
    return String(k).toLowerCase() === 'serial';
  }

  function processSlotDeepStats(node, level, depth) {
    depth = depth == null ? 0 : depth;
    if (node == null || depth > 14) return { m: 0, f: 0 };
    if (Array.isArray(node)) {
      var ta = { m: 0, f: 0 };
      for (var i = 0; i < node.length; i++) {
        var si = processSlotDeepStats(node[i], level, depth + 1);
        ta.m += si.m;
        ta.f += si.f;
      }
      return ta;
    }
    if (typeof node !== 'object') return { m: 0, f: 0 };
    var out = { m: 0, f: 0 };
    for (var k in node) {
      if (!Object.prototype.hasOwnProperty.call(node, k)) continue;
      if (isSerialKey(k) && typeof node[k] === 'string' && String(node[k]).trim().length > 2) {
        out.f++;
        var next = updateSerialLevelFlexible(node[k], level);
        if (next !== node[k]) {
          node[k] = next;
          out.m++;
        }
      } else {
        var sub = processSlotDeepStats(node[k], level, depth + 1);
        out.m += sub.m;
        out.f += sub.f;
      }
    }
    return out;
  }

  function processInventorySlotContainer(container, level) {
    if (container == null) return { m: 0, f: 0 };
    if (Array.isArray(container)) return processSlotDeepStats(container, level, 0);
    if (typeof container !== 'object') return { m: 0, f: 0 };
    var tot = { m: 0, f: 0 };
    for (var sk in container) {
      if (container.hasOwnProperty(sk)) {
        var s = processSlotDeepStats(container[sk], level, 0);
        tot.m += s.m;
        tot.f += s.f;
      }
    }
    return tot;
  }

  function processSlot(slot, level) {
    processSlotDeepStats(slot, level, 0);
  }

  window.customBase85Decode = customBase85Decode;
  window.bytesToCustomB85 = bytesToCustomB85;
  window.deserializeBase85 = deserializeBase85;
  window.serializeToBase85 = serializeToBase85;
  window.ccDeserializedPayloadWeight = deserializedPayloadWeight;
  window.ccSerializeToBase85Async = function (deser, cb, headerWords) {
    var w = deserializedPayloadWeight(deser);
    var run = function () {
      var out = serializeToBase85(deser, headerWords, !w.heavy);
      if (typeof cb === 'function') cb(out);
      return out;
    };
    if (!w.heavy) return run();
    setTimeout(run, 0);
    return '';
  };
  window.ccDeserializeBase85Async = function (b85, cb, headerWords) {
    var src = String(b85 || '').trim();
    var run = function () {
      var out = deserializeBase85(src, headerWords);
      if (typeof cb === 'function') cb(out);
      return out;
    };
    /* Yield so Convert buttons stay responsive on long @U serials. */
    if (typeof cb === 'function') {
      setTimeout(run, 0);
      return '';
    }
    return run();
  };
  window.updateSerialLevel = updateSerialLevel;
  window.updateSerialLevelFlexible = updateSerialLevelFlexible;
  window.processSlot = processSlot;
  window.processInventorySlotContainer = processInventorySlotContainer;
})();
