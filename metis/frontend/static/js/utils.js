export const esc = (s) => String(s ?? "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
export const $ = (id) => document.getElementById(id);
