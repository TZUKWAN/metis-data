// Developer Mode (Ctrl+Shift+D) — shows debug drawer.
import { $ } from './utils.js';

export function toggleDebug() {
  let d = document.getElementById("debug-drawer");
  if (d) { d.remove(); return; }
  d = document.createElement("div");
  d.id = "debug-drawer";
  d.innerHTML = "<h4>Debug</h4><div id='debug-content'>Loading…</div>";
  document.body.appendChild(d);
  fetch("/api/providers").then(r => r.json()).then(p => {
    d.querySelector("#debug-content").innerHTML = p.slice(0, 10).map(x =>
      `<div class="event">${esc(x.provider_id)}: P${x.integration_level}</div>`).join("");
  });
}
