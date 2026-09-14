export async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok && j.error_code) throw new Error(`${j.error_code}: ${j.message}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return j;
}
