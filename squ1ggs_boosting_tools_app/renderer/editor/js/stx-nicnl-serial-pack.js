/**
 * Pack deserialized text -> @U Base85 (FromString + Serialize + b85.Encode).
 * Required because WASM bl4DecodeBulk only accepts @U (b85.Decode rejects plain text).
 */
(function () {
  'use strict';

  var VARINT_NB = 4;
  var VARINT_BPB = 4;
  var VARINT_MAX_BITS = VARINT_NB * VARINT_BPB;

  function buildUint4Mirror() {
    var t = new Uint8Array(16);
    for (var i = 0; i < 16; i++) {
      var b = i;
      t[i] = ((b & 1) << 3) | ((b & 2) << 1) | ((b & 4) >> 1) | ((b & 8) >> 3);
    }
    return t;
  }
  function buildUint5Mirror() {
    var t = new Uint8Array(32);
    for (var i = 0; i < 32; i++) {
      var b = i;
      t[i] =
        ((b & 1) << 4) |
        ((b & 2) << 2) |
        (b & 4) |
        ((b & 8) >> 2) |
        ((b & 16) >> 4);
    }
    return t;
  }
  function buildUint7Mirror() {
    var t = new Uint8Array(128);
    for (var i = 0; i < 128; i++) {
      var b = i;
      t[i] =
        ((b & 1) << 6) |
        ((b & 2) << 4) |
        ((b & 4) << 2) |
        (b & 8) |
        ((b & 16) >> 2) |
        ((b & 32) >> 4) |
        ((b & 64) >> 6);
    }
    return t;
  }
  function buildUint8Mirror() {
    var t = new Uint8Array(256);
    for (var i = 0; i < 256; i++) {
      var b = i;
      t[i] =
        ((b & 1) << 7) |
        ((b & 2) << 5) |
        ((b & 4) << 3) |
        ((b & 8) << 1) |
        ((b & 16) >> 1) |
        ((b & 32) >> 3) |
        ((b & 64) >> 5) |
        ((b & 128) >> 7);
    }
    return t;
  }

  var M4 = buildUint4Mirror();
  var M5 = buildUint5Mirror();
  var M7 = buildUint7Mirror();
  var M8 = buildUint8Mirror();

  function BitWriter() {
    this.buf = [];
    this.pos = 0;
  }
  BitWriter.prototype.writeBit = function (bit) {
    var idx = this.pos;
    var bi = (idx / 8) | 0;
    var off = 7 - (idx % 8);
    while (this.buf.length <= bi) this.buf.push(0);
    if (bit & 1) this.buf[bi] |= 1 << off;
    else this.buf[bi] &= ~(1 << off);
    this.pos++;
  };
  BitWriter.prototype.writeBits = function () {
    for (var i = 0; i < arguments.length; i++) this.writeBit(arguments[i]);
  };
  BitWriter.prototype.bitsLen = function () {
    return this.pos;
  };
  BitWriter.prototype.copyBits = function () {
    var out = new Uint8Array(this.pos);
    for (var i = 0; i < this.pos; i++) {
      var bi = (i / 8) | 0;
      var off = 7 - (i % 8);
      out[i] = (this.buf[bi] >> off) & 1;
    }
    return out;
  };

  function varintWrite(bw, value) {
    value = value >>> 0;
    var nBits = 0;
    var v2 = value;
    while (v2 > 0) {
      nBits++;
      v2 >>>= 1;
    }
    if (nBits === 0) nBits = 1;
    if (nBits > VARINT_MAX_BITS) nBits = VARINT_MAX_BITS;
    while (nBits > VARINT_BPB) {
      for (var k = 0; k < VARINT_BPB; k++) {
        bw.writeBit(value & 1);
        value >>>= 1;
        nBits--;
      }
      bw.writeBit(1);
    }
    if (nBits > 0) {
      for (var i = 0; i < VARINT_BPB; i++) {
        if (nBits > 0) {
          bw.writeBit(value & 1);
          value >>>= 1;
          nBits--;
        } else bw.writeBit(0);
      }
      bw.writeBit(0);
    }
  }

  function intBitsSize(v, minSize, maxSize) {
    v = v >>> 0;
    var n = 0;
    while (v > 0) {
      n++;
      v >>>= 1;
    }
    if (n < minSize) n = minSize;
    if (n > maxSize) n = maxSize;
    return n;
  }

  function varbitWrite(bw, value) {
    value = value >>> 0;
    var nBits = intBitsSize(value, 0, 31);
    var lb = nBits;
    for (var i = 0; i < 5; i++) {
      bw.writeBit(lb & 1);
      lb >>>= 1;
    }
    for (var j = 0; j < nBits; j++) {
      bw.writeBit(value & 1);
      value >>>= 1;
    }
  }

  function bestTypeForNumber(v) {
    var w1 = new BitWriter();
    varintWrite(w1, v);
    var w2 = new BitWriter();
    varbitWrite(w2, v);
    if (w1.bitsLen() > w2.bitsLen()) return { kind: 'vbit', val: v };
    return { kind: 'vint', val: v };
  }

  /** List elements are almost always small part ids — skip per-value varint/varbit comparison. */
  function writeListValueFast(bw, value) {
    bw.writeBits(1, 0, 0);
    varintWrite(bw, value >>> 0);
  }

  var SUB_NONE = 0;
  var SUB_INT = 1;
  var SUB_LIST = 2;

  function partWrite(bw, p) {
    varintWrite(bw, p.index >>> 0);
    switch (p.sub) {
      case SUB_NONE:
        bw.writeBits(0, 1, 0);
        break;
      case SUB_INT:
        bw.writeBit(1);
        varintWrite(bw, p.value >>> 0);
        bw.writeBits(0, 0, 0);
        break;
      case SUB_LIST:
        bw.writeBits(0, 0, 1);
        bw.writeBits(0, 1);
        for (var i = 0; i < p.values.length; i++) {
          writeListValueFast(bw, p.values[i]);
        }
        bw.writeBits(0, 0);
        break;
      default:
        break;
    }
  }

  function b4stringWrite(bw, str) {
    varintWrite(bw, str.length >>> 0);
    for (var i = 0; i < str.length; i++) {
      var ch = str.charCodeAt(i) & 0xff;
      var m = M7[ch];
      for (var b = 6; b >= 0; b--) bw.writeBit((m >> b) & 1);
    }
  }

  function serializeBlocks(blocks) {
    var bw = new BitWriter();
    bw.writeBits(0, 0, 1, 0, 0, 0, 0);
    var i;
    for (i = 0; i < blocks.length; i++) {
      var b = blocks[i];
      switch (b.kind) {
        case 'sep1':
          bw.writeBits(0, 0);
          break;
        case 'sep2':
          bw.writeBits(0, 1);
          break;
        case 'vint':
          bw.writeBits(1, 0, 0);
          varintWrite(bw, b.val >>> 0);
          break;
        case 'vbit':
          bw.writeBits(1, 1, 0);
          varbitWrite(bw, b.val >>> 0);
          break;
        case 'part':
          bw.writeBits(1, 0, 1);
          partWrite(bw, b.part);
          break;
        case 'str':
          bw.writeBits(1, 1, 1);
          b4stringWrite(bw, b.str);
          break;
        default:
          break;
      }
    }
    var nBytes = Math.ceil(bw.pos / 8);
    var raw = new Uint8Array(nBytes);
    for (var bi = 0; bi < nBytes; bi++) raw[bi] = bw.buf[bi] || 0;
    return raw;
  }

  /** Same as cc-base85-rebuild bytesToCustomB85 (expects one bit-reverse pass like serializeToBase85). */
  function bytesToB85Body(data) {
    if (typeof window.bytesToCustomB85 === 'function') {
      return window.bytesToCustomB85(data);
    }
    var CUSTOM_B85_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~';
    function reverseBitsInByte(b) {
      var rev = 0;
      for (var i = 0; i < 8; i++) {
        rev = (rev << 1) | (b & 1);
        b >>= 1;
      }
      return rev;
    }
    var padLen = (4 - (data.length % 4)) % 4;
    var padded = new Uint8Array(data.length + padLen);
    for (var i = 0; i < data.length; i++) padded[i] = reverseBitsInByte(data[i]);
    var out = '';
    for (var p = 0; p < padded.length; p += 4) {
      var acc = 0;
      for (var j = 0; j < 4; j++) acc = ((acc << 8) | (padded[p + j] || 0)) >>> 0;
      var chars = [];
      for (var k = 0; k < 5; k++) {
        chars.push(CUSTOM_B85_ALPHABET.charAt(acc % 85));
        acc = Math.floor(acc / 85);
      }
      for (var r = chars.length - 1; r >= 0; r--) out += chars[r];
    }
    if (padLen > 0) out = out.slice(0, out.length - Math.floor((padLen * 5) / 4));
    return out;
  }

  function isNumbers(str) {
    str = String(str || '').trim();
    if (!str.length) return null;
    var j;
    for (j = 0; j < str.length; j++) {
      var c = str.charCodeAt(j);
      if (c < 48 || c > 57) return null;
    }
    var n = parseInt(str, 10);
    return Number.isFinite(n) ? (n >>> 0) : null;
  }

  function parsePartSubtypeList(partStr) {
    var str = String(partStr || '').trim();
    if (str.charAt(0) !== '{' || str.charAt(str.length - 1) !== '}') return null;
    var middle = str.slice(1, -1).trim();
    var splitted = middle.split(':');
    if (splitted.length < 2) return null;
    var index = isNumbers(splitted[0]);
    if (index == null) return null;
    var listStr = splitted.slice(1).join(':').trim();
    if (!listStr.length || listStr.charAt(0) !== '[' || listStr.charAt(listStr.length - 1) !== ']') return null;
    var inner = listStr.slice(1, -1).trim();
    var nums = inner.length ? inner.split(/[\s,]+/) : [];
    var list = [];
    var ni;
    for (ni = 0; ni < nums.length; ni++) {
      var t = nums[ni].trim();
      if (!t) continue;
      var v = isNumbers(t);
      if (v == null) return null;
      list.push(v);
    }
    return { index: index, values: list };
  }

  function parsePartSubtypeInt(partStr) {
    var str = String(partStr || '').trim();
    if (str.charAt(0) !== '{' || str.charAt(str.length - 1) !== '}') return null;
    var middle = str.slice(1, -1).trim();
    var splitted = middle.split(':');
    if (splitted.length !== 2) return null;
    var index = isNumbers(splitted[0]);
    var value = isNumbers(splitted[1]);
    if (index == null || value == null) return null;
    return { index: index, value: value };
  }

  function parsePartSimple(partStr) {
    var str = String(partStr || '').trim();
    if (str.charAt(0) !== '{' || str.charAt(str.length - 1) !== '}') return null;
    var inner = str.slice(1, -1).trim();
    var v = isNumbers(inner);
    return v == null ? null : v;
  }

  function nicnlTrailCleanup(s) {
    s = String(s || '').trim();
    if (!s.length) return s;
    if (s.charAt(s.length - 1) !== '|') s = s + '|';
    while (s.length >= 2 && s.charAt(s.length - 1) === '|' && s.charAt(s.length - 2) === '|') {
      s = s.slice(0, -1);
    }
    return s;
  }

  function fromStringToBlocks(str) {
    var blocks = [];
    var i = 0;
    var n = str.length;
    while (i < n) {
      var ch = str.charAt(i);
      var cc = str.charCodeAt(i);
      if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
        i++;
        continue;
      }
      if (ch === '|') {
        blocks.push({ kind: 'sep1' });
        i++;
        continue;
      }
      if (ch === ',') {
        blocks.push({ kind: 'sep2' });
        i++;
        continue;
      }
      if (ch === '{') {
        var end = str.indexOf('}', i);
        if (end < 0) throw new Error("unmatched '{' at position " + i);
        var partStr = str.slice(i, end + 1);
        i = end + 1;
        var pl = parsePartSubtypeList(partStr);
        if (pl) {
          blocks.push({ kind: 'part', part: { index: pl.index, sub: SUB_LIST, values: pl.values } });
          continue;
        }
        var pi = parsePartSubtypeInt(partStr);
        if (pi) {
          blocks.push({ kind: 'part', part: { index: pi.index, sub: SUB_INT, value: pi.value } });
          continue;
        }
        var ps = parsePartSimple(partStr);
        if (ps != null) {
          blocks.push({ kind: 'part', part: { index: ps, sub: SUB_NONE } });
          continue;
        }
        throw new Error("invalid part format: '" + partStr + "'");
      }
      if (cc >= 48 && cc <= 57) {
        var start = i;
        while (i < n && str.charCodeAt(i) >= 48 && str.charCodeAt(i) <= 57) i++;
        var numStr = str.slice(start, i);
        var vv = parseInt(numStr, 10) >>> 0;
        var tok = bestTypeForNumber(vv);
        blocks.push({ kind: tok.kind, val: vv });
        continue;
      }
      if (ch === '"') {
        var endq = i + 1;
        while (endq < n && str.charAt(endq) !== '"') {
          if (str.charAt(endq) === '\\' && endq + 1 < n && str.charAt(endq + 1) === '"') endq += 2;
          else endq++;
        }
        if (endq >= n) throw new Error("unmatched '\"' at position " + i);
        var strContent = str.slice(i + 1, endq);
        i = endq + 1;
        strContent = strContent.split('\\"').join('"').split('\\\\').join('\\');
        blocks.push({ kind: 'str', str: strContent });
        continue;
      }
      throw new Error("invalid character: '" + ch + "' at position " + i);
    }
    return blocks;
  }

  /**
   * @param {string} deserialized
   * @returns {string} @U… or '' on failure
   */
  function packDeserializedToU(deserialized) {
    try {
      var s = nicnlTrailCleanup(String(deserialized || '').trim());
      if (!s) return '';
      var blocks = fromStringToBlocks(s);
      var raw = serializeBlocks(blocks);
      // bytesToCustomB85 (and fallback) mirror each byte like standard b85.Encode.
      var body = bytesToB85Body(raw);
      if (!body) return '';
      body = String(body).replace(/\|/g, '/');
      return '@U' + body;
    } catch (e) {
      console.warn('stx-nicnl-serial-pack:', e && e.message ? e.message : e);
      return '';
    }
  }

  window.__stxNicnlPackDeserialized = packDeserializedToU;
})();
