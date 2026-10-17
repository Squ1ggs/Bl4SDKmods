/**
 * Bump EXE patch (1.3.x) + matching mod patch (3.10.x), update pack output dir + changelogs.
 * Usage: node scripts/bump_version.cjs [optional note]
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const pkgPath = path.join(root, "package.json");
const resModPath = path.join(root, "resources", "Squ1ggsBoostingTools", "_mod_version.py");
const resClPath = path.join(root, "resources", "Squ1ggsBoostingTools", "CHANGELOG.md");
const steamModPath =
  resModPath;

const args = process.argv.slice(2);
function option(name) {
  const i = args.indexOf(name);
  return i >= 0 ? String(args[i + 1] || "").trim() : "";
}
const targetExe = option("--exe");
const targetMod = option("--mod");
const noteArgs = args.filter((arg, index) => {
  if (arg === "--exe" || arg === "--mod") return false;
  if (index > 0 && (args[index - 1] === "--exe" || args[index - 1] === "--mod")) return false;
  return true;
});
const note =
  String(noteArgs.join(" ") || "").trim() ||
  "Local pack bump (see prior chat / editor fixes).";

function bumpPatch(semver) {
  const m = String(semver || "").trim().match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!m) throw new Error("Bad semver: " + semver);
  return `${m[1]}.${m[2]}.${Number(m[3]) + 1}`;
}

function writeModVersion(filePath, version) {
  const parts = version.split(".").map((n) => Number(n));
  const body =
    '"""Single source of truth for the Squ1ggsBoostingTools package version."""\n\n' +
    `__version__: str = "${version}"\n\n` +
    `__version_info__: tuple[int, int, int] = (${parts[0]}, ${parts[1]}, ${parts[2]})\n`;
  fs.writeFileSync(filePath, body, "utf8");
}

const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
const oldExe = String(pkg.version || "1.3.0");
const newExe = targetExe || bumpPatch(oldExe);

let oldMod = "3.10.0";
try {
  const raw = fs.readFileSync(resModPath, "utf8");
  const m = raw.match(/__version__:\s*str\s*=\s*"([^"]+)"/);
  if (m) oldMod = m[1];
} catch (_) {}
const newMod = targetMod || bumpPatch(oldMod);
if ((!targetExe || !targetMod) && oldExe.split(".")[2] !== oldMod.split(".")[2]) {
  throw new Error("Development EXE/mod versions differ. Choose an explicit public pair with --exe and --mod before packing.");
}
if (!/^1\.3\.\d+$/.test(newExe) || !/^3\.10\.\d+$/.test(newMod)) {
  throw new Error(`Bad target pair: EXE ${newExe} / mod ${newMod}`);
}

pkg.version = newExe;
if (!pkg.build) pkg.build = {};
if (!pkg.build.directories) pkg.build.directories = {};
pkg.build.directories.output = `../dist_squ1ggs_boosting_tools_native_bl4_${newExe}_mod${newMod}`;
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n", "utf8");

const lockPath = path.join(root, "package-lock.json");
if (fs.existsSync(lockPath)) {
  const lock = JSON.parse(fs.readFileSync(lockPath, "utf8"));
  lock.version = newExe;
  if (lock.packages?.[""]) lock.packages[""].version = newExe;
  fs.writeFileSync(lockPath, JSON.stringify(lock, null, 2) + "\n", "utf8");
}
// The reviewed menu is also used offline and owns the displayed mod version.
for (const relative of ["offline_manifest.json", "resources/Squ1ggsBoostingTools/data/release_native_manifest.json"]) {
  const file = path.join(root, relative);
  const manifest = JSON.parse(fs.readFileSync(file, "utf8"));
  manifest.version = newMod;
  fs.writeFileSync(file, JSON.stringify(manifest, null, 2) + "\n", "utf8");
}
const schemaPath = path.join(root, "renderer/release_ui_schema.js");
const schema = require(schemaPath);
schema.version = newMod;
fs.writeFileSync(schemaPath,
  '"use strict";\nconst SQBT_RELEASE_UI_SCHEMA = ' + JSON.stringify(schema) + ';\n' +
  'if (typeof module !== "undefined") module.exports = SQBT_RELEASE_UI_SCHEMA;\n' +
  'else window.SQBT_RELEASE_UI_SCHEMA = SQBT_RELEASE_UI_SCHEMA;\n', "utf8");

writeModVersion(resModPath, newMod);
try {
  writeModVersion(steamModPath, newMod);
} catch (e) {
  console.warn("Steam _mod_version.py not updated:", e.message);
}

const steamClPath =
  resClPath;

function prependChangelog(filePath, exeVer, modVer, noteText) {
  if (!fs.existsSync(filePath)) return;
  let cl = fs.readFileSync(filePath, "utf8");
  const entry = `## ${modVer} / EXE ${exeVer}\n- ${noteText}\n\n`;
  if (cl.includes(`## ${modVer} / EXE ${exeVer}`)) return;
  const header = `# Changelog\n\n`;
  if (/^# Changelog\s*\n/.test(cl)) {
    cl = cl.replace(/^# Changelog\s*\n+/, header + entry);
  } else {
    cl = header + entry + cl;
  }
  fs.writeFileSync(filePath, cl, "utf8");
}

/* Steam sdk_mods is the sync source — write changelog there so pack sync keeps it. */
prependChangelog(steamClPath, newExe, newMod, note);
prependChangelog(resClPath, newExe, newMod, note);

const releasePath = path.join(root, "README_RELEASE.md");
const release =
  `# Squ1ggs Boosting Tools — EXE ${newExe} · mod ${newMod}\n\n` +
  `Local test pack.\n\n` +
  `## What's new (${newExe})\n\n` +
  `- ${note}\n\n` +
  `## Run / pack\n\n` +
  `- Dev: \`npm start\` in this folder\n` +
  `- Pack next: double-click \`PACK_NEXT.bat\` (bumps version then packs)\n` +
  `- EXE: \`..\\dist_squ1ggs_boosting_tools_native_bl4_${newExe}_mod${newMod}\\win-unpacked\\Squ1ggsBoostingTools.exe\`\n`;
fs.writeFileSync(releasePath, release, "utf8");

const readmePath = path.join(root, "README.md");
if (fs.existsSync(readmePath)) {
  const readme = fs.readFileSync(readmePath, "utf8").replace(
    /\*\*EXE [\d.]+ \/ mod [\d.]+\*\*/,
    `**EXE ${newExe} / mod ${newMod}**`,
  );
  fs.writeFileSync(readmePath, readme, "utf8");
}

console.log(`Bumped EXE ${oldExe} → ${newExe}`);
console.log(`Bumped mod ${oldMod} → ${newMod}`);
console.log(`Output dir: ${pkg.build.directories.output}`);
