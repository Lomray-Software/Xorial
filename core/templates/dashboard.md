# Xorial Dashboard

```button
name ← Project
type link
action obsidian://open?vault=context&file=project-context
color default
```

```button
name 📋 Open Kanban
type link
action obsidian://open?vault=context&file=kanban
color blue
```

> **Required plugins** — click a name to open its install page in Obsidian:
> - [**Dataview**](obsidian://show-plugin?id=dataview) — powers all tables and queries on this dashboard
> - [**Kanban**](obsidian://show-plugin?id=obsidian-kanban) — powers the [[kanban]] board
> - [**Buttons**](obsidian://show-plugin?id=buttons) — powers all buttons on this page
> - [**Icon Folder**](obsidian://show-plugin?id=obsidian-icon-folder) — file and folder icons
> - [**Omnisearch**](obsidian://show-plugin?id=omnisearch) — full-text search across the vault (`Cmd+Shift+O`)
> - [**Timeline**](obsidian://show-plugin?id=obsidian-timeline) — timeline view for history files
> - [**Commander**](obsidian://show-plugin?id=commander) — custom ribbon/toolbar buttons

---

## Needs Attention

```dataviewjs
const statusFiles = app.vault.getFiles().filter(f => f.path.endsWith("status.json"));
const rows = [];
for (const file of statusFiles) {
  const raw = await dv.io.load(file.path);
  try {
    const s = JSON.parse(raw);
    if (!s.feature) continue;
    if (!["NEEDS_HUMAN_INPUT", "BLOCKED"].includes(s.status)) continue;
    const link = dv.fileLink(file.parent.path + "/" + file.parent.name, false, s.feature);
    rows.push([link, s.status, s.assigned_to ?? "", s.blocked_reason ?? ""]);
  } catch(e) {}
}
if (rows.length === 0) dv.paragraph("✓ Nothing needs your attention.");
else dv.table(["Feature", "Status", "Assigned", "Reason"], rows);
```

---

## Stats

```dataviewjs
const statusFiles = app.vault.getFiles().filter(f => f.path.endsWith("status.json"));
const counts = {};
for (const file of statusFiles) {
  const raw = await dv.io.load(file.path);
  try {
    const s = JSON.parse(raw);
    if (!s.feature) continue;
    const stage = s.stage ?? "unknown";
    counts[stage] = (counts[stage] ?? 0) + 1;
  } catch(e) {}
}
const order = ["planning", "implementation", "review", "done"];
const parts = [...order.filter(k => counts[k]).map(k => `**${k}**: ${counts[k]}`),
               ...Object.entries(counts).filter(([k]) => !order.includes(k)).map(([k,v]) => `${k}: ${v}`)];
dv.paragraph(parts.length ? parts.join(" · ") : "No features yet.");
```

---

## Recent Activity

```dataviewjs
const historyFiles = app.vault.getFiles()
  .filter(f => /\/history\/\d{4}-\d{2}-\d{2}\.md$/.test(f.path))
  .sort((a, b) => b.basename.localeCompare(a.basename));

const rows = [];
for (const file of historyFiles) {
  if (rows.length >= 5) break;
  const content = await dv.io.load(file.path);
  const entries = [...content.matchAll(/## (\d{2}:\d{2}) · ([\w-]+)[^\n]*\n[\s\S]*?\*\*Event:\*\* ([^\n]+)/g)];
  if (!entries.length) continue;
  const last = entries[entries.length - 1];
  const featureName = file.parent.parent.name;
  rows.push([
    dv.fileLink(file.parent.parent.path + "/" + featureName, false, featureName),
    file.basename,
    last[2],
    last[3]
  ]);
}
if (rows.length) dv.table(["Feature", "Date", "Role", "Last Event"], rows);
else dv.paragraph("No activity yet.");
```

---

## All Features

```dataviewjs
const files = app.vault.getFiles().filter(f => f.path.endsWith("status.json"));
const rows = [];
for (const file of files) {
  const content = await dv.io.load(file.path);
  try {
    const s = JSON.parse(content);
    if (!s.feature) continue;
    const link = dv.fileLink(file.parent.path + "/" + file.parent.name, false, s.feature);
    rows.push([
      link,
      s.type ?? "",
      Array.isArray(s.scope) ? s.scope.join(", ") : (s.scope ?? ""),
      s.stage ?? "",
      s.status ?? "",
      s.assigned_to ?? "",
    ]);
  } catch (e) {}
}
rows.sort((a, b) => {
  const order = ["implementation", "review", "planning", "done"];
  return (order.indexOf(a[3]) === -1 ? 99 : order.indexOf(a[3])) -
         (order.indexOf(b[3]) === -1 ? 99 : order.indexOf(b[3]));
});
dv.table(["Feature", "Type", "Scope", "Stage", "Status", "Assigned"], rows);
```
