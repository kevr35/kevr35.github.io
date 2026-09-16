(() => {
  const root = document.querySelector("[data-climbing-editor]");
  if (!root) return;

  const form = root.querySelector("[data-route-form]");
  const status = root.querySelector("[data-import-status]");
  const exportStatus = root.querySelector("[data-export-status]");
  const preview = root.querySelector("[data-markdown-preview]");
  const photoInput = root.querySelector("[data-route-photos]");
  const photoStatus = root.querySelector("[data-photo-status]");
  const saveButton = root.querySelector("[data-save-route]");
  const overwriteWrap = root.querySelector("[data-overwrite-wrap]");
  const locationPrompt = root.querySelector("[data-location-prompt]");
  const locationName = root.querySelector("[data-location-name]");
  const isLocalEditor = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const field = (name) => form.elements[name];
  const archetypeSource = root.parentElement.querySelector("[data-climbing-archetype]");
  const archetypeText = archetypeSource ? JSON.parse(archetypeSource.textContent) : "";
  const archetypeFields = [...(archetypeText.match(/^([A-Za-z_][A-Za-z0-9_]*):/gm) || [])].map((line) => line.replace(/:$/, ""));
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  const slugify = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const markdownFilename = (value) => `${slugify(String(value || "").replace(/\.md$/i, "")) || "climbing-route"}.md`;
  const text = (document, selectors) => selectors.map((selector) => document.querySelector(selector)?.content || document.querySelector(selector)?.textContent || "").find(Boolean) || "";
  const set = (name, value) => { if (value && field(name)) field(name).value = clean(value); };
  let importedCoordinates = null;
  let importedCragName = "";
  let importedLocationName = "";
  let importedStateName = "";
  let selectedPhotos = [];
  let originalFilename = "";

  const updatePreview = () => {
    const values = {
      title: JSON.stringify(clean(field("title").value)), date: new Date().toISOString(), climb_date: JSON.stringify(field("climb_date").value),
      crag: JSON.stringify(clean(field("crag").value)), wall: JSON.stringify(clean(field("wall").value)), discipline: JSON.stringify(field("discipline").value), setting: JSON.stringify(field("setting").value), grade: JSON.stringify(clean(field("grade").value)), ascent_type: JSON.stringify(clean(field("ascent_type").value)), mountain_project_url: JSON.stringify(clean(field("mountain_project_url").value)), youtube_url: JSON.stringify(clean(field("youtube_url").value)),
      thumbnail: JSON.stringify(selectedPhotos.length ? `route-images/${slugify(field("filename").value)}/${selectedPhotos[0].output}` : ""),
      photos: selectedPhotos.length ? ["photos:", ...selectedPhotos.map((photo) => `  - ${JSON.stringify(`route-images/${slugify(field("filename").value)}/${photo.output}`)}`)] : ["photos: []"],
      personal_note: JSON.stringify(clean(field("personal_note").value)), tags: ["tags:", "  - \"Climbing\""], draft: String(field("draft").checked),
    };
    const lines = ["---"];
    (archetypeFields.length ? archetypeFields : Object.keys(values)).forEach((name) => {
      if (name === "photos" || name === "tags") lines.push(...values[name]);
      else if (values[name] !== undefined) lines.push(`${name}: ${values[name]}`);
    });
    preview.value = lines.concat(["---", "", field("body").value, ""]).join("\n");
  };

  const saveLocally = async () => {
    if (!isLocalEditor) { exportStatus.textContent = "Direct saving is available only in the local editor."; return; }
    saveButton.disabled = true;
    try {
      const photos = [...photoInput.files].map((file, index) => ({ name: file.name, output: `${String(index + 1).padStart(2, "0")}.jpg` }));
      const photoData = photos.length ? await Promise.all([...photoInput.files].map((file, index) => new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve({ name: file.name, output: photos[index].output, data: reader.result }); reader.onerror = reject; reader.readAsDataURL(file); }))) : [];
      const response = await fetch("/api/climbing/routes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: markdownFilename(field("filename").value), original_filename: originalFilename || undefined, markdown: preview.value, overwrite: field("overwrite").checked, add_crag: field("add_crag").checked, crag_name: clean(field("crag").value), state_name: importedStateName, location_name: importedLocationName, parent: importedLocationName, coordinates: importedCoordinates, photos: photoData }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected the route.");
      exportStatus.textContent = `${result.path} saved. Hugo rebuilt the site.`;
      originalFilename = markdownFilename(field("filename").value);
    } catch (error) { exportStatus.textContent = `Could not save locally: ${error.message}`; }
    finally { saveButton.disabled = false; }
  };

  const checkLocationRegistry = async () => {
    locationPrompt.hidden = true;
    if (!isLocalEditor || !importedCoordinates || !importedCragName) return;
    const response = await fetch("/api/climbing/locations");
    if (!response.ok) return;
    const locations = await response.json();
    const knownCrag = locations.some((entry) => entry.level === "crag" && entry.name.toLowerCase() === importedCragName.toLowerCase());
    const knownState = locations.some((entry) => entry.level === "state" && entry.name.toLowerCase() === importedStateName.toLowerCase());
    const knownLocation = locations.some((entry) => entry.level === "location" && entry.name.toLowerCase() === importedLocationName.toLowerCase());
    if (!knownCrag || !knownLocation || !knownState) {
      locationName.textContent = `${importedStateName} / ${importedLocationName} / ${importedCragName}`;
      field("add_crag").checked = true;
      locationPrompt.hidden = false;
    }
  };

  const populateFromPage = (html, url) => {
    const document = new DOMParser().parseFromString(html, "text/html");
    const canonical = document.querySelector('link[rel="canonical"]')?.href || url;
    const heading = document.querySelector("#route-page h1");
    heading?.querySelectorAll("a, img").forEach((element) => element.remove());
    const title = clean(heading?.textContent) || text(document, ['meta[name="citation_title"]']) || document.title;
    const description = text(document, ['meta[property="og:description"]', 'meta[name="description"]']);
    const grade = text(document, ['meta[name="route_grade"]', '[class*="grade"]', '[class*="Grade"]']);
    const location = text(document, ['meta[name="area_name"]', '[class*="area"]', '[class*="Area"]']);
    const pageText = document.body?.textContent.replace(/\s+/g, " ") || "";
    const breadcrumb = [...document.querySelectorAll("#route-page .text-warm a[href*='/area/']")].map((link) => clean(link.textContent)).filter(Boolean);
    const hierarchy = breadcrumb.slice(1).map((name) => name.replace(/^The\s+/i, ""));
    importedStateName = clean(breadcrumb[0] || "");
    importedLocationName = hierarchy.shift() || "";
    importedCragName = clean(hierarchy.shift() || "");
    importedCoordinates = (pageText.match(/GPS:\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i) || []).slice(1);
    importedCoordinates = importedCoordinates.length === 2 ? { latitude: importedCoordinates[0], longitude: importedCoordinates[1] } : null;
    set("title", title); set("mountain_project_url", canonical); set("grade", grade || (pageText.match(/\b(V\d+(?:[+-])?|5\.\d+[a-d]?(?:[+-])?)\b/i) || [""])[1]);
    field("crag").value = clean(importedCragName || location); field("wall").value = clean(hierarchy.join(" / "));
    if (/Type:\s*Boulder/i.test(pageText)) field("discipline").value = "Boulder";
    else if (/Type:\s*Sport|5\.\d/i.test(`${grade} ${description}`)) field("discipline").value = "Sport";
    field("filename").value = slugify(title);
    checkLocationRegistry(); updatePreview();
  };

  root.querySelector("[data-fetch-mp]").addEventListener("click", async () => {
    const url = clean(root.querySelector("[data-mp-url]").value);
    if (!url) { status.textContent = "Enter a Mountain Project route URL first."; return; }
    status.textContent = "Fetching Mountain Project data...";
    try { const response = await fetch(url); if (!response.ok) throw new Error(`Mountain Project returned ${response.status}.`); populateFromPage(await response.text(), url); status.textContent = "Imported what the page exposed. Review every field before downloading."; }
    catch (error) { set("mountain_project_url", url); status.textContent = `Mountain Project blocked browser lookup: ${error.message}`; }
  });
  root.querySelector("[data-search-mp]").addEventListener("click", () => { const query = clean(root.querySelector("[data-mp-search]").value); if (query) window.open(`https://www.mountainproject.com/search?q=${encodeURIComponent(query)}`, "_blank", "noopener"); });

  const importResolvedTicks = async (csv, resolutions, button, tickStatus, panel) => {
    button.disabled = true;
    try {
      const response = await fetch("/api/climbing/import-ticks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ csv, resolutions, overwrite: root.querySelector("[data-tick-overwrite]").checked, fetch_gps: root.querySelector("[data-tick-fetch-gps]").checked }) });
      const result = await response.json(); if (!response.ok) throw new Error(result.error || "The local server rejected the tick list.");
      tickStatus.textContent = `${result.created.length} route${result.created.length === 1 ? "" : "s"} created, ${result.skipped.length} skipped, ${result.errors.length} failed.`; panel.hidden = true;
    } catch (error) { tickStatus.textContent = `Could not import the tick list: ${error.message}`; }
    finally { button.disabled = false; }
  };
  root.querySelector("[data-import-ticks]").addEventListener("click", async () => {
    const csv = root.querySelector("[data-tick-csv]").value; const button = root.querySelector("[data-import-ticks]"); const panel = root.querySelector("[data-tick-resolutions]"); const tickStatus = root.querySelector("[data-tick-status]");
    if (!csv.trim()) { tickStatus.textContent = "Paste the exported tick list CSV first."; return; }
    button.disabled = true;
    try {
      const response = await fetch("/api/climbing/preview-ticks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ csv }) });
      const previewResult = await response.json(); if (!response.ok) throw new Error(previewResult.error || "Could not inspect the tick list.");
      if (!previewResult.unresolved.length) return importResolvedTicks(csv, {}, button, tickStatus, panel);
      panel.hidden = false;
      panel.innerHTML = `<p>Choose the approved parent location and crag for each unresolved source hierarchy.</p>${previewResult.unresolved.map((item) => `<div class="climbing-editor__grid" data-tick-resolution="${escapeHtml(item.key)}"><p><strong>${escapeHtml(item.source_location)} / ${escapeHtml(item.source_crag)}</strong></p><label>Approved location<input data-resolution-location value="${escapeHtml(item.source_location)}"></label><label>Approved crag<input data-resolution-crag value="${escapeHtml(item.source_crag)}"></label></div>`).join("")}<button type="button" class="climbing-editor__button climbing-editor__button--local" data-apply-tick-resolutions>Continue</button>`;
      panel.querySelector("[data-apply-tick-resolutions]").addEventListener("click", () => { const resolutions = {}; panel.querySelectorAll("[data-tick-resolution]").forEach((entry) => { resolutions[entry.dataset.tickResolution] = { location: clean(entry.querySelector("[data-resolution-location]").value), crag: clean(entry.querySelector("[data-resolution-crag]").value) }; }); importResolvedTicks(csv, resolutions, button, tickStatus, panel); });
    } catch (error) { tickStatus.textContent = error.message; button.disabled = false; }
  });

  form.addEventListener("input", updatePreview);
  photoInput.addEventListener("change", () => { selectedPhotos = [...photoInput.files].map((file, index) => ({ name: file.name, output: `${String(index + 1).padStart(2, "0")}.jpg` })); photoStatus.textContent = `${selectedPhotos.length} photo${selectedPhotos.length === 1 ? "" : "s"} selected.`; updatePreview(); });
  form.addEventListener("submit", (event) => { event.preventDefault(); const blob = new Blob([preview.value], { type: "text/markdown;charset=utf-8" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${slugify(field("filename").value) || "climbing-route"}.md`; link.click(); URL.revokeObjectURL(link.href); });
  root.querySelector("[data-copy-route]").addEventListener("click", async () => { await navigator.clipboard.writeText(preview.value); exportStatus.textContent = "Markdown copied to the clipboard."; });
  saveButton.addEventListener("click", saveLocally);
  if (isLocalEditor) { saveButton.hidden = false; overwriteWrap.hidden = false; root.querySelector("[data-import-ticks]").hidden = false; root.querySelector("[data-tick-status]").textContent = ""; }
  updatePreview();
})();
