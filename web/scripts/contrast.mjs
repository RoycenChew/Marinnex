/** WCAG contrast for the token pairs that carry text or meaning. */
const hex = (h) => { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const L = (h) => { const [r, g, b] = hex(h); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
const ratio = (a, b) => { const [x, y] = [L(a), L(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

const T = {
  brand600: '#0d7291', brand700: '#08627a', brand300: '#78cade', brand400: '#3aabc6',
  slate100: '#f1f5f9', slate400: '#94a3b8', slate500: '#64748b', slate600: '#475569',
  slate800: '#1e293b', slate900: '#0f172a', slate950: '#020617', white: '#ffffff',
  success600: '#27865a', success500: '#2f9e6c', warning600: '#96620f', warning500: '#d4922a',
  danger600: '#dc2626', danger500: '#ef4444',
  mExact: '#27865a', mNorm: '#4f46e5', mDeriv: '#7c5cd6', mFuzzy: '#96620f', mNot: '#dc2626', mMiss: '#6b7a8d',
  dExact: '#4ec08a', dNorm: '#8b9cf8', dDeriv: '#b49df0', dFuzzy: '#e0ad5c', dNot: '#f28b8b', dMiss: '#7b8a9c',
};

const rows = [
  ['LIGHT  body text', T.slate900, T.white, 4.5],
  ['LIGHT  secondary', T.slate600, T.white, 4.5],
  ['LIGHT  tertiary', T.slate500, T.white, 4.5],
  ['LIGHT  brand text', T.brand700, T.white, 4.5],
  ['LIGHT  button label', T.white, T.brand600, 4.5],
  ['LIGHT  success', T.success600, T.white, 4.5],
  ['LIGHT  warning', T.warning600, T.white, 4.5],
  ['LIGHT  danger', T.danger600, T.white, 4.5],
  ['LIGHT  match exact', T.mExact, T.white, 3.0],
  ['LIGHT  match normalized', T.mNorm, T.white, 3.0],
  ['LIGHT  match derived', T.mDeriv, T.white, 3.0],
  ['LIGHT  match fuzzy', T.mFuzzy, T.white, 3.0],
  ['LIGHT  match not_found', T.mNot, T.white, 3.0],
  ['LIGHT  match missing', T.mMiss, T.white, 3.0],
  ['DARK   body text', T.slate100, T.slate900, 4.5],
  ['DARK   secondary', T.slate400, T.slate900, 4.5],
  ['DARK   brand text', T.brand300, T.slate900, 4.5],
  ['DARK   button label', T.white, '#0d7291', 4.5],
  ['DARK   match exact', T.dExact, T.slate900, 3.0],
  ['DARK   match normalized', T.dNorm, T.slate900, 3.0],
  ['DARK   match derived', T.dDeriv, T.slate900, 3.0],
  ['DARK   match fuzzy', T.dFuzzy, T.slate900, 3.0],
  ['DARK   match not_found', T.dNot, T.slate900, 3.0],
  ['DARK   match missing', T.dMiss, T.slate900, 3.0],
];

let fails = 0;
for (const [name, fg, bg, min] of rows) {
  const r = ratio(fg, bg);
  const ok = r >= min;
  if (!ok) fails++;
  console.log(`${ok ? 'pass' : 'FAIL'}  ${name.padEnd(24)} ${r.toFixed(2)}:1  (needs ${min})`);
}
console.log(fails ? `\n${fails} below target` : '\nall pass');
