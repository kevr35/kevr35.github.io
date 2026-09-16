(() => {
  if (window.openClimbingRouteEditor) return;

  const fields = ["title", "climb_date", "crag", "wall", "discipline", "setting", "grade", "ascent_type", "mountain_project_url", "youtube_url", "personal_note"];
  const dialog = document.createElement("dialog");
  dialog.className = "climbing-route-dialog";
  dialog.innerHTML = `<form method="dialog" class="climbing-route-dialog__content">
    <h2 data-route-dialog-title>Edit route</h2>
    <div class="climbing-route-dialog__grid">
      <label>Route name<input name="title"></label>
      <label>Climb date<input name="climb_date" type="date"></label>
      <label>State / country<input name="inherited_state" readonly disabled></label>
      <label>Location<input name="inherited_location" readonly disabled></label>
      <label>Crag<input name="crag"></label>
      <label>Wall / sector<input name="wall"></label>
      <label>Discipline<select name="discipline"><option value="Boulder">Bouldering</option><option value="Sport">Sport</option></select></label>
      <label>Setting<select name="setting"><option value="Outdoor">Outdoor</option><option value="Indoor">Indoor</option></select></label>
      <label>Grade<input name="grade"></label>
      <label>Ascent type<input name="ascent_type"></label>
      <label>Mountain Project URL<input name="mountain_project_url" type="url"></label>
      <label>YouTube URL<input name="youtube_url" type="url"></label>
    </div>
    <label>Personal note<textarea name="personal_note" rows="4"></textarea></label>
    <label>Route report / beta<textarea name="body" rows="6"></textarea></label>
    <label class="climbing-route-dialog__draft"><input name="draft" type="checkbox"> Keep as draft</label>
    <p data-route-dialog-status role="status"></p>
    <div class="climbing-route-dialog__actions"><button type="button" data-route-dialog-cancel>Cancel</button><button type="button" data-route-dialog-save disabled>Save and rebuild</button></div>
  </form>`;
  document.body.append(dialog);

  const form = dialog.querySelector("form");
  const title = dialog.querySelector("[data-route-dialog-title]");
  const status = dialog.querySelector("[data-route-dialog-status]");
  const save = dialog.querySelector("[data-route-dialog-save]");
  let filename = "";
  let originalMarkdown = "";
  let savedFormState = "";
  let originalFieldValues = {};

  const frontmatterMatch = (markdown) => markdown.match(/^(---\r?\n)([\s\S]*?)(\r?\n---)([\s\S]*)$/);
  const readField = (frontmatter, name) => {
    const match = frontmatter.match(new RegExp(`^${name}:\\s*(.*)$`, "m"));
    if (!match) return "";
    const value = match[1].trim();
    if (value.startsWith('"')) {
      try { return JSON.parse(value); } catch { return value.slice(1, -1); }
    }
    return value;
  };
  const setField = (frontmatter, name, value, raw = false) => {
    const line = `${name}: ${raw ? value : JSON.stringify(String(value || ""))}`;
    const pattern = new RegExp(`^${name}:.*$`, "m");
    return pattern.test(frontmatter) ? frontmatter.replace(pattern, line) : `${frontmatter}\n${line}`;
  };
  const removeField = (frontmatter, name) => frontmatter.replace(new RegExp(`^${name}:.*(?:\\r?\\n|$)`, "m"), "");
  const state = () => JSON.stringify(Object.fromEntries([...new FormData(form).entries()].concat([["draft", form.elements.draft.checked]])));
  const close = () => {
    dialog.close();
    filename = "";
    originalMarkdown = "";
    status.textContent = "";
  };
  const refreshSaveState = () => {
    const changed = state() !== savedFormState;
    save.disabled = !changed;
    status.textContent = changed ? "Unsaved changes." : "";
    form.querySelectorAll("input, select, textarea").forEach((control) => {
      if (control.disabled) return;
      const value = control.type === "checkbox" ? String(control.checked) : control.value;
      control.classList.toggle("climbing-route-dialog__field--changed", value !== originalFieldValues[control.name]);
      control.closest("label")?.classList.toggle("climbing-route-dialog__label--changed", value !== originalFieldValues[control.name]);
    });
  };
  const buildMarkdown = () => {
    const match = frontmatterMatch(originalMarkdown);
    if (!match) throw new Error("This route does not contain valid YAML frontmatter.");
    let frontmatter = match[2];
    ["state", "location", "region", "area"].forEach((name) => { frontmatter = removeField(frontmatter, name); });
    fields.forEach((name) => { frontmatter = setField(frontmatter, name, form.elements[name].value); });
    frontmatter = setField(frontmatter, "draft", String(form.elements.draft.checked), true);
    return `${match[1]}${frontmatter}${match[3]}\n\n${form.elements.body.value.trim()}\n`;
  };

  dialog.querySelector("[data-route-dialog-cancel]").addEventListener("click", close);
  dialog.addEventListener("click", (event) => { if (event.target === dialog) close(); });
  form.addEventListener("input", refreshSaveState);
  form.addEventListener("change", refreshSaveState);
  save.addEventListener("click", async () => {
    let markdown;
    try { markdown = buildMarkdown(); } catch (error) { status.textContent = error.message; return; }
    save.disabled = true;
    status.textContent = "Saving route and rebuilding the site...";
    try {
      const response = await fetch("/api/climbing/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, original_filename: filename, markdown, overwrite: true }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save this route.");
      status.textContent = `${result.path} saved. Refreshing...`;
      window.location.reload();
    } catch (error) {
      status.textContent = `Could not save route: ${error.message}`;
      save.disabled = false;
    }
  });

  window.openClimbingRouteEditor = async (routeFilename, routeTitle = routeFilename) => {
    filename = routeFilename;
    title.textContent = `Edit ${routeTitle}`;
    status.textContent = "Loading route...";
    save.disabled = true;
    dialog.showModal();
    try {
      const response = await fetch(`/api/climbing/routes/${encodeURIComponent(filename)}/markdown`);
      const route = await response.json();
      if (!response.ok) throw new Error(route.error || "Could not load this route.");
      originalMarkdown = route.markdown;
      const match = frontmatterMatch(originalMarkdown);
      if (!match) throw new Error("This route does not contain valid YAML frontmatter.");
      fields.forEach((name) => { form.elements[name].value = readField(match[2], name); });
      const locationsResponse = await fetch("/api/climbing/locations");
      if (locationsResponse.ok) {
        const locations = await locationsResponse.json();
        const crag = locations.find((entry) => entry.level === "crag" && entry.name.toLowerCase() === form.elements.crag.value.toLowerCase());
        const location = locations.find((entry) => entry.name.toLowerCase() === (crag?.parent || "").toLowerCase());
        form.elements.inherited_location.value = location?.name || "";
        const state = locations.find((entry) => entry.name.toLowerCase() === (location?.parent || "").toLowerCase());
        form.elements.inherited_state.value = state?.name || "";
      }
      form.elements.body.value = match[4].trim();
      form.elements.draft.checked = readField(match[2], "draft") === "true";
      savedFormState = state();
      originalFieldValues = Object.fromEntries([...form.elements].filter((control) => control.name).map((control) => [control.name, control.type === "checkbox" ? String(control.checked) : control.value]));
      refreshSaveState();
      status.textContent = "";
      form.elements.title.focus({ preventScroll: true });
    } catch (error) {
      status.textContent = `Could not load route: ${error.message}`;
    }
  };
})();
