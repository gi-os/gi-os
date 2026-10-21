// Rebuilds the sponsor thanks in three places from the live GitHub Sponsors list:
//   README.md                  the block between <!-- Sponsors --> markers
//   images/bright-sponsors.svg the banner every Bright app's README embeds
//   sponsors.json              the list brightmarket.gzl.dev reads
// Run by .github/workflows/sponsors.yml; `node sponsors.js preview name1 name2` renders locally.

const fs = require('fs');

const SPONSOR_URL = 'https://github.com/sponsors/gi-os';

const xml = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function readmeBlock(sponsors) {
  if (!sponsors.length) {
    return `<p align="center">No sponsors yet. <a href="${SPONSOR_URL}">Be the first →</a></p>`;
  }
  const faces = sponsors
    .map(s => `<a href="https://github.com/${s}"><img src="https://github.com/${s}.png?size=64" width="48" height="48" alt="${s}" title="${s}" /></a>`)
    .join('\n');
  return `<p align="center">\n${faces}\n</p>\n\n` +
    `<p align="center">Thank you, ${sponsors.map(s => `<a href="https://github.com/${s}">@${s}</a>`).join(', ')}, ` +
    `and everyone who sponsors quietly.<br />Every Bright app is free because of you. <a href="${SPONSOR_URL}">Sponsor →</a></p>`;
}

// Light Phone look: black screen, one column of words, nothing else.
function banner(sponsors) {
  const names = sponsors.length ? sponsors : ['you, maybe?'];
  const shown = names.slice(0, 4);
  const more = names.length - shown.length;
  if (more > 0) shown.push(`+ ${more} more`);

  const top = 92, step = 34;
  const height = top + shown.length * step + 64;
  const lines = shown
    .map((n, i) => `  <text x="48" y="${top + 8 + i * step}" class="name${i === shown.length - 1 && more > 0 ? ' dim' : ''}">${xml(n)}</text>`)
    .join('\n');

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 ${height}" width="800" height="${height}" role="img" aria-label="Thank you to my sponsors: ${xml(names.join(', '))}">
  <style>
    text { font-family: "Public Sans", "Helvetica Neue", Helvetica, Arial, sans-serif; fill: #FFFFFF; }
    .head { font-size: 40px; font-weight: 300; letter-spacing: -0.5px; }
    .name { font-size: 26px; font-weight: 400; }
    .dim  { fill: #8C8C8C; }
    .foot { font-size: 15px; fill: #8C8C8C; letter-spacing: 0.5px; }
    .dot  { animation: pulse 2.4s ease-in-out infinite; }
    @keyframes pulse { 50% { opacity: .25; } }
  </style>
  <rect width="800" height="${height}" rx="18" fill="#000000"/>
  <circle class="dot" cx="752" cy="50" r="6" fill="#FFFFFF"/>
  <text x="48" y="62" class="head">thank you</text>
${lines}
  <text x="48" y="${height - 30}" class="foot">this app is free because of my sponsors · github.com/sponsors/gi-os</text>
</svg>
`;
}

function write(sponsors) {
  const readme = fs.readFileSync('README.md', 'utf8');
  fs.writeFileSync('README.md', readme.replace(
    /(<!-- Sponsors -->\n)[\s\S]*?(<!-- \/Sponsors -->)/,
    (_, open, close) => `${open}${readmeBlock(sponsors)}\n${close}`));
  fs.writeFileSync('images/bright-sponsors.svg', banner(sponsors));
  fs.writeFileSync('sponsors.json', JSON.stringify({ sponsors }, null, 2) + '\n');
}

module.exports = async ({ github, context }) => {
  // Public sponsors only; private ones stay private.
  const { user } = await github.graphql(`
    query($login: String!) {
      user(login: $login) {
        sponsors(first: 100) { nodes { ... on User { login } ... on Organization { login } } }
      }
    }`, { login: context.repo.owner });
  write(user.sponsors.nodes.map(n => n.login).filter(Boolean));
};

if (require.main === module && process.argv[2] === 'preview') {
  process.stdout.write(banner(process.argv.slice(3)));
}
