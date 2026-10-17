"use strict";

/**
 * Raw InventoryStatModifier contribution for NumericDisplayValue nodes with
 * bShowStatModifier (Explosive +20.6%, gun secondary "increased by +X%", …).
 * Returns null when no StatModifier rows target the attribute.
 */
function resolveStatModifierDisplayValue(node, ctx, referenceFn) {
  if (!node || !ctx) return null;
  const reference = typeof referenceFn === "function" ? referenceFn : null;
  const key = reference
    ? reference(node.attributedef, "attribute") || String(node.attributedef || "").toLowerCase()
    : String(node.attributedef || "")
        .replace(/^attribute'/i, "")
        .replace(/'$/, "")
        .toLowerCase();
  if (!key) return null;
  const rows = (ctx.statModifiers?.modifiers || []).filter((row) => {
    const attr = reference
      ? reference(row.attributetomodify, "attribute")
      : String(row.attributetomodify || "")
          .replace(/^attribute'/i, "")
          .replace(/'$/, "")
          .toLowerCase();
    return attr === key;
  });
  if (!rows.length) return null;
  let scale = 1;
  let additive = 0;
  let sawScale = false;
  for (const row of rows) {
    const c = Number(row.modifiervalue?.constant);
    if (!Number.isFinite(c)) continue;
    if (/scalemultiply/i.test(String(row.modifiertype || ""))) {
      scale *= c;
      sawScale = true;
    } else {
      additive += c;
    }
  }
  const value = sawScale ? scale : additive;
  return Number.isFinite(value) ? value : null;
}

module.exports = { resolveStatModifierDisplayValue };
