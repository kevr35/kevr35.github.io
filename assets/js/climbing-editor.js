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
  let selectedPhotos = [];
  const text = (document, selectors) => selectors.map((selector) => document.querySelector(selector)?.content || document.querySelector(selector)?.textContent || "").find(Boolean) || "";
  const set = (name, value) => { if (value) field(name).value = clean(value); };

  const updatePreview = () => {
    const values = {
      title: JSON.stringify(clean(field("title").value)),
      region: JSON.stringify(clean(field("region").value)),
      date: new Date().toISOString(),
      climb_date: JSON.stringify(field("climb_date").value),
      location: JSON.stringify(clean(field("location").value)),
      area: JSON.stringify(clean(field("area").value)),
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
      exportStatus.textContent = "Direct saving is available only in the local editor. Run python tools/climbing_editor.py and open http://127.0.0.1:8000/admin/climbing/.";
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
          markdown: preview.value,
          overwrite: field("overwrite").checked,
          add_location: field("add_location").checked,
          region_name: clean(field("region").value),
          crag_name: importedCragName,
          parent: clean(field("region").value),
          coordinates: importedCoordinates,
          photos,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected the route.");
      exportStatus.textContent = `${result.path} saved. Hugo rebuilt the site.`;
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
    const breadcrumbRegion = hierarchy.shift() || "";
    const breadcrumbLocation = hierarchy.shift() || "";
    const breadcrumbArea = hierarchy.join(" / ");
    const coordinates = pageText.match(/GPS:\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/i);
    importedCoordinates = coordinates ? { latitude: coordinates[1], longitude: coordinates[2] } : null;
    importedCragName = breadcrumbLocation;
    set("title", title);
    set("mountain_project_url", canonical);
    set("grade", grade || pageGrade);
    field("region").value = clean(breadcrumbRegion);
    field("location").value = clean(breadcrumbLocation || location);
    field("area").value = clean(breadcrumbArea);
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
        const knownCrag = locations.some((location) => location.name.toLowerCase() === importedCragName.toLowerCase());
        const regionValue = clean(field("region").value).toLowerCase();
        const knownRegion = !regionValue || locations.some((location) => location.level === "region" && location.name.toLowerCase() === regionValue);
        if (!knownCrag || !knownRegion) {
          locationName.textContent = `${field("region").value} / ${importedCragName}`;
        field("add_location").checked = true;
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
  updatePreview();
})();