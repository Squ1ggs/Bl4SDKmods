"use strict";
(function (root) {
  const clone = value => JSON.parse(JSON.stringify(value));
  function clean(template, live) {
    if (!template || typeof template !== "object") return template;
    if (Array.isArray(template)) return template.map(clone);
    const out = clone(template);
    for (const key of ["sections", "actions"]) {
      if (!Array.isArray(template[key])) continue;
      const rows = Array.isArray(live?.[key]) ? live[key] : [];
      const id = row => key === "sections" ? row?.title : `${row?.action || ""}|${row?.label || ""}|${row?.type || ""}`;
      out[key] = template[key].map(approved => clean(approved, rows.find(row => id(row) === id(approved))));
    }
    // Runtime tuning contributes numeric sliders and checkboxes; choices and
    // section/action definitions always belong to the bundled schema.
    if (template.action === "tuning_apply" && !template.fields?.length) {
      out.fields = (live?.fields || []).filter(f => ["number", "checkbox"].includes(f?.type) && typeof f.key === "string").map(f => {
        const field = {};
        for (const key of ["key", "label", "type", "min", "max", "step", "default"]) if (key in f) field[key] = f[key];
        return field;
      });
    }
    return out;
  }
  function restrict(raw, schema) {
    if (!raw || typeof raw !== "object") return raw;
    if (!Array.isArray(schema?.tabs)) return { tabs: [] };
    const reviewed = new Map(schema.tabs.map(tab => [tab.id, tab]));
    const order = new Map(schema.tabs.map((tab, index) => [tab.id, index]));
    const tabs = (raw.tabs || []).flatMap(tab => reviewed.has(tab?.id) ? [clean(reviewed.get(tab.id), tab)] : []).sort((a, b) => order.get(a.id) - order.get(b.id));
    const result = { ...clone(schema), tabs };
    if (raw.lobby?.sections) result.lobby = { sections: raw.lobby.sections.flatMap(section => {
      const id = section?.tabId || section?.tab_id || section?.id;
      const tab = reviewed.get(id);
      return tab ? [{ tabId: id, label: tab.label }] : [];
    }) };
    return result;
  }
  if (typeof module !== "undefined") module.exports = restrict;
  else root.SQBT_RESTRICT_MANIFEST = restrict;
})(typeof window !== "undefined" ? window : globalThis);
