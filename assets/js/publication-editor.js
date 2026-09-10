(() => {
  const root = document.querySelector("[data-publication-editor]");
  if (!root) return;

  const input = root.querySelector("[data-bibtex-input]");
  const parseButton = root.querySelector("[data-parse]");
  const fileInput = root.querySelector("[data-bib-file]");
  const sourceInput = root.querySelector("[data-publication-source]");
  const fetchSourceButton = root.querySelector("[data-fetch-source]");
  const fetchStatus = root.querySelector("[data-fetch-status]");
  const status = root.querySelector("[data-status]");
  const picker = root.querySelector("[data-entry-picker]");
  const entrySelect = root.querySelector("[data-entry-select]");
  const form = root.querySelector("[data-publication-form]");
  const preview = root.querySelector("[data-markdown-preview]");
  const exportStatus = root.querySelector("[data-export-status]");
  const includeImage = root.querySelector("[data-include-image]");
  const imageOptions = root.querySelector("[data-image-options]");
  const imageMode = root.querySelector("[data-image-mode]");
  const imageHelp = root.querySelector("[data-image-help]");
  let entries = [];
  let selectedEntry = null;

  const citationKeys = [
    "author", "title", "year", "date", "journal", "booktitle", "publisher",
    "volume", "number", "issue", "pages", "chapter", "edition", "series",
    "school", "institution", "organization", "doi", "url", "eprint",
    "archiveprefix", "primaryclass", "month",
  ];

  const field = (name) => form.elements[name];
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const sourceAsUrl = (value) => {
    const candidate = clean(value);
    if (/^10\.\d{4,9}\//i.test(candidate)) return `https://doi.org/${candidate}`;
    return candidate;
  };
  const unquote = (value) => {
    const trimmed = clean(value);
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith('"') && trimmed.endsWith('"'))) {
      return trimmed.slice(1, -1).replace(/\\([{}"])/g, "$1").replace(/[{}]/g, "");
    }
    return trimmed.replace(/[{}]/g, "");
  };

  const splitFields = (body) => {
    const fields = {};
    let start = 0;
    let depth = 0;
    let quote = false;
    const parts = [];
    for (let index = 0; index < body.length; index += 1) {
      const character = body[index];
      if (character === '"' && body[index - 1] !== "\\") quote = !quote;
      if (!quote && character === "{") depth += 1;
      if (!quote && character === "}") depth -= 1;
      if (!quote && depth === 0 && character === ",") {
        parts.push(body.slice(start, index));
        start = index + 1;
      }
    }
    parts.push(body.slice(start));
    parts.forEach((part) => {
      const separator = part.indexOf("=");
      if (separator < 0) return;
      const key = clean(part.slice(0, separator)).toLowerCase();
      if (key) fields[key] = unquote(part.slice(separator + 1));
    });
    return fields;
  };

  const parseBibtex = (text) => {
    const parsed = [];
    const entryStart = /@([a-z]+)\s*\{/gi;
    let match;
    while ((match = entryStart.exec(text))) {
      let depth = 1;
      let quote = false;
      let index = entryStart.lastIndex;
      for (; index < text.length && depth; index += 1) {
        const character = text[index];
        if (character === '"' && text[index - 1] !== "\\") quote = !quote;
        if (!quote && character === "{") depth += 1;
        if (!quote && character === "}") depth -= 1;
      }
      if (depth !== 0) break;
      const body = text.slice(entryStart.lastIndex, index - 1);
      const separator = body.indexOf(",");
      if (separator < 0) continue;
      parsed.push({
        type: match[1].toLowerCase(),
        key: clean(body.slice(0, separator)),
        fields: splitFields(body.slice(separator + 1)),
      });
      entryStart.lastIndex = index;
    }
    return parsed;
  };

  const entryFromCrossref = (message, doi) => {
    const dateParts = message.published?.["date-parts"]?.[0] || message.issued?.["date-parts"]?.[0] || [];
    const authors = (message.author || []).map((author) => [author.family, author.given].filter(Boolean).join(", ")).join(" and ");
    const publisherUrl = message.URL && !/doi\.org/i.test(message.URL)
      ? message.URL
      : (message.link || []).find((link) => /text\/html/i.test(link["content-type"] || ""))?.URL || message.URL || `https://doi.org/${message.DOI || doi}`;
    const fields = {
      title: message.title?.[0] || "",
      author: authors,
      year: dateParts[0] ? String(dateParts[0]) : "",
      journal: message["container-title"]?.[0] || "",
      volume: message.volume || "",
      number: message.issue || "",
      pages: message.page || "",
      publisher: message.publisher || "",
      doi: message.DOI || doi,
      url: publisherUrl,
      abstract: message.abstract || "",
    };
    return { type: message.type === "book" ? "book" : "article", key: clean(fields.author.split(" and ")[0]).replace(/[^A-Za-z0-9]+/g, "") + (dateParts[0] || ""), fields };
  };

  const normalizeTitle = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

  const resolvePublisherUrl = async (doi, fallback) => {
    try {
      const response = await fetch(`https://doi.org/${encodeURIComponent(doi)}`, { redirect: "follow" });
      if (response.url && !/doi\.org/i.test(new URL(response.url).hostname)) return response.url;
    } catch {
      // Cross-origin redirect resolution is best effort in a static browser tool.
    }
    return fallback;
  };

  const findArxivId = async (title) => {
    if (!title) return "";
    try {
      const query = encodeURIComponent(`ti:"${title.replace(/"/g, "")}"`);
      const response = await fetch(`https://export.arxiv.org/api/query?search_query=${query}&max_results=5`);
      if (!response.ok) return "";
      const xml = new DOMParser().parseFromString(await response.text(), "application/xml");
      const target = normalizeTitle(title);
      const result = [...xml.querySelectorAll("entry")].find((entry) => {
        const candidate = normalizeTitle(entry.querySelector("title")?.textContent || "");
        return candidate === target || (candidate.length > 20 && (candidate.includes(target) || target.includes(candidate)));
      });
      const link = result?.querySelector('id')?.textContent || "";
      return link.match(/arxiv\.org\/(?:abs\/)?([^?#]+)$/i)?.[1] || "";
    } catch {
      return "";
    }
  };

  const enrichExternalMetadata = async (entry) => {
    if (entry.fields.doi) {
      entry.fields.url = await resolvePublisherUrl(entry.fields.doi, entry.fields.url);
    }
    if (!entry.fields.eprint) {
      const arxivId = await findArxivId(entry.fields.title);
      if (arxivId) entry.fields.eprint = arxivId;
    }
    return entry;
  };

  const metadataEntryFromHtml = (html, url) => {
    const document = new DOMParser().parseFromString(html, "text/html");
    const meta = (name) => document.querySelector(`meta[name="${name}"], meta[property="${name}"]`)?.content || "";
    const canonical = document.querySelector('link[rel="canonical"]')?.href || url;
    const title = meta("citation_title") || meta("og:title") || document.querySelector("title")?.textContent || "";
    const authorNodes = [...document.querySelectorAll('meta[name="citation_author"]')];
    const author = authorNodes.map((node) => node.content).join(" and ");
    const doi = meta("citation_doi") || (html.match(/10\.\d{4,9}\/[A-Za-z0-9._;()/:+-]+/) || [""])[0];
    const year = meta("citation_publication_date") || meta("citation_date") || "";
    const journal = meta("citation_journal_title") || meta("og:site_name") || "";
    const abstract = meta("description") || meta("og:description") || "";
    const metadataFields = { title, author, year: year.slice(0, 4), journal, doi, url: canonical, abstract };
    const bibtexMatch = html.match(/@(?:article|inproceedings|book|misc)\s*\{[\s\S]*?\n\s*\}/i);
    if (bibtexMatch) {
      const bibEntries = parseBibtex(bibtexMatch[0]);
      if (bibEntries.length) {
        const bibEntry = bibEntries[0];
        return { ...bibEntry, fields: { ...metadataFields, ...bibEntry.fields } };
      }
    }
    return { type: "article", key: slugify(title) || "publication", fields: metadataFields };
  };

  const showEntries = (loadedEntries, message) => {
    entries = loadedEntries;
    entrySelect.replaceChildren(...entries.map((entry, index) => new Option(`${entry.fields.title || entry.key} (${entry.type})`, index)));
    picker.hidden = entries.length < 2;
    form.hidden = false;
    status.textContent = message;
    setForm(entries[0]);
  };

  const fetchPublication = async () => {
    const source = sourceAsUrl(sourceInput.value);
    if (!source) {
      fetchStatus.textContent = "Enter a DOI or paper URL first.";
      return;
    }
    fetchSourceButton.disabled = true;
    fetchStatus.textContent = "Fetching publication metadata...";
    try {
      const doiMatch = source.match(/10\.\d{4,9}\/[A-Za-z0-9._;()/:+-]+/i);
      if (doiMatch) {
        const doi = doiMatch[0];
        const response = await fetch(`https://api.crossref.org/works/${encodeURIComponent(doi)}`, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`Crossref returned ${response.status}.`);
        const data = await response.json();
        const entry = await enrichExternalMetadata(entryFromCrossref(data.message, doi));
        input.value = cleanBibtex(entry);
        showEntries([entry], "Metadata fetched from Crossref. Review and edit it below.");
      } else {
        const response = await fetch(source);
        if (!response.ok) throw new Error(`The publisher returned ${response.status}.`);
        const entry = await enrichExternalMetadata(metadataEntryFromHtml(await response.text(), source));
        input.value = cleanBibtex(entry);
        showEntries([entry], "Metadata fetched from the page. Review and edit it below.");
      }
    } catch (error) {
      fetchStatus.textContent = `Could not fetch this source: ${error.message} Try pasting its BibTeX instead; publisher pages may block browser scraping.`;
    } finally {
      fetchSourceButton.disabled = false;
    }
  };

  const authors = (value) => clean(value).split(/\s+and\s+/i).map((author) => {
    const [last, first] = author.split(",").map(clean);
    return first ? `${first} ${last}` : last;
  }).filter(Boolean).join("; ");

  const slugify = (value) => clean(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const localImagePath = () => `previews/${slugify(field("title").value || field("filename").value || "publication")}.png`;

  const publisherFavicon = () => {
    const source = field("external_url").value || (field("doi").value ? `https://doi.org/${field("doi").value}` : "");
    if (!source) return "";
    try {
      return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(new URL(source).hostname)}&sz=128`;
    } catch {
      return "";
    }
  };

  const updateImageControls = () => {
    imageOptions.hidden = !includeImage.checked;
    if (!includeImage.checked) {
      imageHelp.textContent = "No image will be written to the Markdown file.";
      return;
    }
    if (imageMode.value === "favicon") {
      const favicon = publisherFavicon();
      field("image").value = favicon;
      imageHelp.textContent = favicon ? "The publisher icon will be loaded from the paper URL. For a durable result, download it into static/previews/ instead." : "Add an external URL or DOI to derive a publisher favicon.";
    } else if (imageMode.value === "local") {
      if (!field("image").value || field("image").value.startsWith("http")) field("image").value = localImagePath();
      imageHelp.textContent = `Put an image at static/${field("image").value} before committing the Markdown file.`;
    }
    updatePreview();
  };

  const bibtexValue = (value) => `{${String(value || "").replace(/[{}]/g, "")}}`;
  const cleanBibtex = (entry) => {
    if (!entry) return "";
    const fields = citationKeys.filter((key) => entry.fields[key]).map((key) => `  ${key} = ${bibtexValue(entry.fields[key])},`);
    if (fields.length) fields[fields.length - 1] = fields[fields.length - 1].replace(/,$/, "");
    return [`@${entry.type}{${entry.key},`, ...fields, "}"].join("\n");
  };

  const setForm = (entry) => {
    selectedEntry = entry;
    const values = entry.fields;
    field("title").value = values.title || entry.key;
    field("publication").value = values.journal || values.booktitle || values.publisher || "";
    field("author").value = authors(values.author || "");
    field("date").value = values.year ? `${values.year}-01-01` : "";
    field("doi").value = values.doi || "";
    field("arxiv").value = values.eprint || "";
    field("pdf").value = "";
    field("external_url").value = values.url || "";
    field("url_label").value = values.url ? "Paper" : "";
    field("image").value = values.image || values.thumbnail || values.cover || "";
    includeImage.checked = true;
    imageMode.value = field("image").value ? (field("image").value.startsWith("http") ? "favicon" : "local") : "local";
    field("tags").value = "";
    field("abstract").value = values.abstract || "";
    field("filename").value = slugify(values.title || entry.key);
    field("draft").checked = false;
    updateImageControls();
    updatePreview();
  };

  const yamlString = (value) => JSON.stringify(clean(value));
  const editedCitationEntry = () => {
    if (!selectedEntry) return null;
    const fields = { ...selectedEntry.fields };
    fields.title = field("title").value;
    fields.author = clean(field("author").value).split(";").map(clean).filter(Boolean).join(" and ");
    fields.year = clean(field("date").value).slice(0, 4);
    const venueKey = fields.journal ? "journal" : fields.booktitle ? "booktitle" : "publisher";
    if (venueKey || field("publication").value) fields[venueKey || "journal"] = field("publication").value;
    fields.doi = field("doi").value;
    fields.url = field("external_url").value;
    fields.eprint = field("arxiv").value;
    return { ...selectedEntry, fields };
  };

  const makeMarkdown = () => {
    const tags = clean(field("tags").value).split(",").map(clean).filter(Boolean);
    const authorList = clean(field("author").value).split(";").map(clean).filter(Boolean);
    const lines = [
      "---",
      `title: ${yamlString(field("title").value)}`,
      `date: ${yamlString(field("date").value || new Date().toISOString().slice(0, 10))}`,
      `author: [${authorList.map(yamlString).join(", ")}]`,
      `publication: ${yamlString(field("publication").value)}`,
      `tags: [${tags.map(yamlString).join(", ")}]`,
      ...(includeImage.checked && clean(field("image").value) ? [`image: ${yamlString(field("image").value)}`] : []),
      `abstract: ${yamlString(field("abstract").value)}`,
      `doi: ${yamlString(field("doi").value)}`,
      `arxiv: ${yamlString(field("arxiv").value)}`,
      `pdf: ${yamlString(field("pdf").value)}`,
      `external_url: ${yamlString(field("external_url").value)}`,
      `url_label: ${yamlString(field("url_label").value || "Paper")}`,
      `draft: ${field("draft").checked}`,
      "bibtex: |",
      ...cleanBibtex(editedCitationEntry()).split("\n").map((line) => `  ${line}`),
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
    link.download = `${slugify(field("filename").value) || "publication"}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
    exportStatus.textContent = "Markdown downloaded. Move it into content/publications/ and review it before committing.";
  };

  const parse = () => {
    entries = parseBibtex(input.value);
    if (!entries.length) {
      status.textContent = "No BibTeX entries found. Check that the text starts with @article, @book, or another BibTeX type.";
      form.hidden = true;
      picker.hidden = true;
      return;
    }
    entrySelect.replaceChildren(...entries.map((entry, index) => new Option(`${entry.fields.title || entry.key} (${entry.type})`, index)));
    picker.hidden = entries.length < 2;
    form.hidden = false;
    status.textContent = `${entries.length} BibTeX ${entries.length === 1 ? "entry" : "entries"} loaded.`;
    setForm(entries[0]);
  };

  parseButton.addEventListener("click", parse);
  fetchSourceButton.addEventListener("click", fetchPublication);
  entrySelect.addEventListener("change", () => setForm(entries[Number(entrySelect.value)]));
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.addEventListener("load", () => { input.value = reader.result; parse(); });
    reader.readAsText(file);
  });
  includeImage.addEventListener("change", updateImageControls);
  imageMode.addEventListener("change", updateImageControls);
  form.addEventListener("input", updatePreview);
  form.addEventListener("submit", (event) => { event.preventDefault(); download(); });
  root.querySelector("[data-copy]").addEventListener("click", async () => {
    await navigator.clipboard.writeText(preview.value);
    exportStatus.textContent = "Markdown copied to the clipboard.";
  });
})();