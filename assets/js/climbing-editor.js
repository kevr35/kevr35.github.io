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
  const archetypeFields = [...(archetypeText.match(/^([A-Za-z_][A-Za-z0-9_]*):/gm) || [])]
    .map((line) => line.replace(/:$/, ""));
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
  const slugify = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const markdownFilename = (value) => `${slugify(String(value || "").replace(/\.md$/i, "")) || "climbing-route"}.md`;
  const readPhoto = (file, index) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve({ name: file.name, output: `${String(index + 1).padStart(2, "0")}.jpg`, data: reader.result }));
    reader.addEventListener("error", reject);
    reader.readAsDataURL(file);
  });
  let importedCoordinates = null;
  let importedCragName = "";
  let importedLocationName = "";
  let importedStateName = "";
  let selectedPhotos = [];
  let originalFilename = "";
  const text = (document, selectors) => selectors.map((selector) => document.querySelector(selector)?.content || document.querySelector(selector)?.textContent || "").find(Boolean) || "";
  const set = (name, value) => { if (value) field(name).value = clean(value); };

  const updatePreview = () => {
    const values = {
      title: JSON.stringify(clean(field("title").value)),
      date: new Date().toISOString(),
      climb_date: JSON.stringify(field("climb_date").value),
      crag: JSON.stringify(clean(field("crag").value)),
      wall: JSON.stringify(clean(field("wall").value)),
      discipline: JSON.stringify(field("discipline").value),
      setting: JSON.stringify(field("setting").value),
      grade: JSON.stringify(clean(field("grade").value)),
      ascent_type: JSON.stringify(clean(field("ascent_type").value)),
      mountain_project_url: JSON.stringify(clean(field("mountain_project_url").value)),
      youtube_url: JSON.stringify(clean(field("youtube_url").value)),
      thumbnail: JSON.stringify(selectedPhotos.length ? `route-images/${slugify(field("filename").value)}/${selectedPhotos[0].output}` : ""),
      photos: selectedPhotos.length ? ["photos:", ...selectedPhotos.map((photo) => `  - ${JSON.stringify(`route-images/${slugify(field("filename").value)}/${photo.output}`)}`)] : ["photos: []"],
      personal_note: JSON.stringify(clean(field("personal_note").value)),
      tags: ["tags:", "  - \"Climbing\""],
      draft: String(field("draft").checked),
    };
    const lines = ["---"];
    (archetypeFields.length ? archetypeFields : Object.keys(values)).forEach((name) => {
      if (name === "photos" || name === "tags") lines.push(...values[name]);
      else if (values[name] !== undefined) lines.push(`${name}: ${values[name]}`);
    });
    lines.push("---", "", field("body").value, "");
    preview.value = lines.join("\n");
  };

  const saveLocally = async () => {
    if (!isLocalEditor) {
      exportStatus.textContent = "Direct saving is available only in the local editor. Run python tools/site_editor.py and open http://127.0.0.1:8000/admin/climbing/.";
      return;
    }
    saveButton.disabled = true;
    exportStatus.textContent = "Saving route to content/climbing/...";
    try {
      const photos = [...photoInput.files].length ? await Promise.all([...photoInput.files].map(readPhoto)) : [];
      const response = await fetch("/api/climbing/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: markdownFilename(field("filename").value),
          original_filename: originalFilename || undefined,
          markdown: preview.value,
          overwrite: field("overwrite").checked,
          add_crag: field("add_crag").checked,
          crag_name: clean(field("crag").value),
          state_name: importedStateName,
          location_name: importedLocationName,
          parent: importedLocationName,
          coordinates: importedCoordinates,
          photos,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected the route.");
      exportStatus.textContent = `${result.path} saved. Hugo rebuilt the site.`;
      originalFilename = markdownFilename(field("filename").value);
    } catch (error) {
      exportStatus.textContent = `Could not save locally: ${error.message}`;
    } finally {
      saveButton.disabled = false;
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
    const pageType = pageText.match(/\bType:\s*(Boulder|Sport)\b/i)?.[1] || "";
    const pageGrade = pageText.match(/\b(V\d+(?:[+-])?|5\.\d+[a-d]?(?:[+-])?)\b/i)?.[1] || "";
    const breadcrumbName = (link) => {
      const visibleName = clean(link.textContent);
      if (!/[.…]|\.\.\./.test(visibleName)) return visibleName;
      const segments = new URL(link.href, window.location.href).pathname.split("/").filter(Boolean);
      const slug = decodeURIComponent(segments[segments.length - 1] || "");
      return slug.replace(/[-_]+/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
    };
    const breadcrumb = [...document.querySelectorAll("#route-page .text-warm a[href*='/area/']")]
      .map(breadcrumbName)
      .filter(Boolean);
    const hierarchy = breadcrumb.slice(1).map((name) => name.replace(/^The\s+/i, ""));
    const breadcrumbLocation = hierarchy.shift() || "";
    const breadcrumbCrag = hierarchy.shift() || "";
    const breadcrumbWall = hierarchy.join(" / ");
    const coordinates = pageText.match(/GPS:\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i);
    importedCoordinates = coordinates ? { latitude: coordinates[1], longitude: coordinates[2] } : null;
    importedCragName = clean(breadcrumbCrag || field("crag").value);
    importedStateName = clean(breadcrumb[0] || "");
    importedLocationName = breadcrumbLocation;
    set("title", title);
    set("mountain_project_url", canonical);
    set("grade", grade || pageGrade);
    field("crag").value = clean(breadcrumbCrag || location);
    field("wall").value = clean(breadcrumbWall);
    if (pageType) field("discipline").value = pageType;
    else if (/sport|5\.\d/i.test(`${grade} ${description}`)) field("discipline").value = "Sport";
    field("filename").value = slugify(title);
    checkLocationRegistry();
    updatePreview();
  };

  const checkLocationRegistry = async () => {
    locationPrompt.hidden = true;
    if (!isLocalEditor || !importedCoordinates || !importedCragName) return;
    try {
      const response = await fetch("/api/climbing/locations");
      if (!response.ok) return;
      const locations = await response.json();
        const knownCrag = locations.some((location) => location.level === "crag" && location.name.toLowerCase() === importedCragName.toLowerCase());
        const knownState = locations.some((location) => location.level === "state" && location.name.toLowerCase() === importedStateName.toLowerCase());
        const knownLocation = locations.some((location) => location.level === "location" && location.name.toLowerCase() === importedLocationName.toLowerCase());
        if (!knownCrag || !knownLocation || !knownState) {
          locationName.textContent = `${importedStateName} / ${importedLocationName} / ${importedCragName}`;
        field("add_crag").checked = true;
        locationPrompt.hidden = false;
      }
    } catch {
      // The hosted editor has no registry endpoint; manual route export still works.
    }
  };

  const fetchMountainProject = async () => {
    const url = clean(root.querySelector("[data-mp-url]").value);
    if (!url) {
      status.textContent = "Enter a Mountain Project route URL first.";
      return;
    }
    importedCoordinates = null;
    importedCragName = "";
    originalFilename = "";
    locationPrompt.hidden = true;
    root.querySelector("[data-mp-url]").value = url;
    status.textContent = "Fetching Mountain Project data...";
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Mountain Project returned ${response.status}.`);
      populateFromPage(await response.text(), url);
      status.textContent = "Imported what the page exposed. Review every field before downloading.";
    } catch (error) {
      set("mountain_project_url", url);
      status.textContent = `Mountain Project blocked browser lookup: ${error.message} You can still fill the form manually, or open search in a new tab.`;
    }
  };

  root.querySelector("[data-fetch-mp]").addEventListener("click", fetchMountainProject);
  const searchMountainProject = () => {
    const query = clean(root.querySelector("[data-mp-search]").value);
    if (query) window.open(`https://www.mountainproject.com/search?q=${encodeURIComponent(query)}`, "_blank", "noopener");
    else status.textContent = "Enter a route or crag name to search Mountain Project.";
  };
  root.querySelector("[data-search-mp]").addEventListener("click", searchMountainProject);
  root.querySelector("[data-mp-search]").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchMountainProject();
    }
  });

  const importTicks = async () => {
    const csv = root.querySelector("[data-tick-csv]").value;
    const tickStatus = root.querySelector("[data-tick-status]");
    const tickButton = root.querySelector("[data-import-ticks]");
    const resolutionPanel = root.querySelector("[data-tick-resolutions]");
    if (!csv.trim()) {
      tickStatus.textContent = "Paste the exported tick list CSV first.";
      return;
    }
    tickButton.disabled = true;
    tickStatus.textContent = "Checking imported locations against your existing hierarchy...";
    try {
      const previewResponse = await fetch("/api/climbing/preview-ticks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv }),
      });
      const preview = await previewResponse.json();
      if (!previewResponse.ok) throw new Error(preview.error || "The local server rejected the tick list.");
      if (preview.unresolved.length) {
        resolutionPanel.hidden = false;
        resolutionPanel.innerHTML = `<p>Choose where these new source locations belong. These choices will be reused for future imports.</p>${preview.unresolved.map((item) => `<div class="climbing-editor__grid" data-tick-resolution="${escapeHtml(item.key)}"><p><strong>${escapeHtml(item.source_location)} / ${escapeHtml(item.source_crag)}</strong> (${Number(item.routes) || 0} route${item.routes === 1 ? "" : "s"})</p><label>Standard location<input data-resolution-location value="${escapeHtml(item.source_location)}" list="climbing-locations"></label><label>Standard crag<input data-resolution-crag value="${escapeHtml(item.source_crag)}" list="climbing-crags"></label></div>`).join("")}<div class="climbing-editor__actions"><button type="button" class="climbing-editor__button climbing-editor__button--local" data-apply-tick-resolutions>Save choices and import</button></div>`;
        tickStatus.textContent = `${preview.matched} route${preview.matched === 1 ? "" : "s"} matched the current structure. Resolve the entries below to continue.`;
        resolutionPanel.querySelector("[data-apply-tick-resolutions]").addEventListener("click", () => {
          const resolutions = {};
          resolutionPanel.querySelectorAll("[data-tick-resolution]").forEach((entry) => {
            resolutions[entry.dataset.tickResolution] = {
              location: clean(entry.querySelector("[data-resolution-location]").value),
              crag: clean(entry.querySelector("[data-resolution-crag]").value),
            };
          });
          importResolvedTicks(csv, resolutions, tickButton, tickStatus, resolutionPanel);
        });
        return;
      }
      importResolvedTicks(csv, {}, tickButton, tickStatus, resolutionPanel);
    } catch (error) {
      tickStatus.textContent = `Could not inspect the tick list: ${error.message}`;
    } finally {
      tickButton.disabled = false;
    }
  };

  const importResolvedTicks = async (csv, resolutions, tickButton, tickStatus, resolutionPanel) => {
    tickButton.disabled = true;
    tickStatus.textContent = "Importing routes and rebuilding the site. This can take a while for large tick lists...";
    try {
      const response = await fetch("/api/climbing/import-ticks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv,
          resolutions,
          overwrite: root.querySelector("[data-tick-overwrite]").checked,
          fetch_gps: root.querySelector("[data-tick-fetch-gps]").checked,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected the tick list.");
      const parts = [`${result.created.length} route${result.created.length === 1 ? "" : "s"} created`];
      if (result.skipped.length) parts.push(`${result.skipped.length} already existed`);
      if (result.errors.length) parts.push(`${result.errors.length} failed: ${result.errors.join("; ")}`);
      tickStatus.textContent = `${parts.join(", ")}. Review the new files before committing.`;
      resolutionPanel.hidden = true;
      resolutionPanel.innerHTML = "";
    } catch (error) {
      tickStatus.textContent = `Could not import the tick list: ${error.message}`;
    } finally {
      tickButton.disabled = false;
    }
  };
  const importTicksButton = root.querySelector("[data-import-ticks]");
  importTicksButton.addEventListener("click", importTicks);
  if (isLocalEditor) {
    importTicksButton.hidden = false;
    importTicksButton.disabled = false;
    root.querySelector("[data-tick-status]").textContent = "";
  }

  const rebuildLocations = async () => {
    const rebuildStatus = root.querySelector("[data-rebuild-status]");
    const rebuildButton = root.querySelector("[data-rebuild-locations-button]");
    rebuildButton.disabled = true;
    rebuildStatus.textContent = "Scanning routes and rebuilding the site...";
    try {
      const response = await fetch("/api/climbing/rebuild-locations", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected the rebuild.");
      const parts = [`${result.added.length} location${result.added.length === 1 ? "" : "s"} added`];
      if (result.failed.length) parts.push(`${result.failed.length} could not be geolocated: ${result.failed.join(", ")}`);
      rebuildStatus.textContent = `${parts.join(", ")}.`;
    } catch (error) {
      rebuildStatus.textContent = `Could not rebuild locations: ${error.message}`;
    } finally {
      rebuildButton.disabled = false;
    }
  };
  const rebuildLocationsButton = root.querySelector("[data-rebuild-locations-button]");
  rebuildLocationsButton.addEventListener("click", rebuildLocations);
  if (isLocalEditor) {
    rebuildLocationsButton.hidden = false;
    rebuildLocationsButton.disabled = false;
  }
  form.addEventListener("input", updatePreview);
  photoInput.addEventListener("change", () => {
    selectedPhotos = [...photoInput.files].map((file, index) => ({ name: file.name, output: `${String(index + 1).padStart(2, "0")}.jpg` }));
    photoStatus.textContent = selectedPhotos.length ? `${selectedPhotos.length} photo${selectedPhotos.length === 1 ? "" : "s"} selected. The local editor will resize and copy them when you save.` : "";
    updatePreview();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const blob = new Blob([preview.value], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${slugify(field("filename").value) || "climbing-route"}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
    exportStatus.textContent = "Markdown downloaded. Move it into content/climbing/ and review it before committing.";
  });
  root.querySelector("[data-copy-route]").addEventListener("click", async () => {
    await navigator.clipboard.writeText(preview.value);
    exportStatus.textContent = "Markdown copied to the clipboard.";
  });
  saveButton.addEventListener("click", saveLocally);
  if (isLocalEditor) {
    saveButton.hidden = false;
    overwriteWrap.hidden = false;
  }

  const editRouteSearch = root.querySelector("[data-edit-route-search]");
  const editRouteSelect = root.querySelector("[data-edit-route-select]");
  const loadRouteButton = root.querySelector("[data-load-route]");
  const editRouteStatus = root.querySelector("[data-edit-route-status]");
  let allRoutes = [];

  const renderRouteOptions = () => {
    const query = clean(editRouteSearch.value).toLowerCase();
    const matches = query
      ? allRoutes.filter((route) => [route.title, route.crag, route.wall, route.filename].some((value) => (value || "").toLowerCase().includes(query)))
      : allRoutes;
    editRouteSelect.innerHTML = matches
      .map((route) => `<option value="${escapeHtml(route.filename)}">${escapeHtml(route.title || route.filename)} — ${escapeHtml(route.crag || "no crag")}</option>`)
      .join("");
  };

  const loadRoutesList = async () => {
    try {
      const response = await fetch("/api/climbing/routes");
      if (!response.ok) return;
      allRoutes = await response.json();
      renderRouteOptions();
      if (hierarchyLocations?.length) renderHierarchy();
    } catch {
      // Hosted editor has no routes endpoint; editing existing routes stays local-only.
    }
  };

  const loadSelectedRoute = async () => {
    const filename = editRouteSelect.value;
    if (!filename) {
      editRouteStatus.textContent = "Select a route to load first.";
      return;
    }
    loadRouteButton.disabled = true;
    editRouteStatus.textContent = "Loading route...";
    try {
      const response = await fetch(`/api/climbing/routes/${encodeURIComponent(filename)}`);
      const route = await response.json();
      if (!response.ok) throw new Error(route.error || "Could not load that route.");
      ["title", "climb_date", "crag", "wall", "discipline", "setting", "grade", "ascent_type", "mountain_project_url", "youtube_url", "personal_note"].forEach((name) => {
        if (field(name)) field(name).value = route[name] || "";
      });
      field("body").value = route.body || "";
      field("filename").value = filename.replace(/\.md$/i, "");
      field("draft").checked = Boolean(route.draft);
      field("overwrite").checked = true;
      originalFilename = filename;
      importedCoordinates = null;
      importedCragName = "";
      importedLocationName = "";
      importedStateName = "";
      locationPrompt.hidden = true;
      updatePreview();
      editRouteStatus.textContent = `Loaded ${filename}. Saving will overwrite this route.`;
    } catch (error) {
      editRouteStatus.textContent = `Could not load route: ${error.message}`;
    } finally {
      loadRouteButton.disabled = false;
    }
  };

  editRouteSearch.addEventListener("input", renderRouteOptions);
  loadRouteButton.addEventListener("click", loadSelectedRoute);
  if (isLocalEditor) {
    loadRouteButton.hidden = false;
    loadRouteButton.disabled = false;
    editRouteStatus.textContent = "";
    loadRoutesList();
  }

  const manageOldCrag = root.querySelector("[data-manage-old-crag]");
  const manageWallFilter = root.querySelector("[data-manage-wall-filter]");
  const manageNewCrag = root.querySelector("[data-manage-new-crag]");
  const manageLatitude = root.querySelector("[data-manage-latitude]");
  const manageLongitude = root.querySelector("[data-manage-longitude]");
  const manageUsageButton = root.querySelector("[data-manage-usage-button]");
  const manageUsageList = root.querySelector("[data-manage-usage-list]");
  const manageApplyButton = root.querySelector("[data-manage-apply-button]");
  const manageStatus = root.querySelector("[data-manage-status]");

  const showCragUsage = async () => {
    const name = clean(manageOldCrag.value);
    if (!name) {
      manageStatus.textContent = "Enter the current crag name first.";
      return;
    }
    manageUsageList.innerHTML = "Loading...";
    try {
      const response = await fetch(`/api/climbing/crag-usage?name=${encodeURIComponent(name)}`);
      const usage = await response.json();
      if (!response.ok) throw new Error(usage.error || "Could not look up that crag.");
      if (!usage.total) {
        manageUsageList.innerHTML = `<p>No routes currently use "${escapeHtml(name)}".</p>`;
        return;
      }
      manageUsageList.innerHTML = `<p>${Number(usage.total) || 0} route${usage.total === 1 ? "" : "s"} at "${escapeHtml(name)}":</p><ul>${usage.walls
        .map((wall) => `<li><button type="button" class="climbing-editor__button" data-fill-wall="${escapeHtml(wall.value)}">${escapeHtml(wall.value)}</button> (${Number(wall.count) || 0})</li>`)
        .join("")}</ul>`;
      manageUsageList.querySelectorAll("[data-fill-wall]").forEach((button) => button.addEventListener("click", () => {
        const value = button.getAttribute("data-fill-wall");
        manageWallFilter.value = value === "(no wall set)" ? "" : value;
        if (!manageNewCrag.value) manageNewCrag.value = value === "(no wall set)" ? "" : value;
      }));
    } catch (error) {
      manageUsageList.textContent = error.message;
    }
  };

  const applyRelocate = async () => {
    manageApplyButton.disabled = true;
    manageStatus.textContent = "Updating routes and rebuilding the site...";
    try {
      const response = await fetch("/api/climbing/relocate-routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_crag: clean(manageOldCrag.value),
          wall_filter: clean(manageWallFilter.value),
          new_crag: clean(manageNewCrag.value),
          parent: "",
          latitude: clean(manageLatitude.value),
          longitude: clean(manageLongitude.value),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected that change.");
      const remainder = result.remaining_at_old_crag
        ? `${result.remaining_at_old_crag} route${result.remaining_at_old_crag === 1 ? "" : "s"} still at the old crag name.`
        : "";
      manageStatus.textContent = `${result.routes_updated} route${result.routes_updated === 1 ? "" : "s"} moved to "${result.crag_name}". ${remainder}`;
      loadRoutesList();
    } catch (error) {
      manageStatus.textContent = `Could not update: ${error.message}`;
    } finally {
      manageApplyButton.disabled = false;
    }
  };

  manageUsageButton.addEventListener("click", showCragUsage);
  manageApplyButton.addEventListener("click", applyRelocate);
  if (isLocalEditor) {
    manageApplyButton.hidden = false;
    manageApplyButton.disabled = false;
    manageStatus.textContent = "";
  }

  const hierarchyGraph = root.querySelector("[data-hierarchy-graph]");
  const hierarchyFields = root.querySelector("[data-hierarchy-fields]");
  const hierarchyActions = root.querySelector("[data-hierarchy-actions]");
  const hierarchyOldName = root.querySelector("[data-hierarchy-old-name]");
  const hierarchyName = root.querySelector("[data-hierarchy-name]");
  const hierarchyParent = root.querySelector("[data-hierarchy-parent]");
  const hierarchyImpact = root.querySelector("[data-hierarchy-impact]");
  const hierarchySave = root.querySelector("[data-hierarchy-save]");
  const hierarchyDelete = root.querySelector("[data-hierarchy-delete]");
  const hierarchyStatus = root.querySelector("[data-hierarchy-status]");
  let hierarchyLocations = [];
  let selectedHierarchyNode = "";
  let expandedHierarchyNodes = new Set();

  const hierarchyDirectRouteCount = (name) => allRoutes.filter((route) => (route.crag || "").toLowerCase() === name.toLowerCase()).length;
  const hierarchyDescendants = (name) => {
    const descendants = new Set([name]);
    let added = true;
    while (added) {
      added = false;
      hierarchyLocations.forEach((location) => {
        if (descendants.has(location.parent) && !descendants.has(location.name)) {
          descendants.add(location.name);
          added = true;
        }
      });
    }
    return descendants;
  };
  const hierarchyRoutesFor = (name) => {
    const descendants = hierarchyDescendants(name);
    return allRoutes.filter((route) => descendants.has(route.crag));
  };
  // The badge shows every route in this node's branch (matching the expanded list below it).
  const hierarchyBranchRouteCount = (name) => hierarchyRoutesFor(name).length;
  const renderHierarchy = () => {
    const children = (parent) => hierarchyLocations.filter((location) => (location.parent || "") === parent);
    const renderNode = (location, visited = new Set()) => {
      if (visited.has(location.name)) return "";
      const nextVisited = new Set(visited).add(location.name);
      const childNodes = children(location.name).map((child) => renderNode(child, nextVisited)).join("");
      const count = hierarchyBranchRouteCount(location.name);
      const routes = expandedHierarchyNodes.has(location.name) ? hierarchyRoutesFor(location.name) : [];
      const routeList = routes.length ? `<ul class="climbing-hierarchy-route-list">${routes.map((route) => `<li><button type="button" data-edit-hierarchy-route="${escapeHtml(route.filename)}">${escapeHtml(route.title || route.filename)}</button><small>${escapeHtml(route.crag || "no crag")}${route.wall ? ` / ${escapeHtml(route.wall)}` : ""}</small></li>`).join("")}</ul>` : "";
      return `<li><button type="button" class="climbing-hierarchy-node" data-hierarchy-node="${escapeHtml(location.name)}" aria-pressed="${location.name === selectedHierarchyNode}" aria-expanded="${expandedHierarchyNodes.has(location.name)}">${escapeHtml(location.name)} <small>${escapeHtml(location.level || "crag")}${count ? ` · ${count} route${count === 1 ? "" : "s"}` : ""}</small></button>${routeList}${childNodes ? `<ul>${childNodes}</ul>` : ""}</li>`;
    };
    const roots = hierarchyLocations.filter((location) => !location.parent || !hierarchyLocations.some((candidate) => candidate.name === location.parent));
    hierarchyGraph.innerHTML = roots.length ? `<ul class="climbing-hierarchy-tree">${roots.map((rootLocation) => renderNode(rootLocation)).join("")}</ul>` : "<p>No location records found.</p>";
    hierarchyGraph.querySelectorAll("[data-hierarchy-node]").forEach((button) => button.addEventListener("click", () => {
      const name = button.dataset.hierarchyNode;
      if (expandedHierarchyNodes.has(name)) expandedHierarchyNodes.delete(name);
      else expandedHierarchyNodes.add(name);
      selectHierarchyNode(name);
    }));
    hierarchyGraph.querySelectorAll("[data-edit-hierarchy-route]").forEach((button) => button.addEventListener("click", () => {
      const route = allRoutes.find((candidate) => candidate.filename === button.dataset.editHierarchyRoute);
      if (route) window.openClimbingRouteEditor?.(route.filename, route.title || route.filename);
    }));
  };

  const selectHierarchyNode = (name) => {
    const node = hierarchyLocations.find((location) => location.name === name);
    if (!node) return;
    selectedHierarchyNode = node.name;
    renderHierarchy();
    hierarchyOldName.value = node.name;
    hierarchyName.value = node.name;
    const parentLevel = node.level === "location" ? "state" : "location";
    const parents = hierarchyLocations.filter((location) => location.level === parentLevel && location.name !== node.name);
    hierarchyParent.innerHTML = node.level === "state"
      ? '<option value="">No parent (state)</option>'
      : `<option value="">Choose a parent ${escapeHtml(parentLevel)}</option>${parents.map((parent) => `<option value="${escapeHtml(parent.name)}"${parent.name === node.parent ? " selected" : ""}>${escapeHtml(parent.name)}</option>`).join("")}`;
    hierarchyParent.disabled = node.level === "state";
    const count = hierarchyDirectRouteCount(node.name);
    hierarchyImpact.textContent = count ? `Saving will update ${count} route${count === 1 ? "" : "s"} that use this ${node.level}.` : `No saved routes currently use this ${node.level}.`;
    const hasChildren = hierarchyLocations.some((location) => (location.parent || "").toLowerCase() === node.name.toLowerCase());
    hierarchyDelete.disabled = Boolean(count || hasChildren);
    hierarchyDelete.title = count || hasChildren ? "Only empty hierarchy nodes can be deleted." : "Delete this empty hierarchy node";
    hierarchyFields.hidden = false;
    hierarchyActions.hidden = false;
  };

  const loadHierarchy = async () => {
    try {
      const response = await fetch("/api/climbing/locations");
      if (!response.ok) throw new Error("Could not load location records.");
      hierarchyLocations = await response.json();
      renderHierarchy();
      hierarchyStatus.textContent = "";
    } catch (error) {
      hierarchyStatus.textContent = error.message;
    }
  };

  hierarchySave.addEventListener("click", async () => {
    hierarchySave.disabled = true;
    hierarchyStatus.textContent = "Updating hierarchy and affected routes...";
    try {
      const response = await fetch("/api/climbing/hierarchy-node", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_name: clean(hierarchyOldName.value), name: clean(hierarchyName.value), parent: clean(hierarchyParent.value) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not update the hierarchy.");
      hierarchyStatus.textContent = `${result.node} saved; ${result.routes_updated} route${result.routes_updated === 1 ? "" : "s"} updated. Reloading...`;
      window.location.reload();
    } catch (error) {
      hierarchyStatus.textContent = `Could not update hierarchy: ${error.message}`;
      hierarchySave.disabled = false;
    }
  });

  hierarchyDelete.addEventListener("click", async () => {
    const name = clean(hierarchyOldName.value);
    if (!name || !window.confirm(`Delete empty ${hierarchyLocations.find((location) => location.name === name)?.level || "hierarchy"} node "${name}"?`)) return;
    hierarchyDelete.disabled = true;
    hierarchyStatus.textContent = "Deleting hierarchy node and rebuilding the site...";
    try {
      const response = await fetch("/api/climbing/delete-hierarchy-node", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not delete the hierarchy node.");
      hierarchyStatus.textContent = `${result.node} deleted. Reloading...`;
      window.location.reload();
    } catch (error) {
      hierarchyStatus.textContent = `Could not delete hierarchy node: ${error.message}`;
      hierarchyDelete.disabled = false;
    }
  });

  if (isLocalEditor) {
    loadHierarchy();
  }

  updatePreview();
})();