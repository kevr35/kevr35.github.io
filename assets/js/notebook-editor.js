(() => {
  const root = document.querySelector("[data-notebook-editor]");
  if (!root) return;

  const isLocalEditor = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const sourceInput = root.querySelector("[data-notebook-source]");
  const loadButton = root.querySelector("[data-load-source]");
  const loadStatus = root.querySelector("[data-load-status]");
  const form = root.querySelector("[data-notebook-form]");
  const preview = root.querySelector("[data-markdown-preview]");
  const exportStatus = root.querySelector("[data-export-status]");
  const saveButton = root.querySelector("[data-save-locally]");
  const overwriteWrap = root.querySelector("[data-overwrite-wrap]");
  let originalFilename = "";

  const field = (name) => form.elements[name];
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const slugify = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  const titleFromUrl = (url) => {
    try {
      const path = decodeURIComponent(new URL(url).pathname);
      const name = path.split("/").filter(Boolean).pop() || "";
      return clean(name.replace(/\.nb$/i, "").replace(/[-_]+/g, " ")).replace(/\b\w/g, (letter) => letter.toUpperCase());
    } catch {
      return "";
    }
  };

  const loadSource = () => {
    const url = clean(sourceInput.value);
    if (!url) {
      loadStatus.textContent = "Paste a Wolfram Cloud embed URL first.";
      return;
    }
    if (!/^https:\/\/(www\.)?wolframcloud\.com\//i.test(url)) {
      loadStatus.textContent = "This doesn't look like a wolframcloud.com link, but it will still be used as entered.";
    } else {
      loadStatus.textContent = "Link loaded. Review the fields below.";
    }
    const title = titleFromUrl(url) || "Untitled notebook";
    field("title").value = title;
    field("date").value = new Date().toISOString().slice(0, 10);
    field("embed_url").value = url;
    field("filename").value = slugify(title);
    field("tags").value = "";
    field("description").value = "";
    field("draft").checked = false;
    field("overwrite").checked = false;
    originalFilename = "";
    overwriteWrap.hidden = true;
    form.hidden = false;
    updatePreview();
  };

  const yamlString = (value) => JSON.stringify(clean(value));
  const makeMarkdown = () => {
    const tags = clean(field("tags").value).split(",").map(clean).filter(Boolean);
    const lines = [
      "---",
      `title: ${yamlString(field("title").value)}`,
      `date: ${yamlString(field("date").value || new Date().toISOString().slice(0, 10))}`,
      `description: ${yamlString(field("description").value)}`,
      `tags: [${tags.map(yamlString).join(", ")}]`,
      `embed_url: ${yamlString(field("embed_url").value)}`,
      `draft: ${field("draft").checked}`,
      "---",
      "",
    ];
    return lines.join("\n");
  };

  const updatePreview = () => { preview.value = makeMarkdown(); };
  const download = () => {
    const blob = new Blob([preview.value], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${slugify(field("filename").value) || "notebook"}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
    exportStatus.textContent = "Markdown downloaded. Move it into content/notebooks/ and review it before committing.";
  };

  const saveLocally = async () => {
    if (!isLocalEditor) {
      exportStatus.textContent = "Direct saving is available only in the local editor. Run python tools/site_editor.py and open http://127.0.0.1:8000/admin/notebooks/.";
      return;
    }
    saveButton.disabled = true;
    exportStatus.textContent = "Saving notebook to content/notebooks/...";
    try {
      const filename = `${slugify(field("filename").value) || "notebook"}.md`;
      const response = await fetch("/api/notebooks/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename,
          markdown: preview.value,
          overwrite: field("overwrite").checked || filename === originalFilename,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "The local server rejected the notebook.");
      exportStatus.textContent = `${result.path} saved. Hugo rebuilt the site.`;
      originalFilename = filename;
      overwriteWrap.hidden = false;
    } catch (error) {
      exportStatus.textContent = `Could not save locally: ${error.message}`;
    } finally {
      saveButton.disabled = false;
    }
  };

  loadButton.addEventListener("click", loadSource);
  form.addEventListener("input", updatePreview);
  form.addEventListener("submit", (event) => { event.preventDefault(); download(); });
  saveButton.addEventListener("click", saveLocally);
  root.querySelector("[data-copy]").addEventListener("click", async () => {
    await navigator.clipboard.writeText(preview.value);
    exportStatus.textContent = "Markdown copied to the clipboard.";
  });
})();
