/* Kleine DOM-Helfer, von allen Modulen genutzt. */
export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => document.querySelectorAll(sel);

export function esc(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
