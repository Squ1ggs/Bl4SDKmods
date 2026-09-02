"use strict";

const fs = require("fs");
const path = require("path");
const QRCode = require("qrcode");

const invite = "https://discord.gg/DqetrAK2sJ";
const qr = QRCode.create(invite, { errorCorrectionLevel: "H" });
const size = qr.modules.size;
const border = 4;
const viewSize = size + border * 2;

function inFinder(row, col) {
  return (
    (row <= 6 && col <= 6) ||
    (row <= 6 && col >= size - 7) ||
    (row >= size - 7 && col <= 6)
  );
}

const black = [];
const gradient = [];
for (let row = 0; row < size; row += 1) {
  for (let col = 0; col < size; col += 1) {
    if (!qr.modules.get(row, col)) continue;
    const rect = `<rect x="${col + border}" y="${row + border}" width="1" height="1"/>`;
    (inFinder(row, col) ? black : gradient).push(rect);
  }
}

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewSize} ${viewSize}" role="img" aria-labelledby="title desc" shape-rendering="crispEdges">
  <title id="title">Squ1ggs Discord invite QR code</title>
  <desc id="desc">Scans to ${invite}</desc>
  <defs>
    <linearGradient id="invite-gradient" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#79d8ed"/>
      <stop offset="0.52" stop-color="#aa94dc"/>
      <stop offset="1" stop-color="#db46cc"/>
    </linearGradient>
  </defs>
  <rect width="${viewSize}" height="${viewSize}" fill="#fff"/>
  <g fill="url(#invite-gradient)">${gradient.join("")}</g>
  <g fill="#050505">${black.join("")}</g>
</svg>
`;

const output = path.join(__dirname, "renderer", "assets", "discord-invite-qr.svg");
fs.writeFileSync(output, svg, "utf8");
console.log(`Wrote ${output} (${size}x${size} modules, H correction)`);
