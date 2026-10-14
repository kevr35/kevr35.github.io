(() => {
  const root = document.querySelector("[data-indoor-import]");
  if (!root) return;
  const urlInput = root.querySelector("[data-indoor-url]");
  const form = root.querySelector("[data-indoor-form]");
  const status = root.querySelector("[data-indoor-status]");
  const filename = root.querySelector("[data-indoor-filename]");
  const overwrite = root.querySelector("[data-indoor-overwrite]");
  const gymPanel = root.querySelector("[data-indoor-gym-panel]");
  const gymName = root.querySelector("[data-indoor-new-gym-name]");
  const gymCity = root.querySelector("[data-indoor-new-gym-city]");
  const gymState = root.querySelector("[data-indoor-new-gym-state]");
  const gymUrl = root.querySelector("[data-indoor-new-gym-url]");
  const addGymButton = root.querySelector("[data-indoor-gym-add]");
  const fields = Object.fromEntries([...root.querySelectorAll("[data-indoor-field]")].map((el) => [el.dataset.indoorField, el]));
  let youtubeUrl = "";
  let instagramUrl = "";

  const post = async (path, body) => {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed.");
    return data;
  };

  const fillSelect = (select, names, value) => {
    select.replaceChildren(new Option("None", ""), ...names.map((name) => new Option(name, name)));
    if (value && !names.includes(value)) select.append(new Option(`${value} (not in registry)`, value));
    select.value = value || "";
  };

  root.querySelector("[data-indoor-gym-toggle]").addEventListener("click", () => {
    gymPanel.hidden = !gymPanel.hidden;
    if (!gymPanel.hidden) gymName.focus();
  });

  root.querySelector("[data-indoor-gym-cancel]").addEventListener("click", () => {
    gymPanel.hidden = true;
  });

  addGymButton.addEventListener("click", async () => {
    const name = gymName.value.trim();
    if (!name) {
      status.textContent = "Enter a gym name before adding it.";
      gymName.focus();
      return;
    }

    addGymButton.disabled = true;
    status.textContent = "Adding gym to the shared list...";
    try {
      const data = await post("/api/climbing/gyms", {
        name,
        city: gymCity.value.trim(),
        state: gymState.value.trim(),
        url: gymUrl.value.trim(),
      });
      fillSelect(fields.gym, data.gyms, data.gym);
      fields.board.value = "";
      gymPanel.hidden = true;
      gymName.value = "";
      gymCity.value = "";
      gymState.value = "";
      gymUrl.value = "";
      status.textContent = `Added ${data.gym} to gyms.yaml and selected it.`;
    } catch (error) {
      status.textContent = error.message;
    } finally {
      addGymButton.disabled = false;
    }
  });

  root.querySelector("[data-indoor-fetch]").addEventListener("click", async () => {
    status.textContent = "Fetching video details...";
    form.hidden = true;
    try {
      const data = await post("/api/climbing/preview-indoor", { url: urlInput.value });
      const f = data.fields;
      youtubeUrl = f.youtube_url;
      instagramUrl = f.instagram_url;
      for (const [key, el] of Object.entries(fields)) if (!(el instanceof HTMLSelectElement)) el.value = f[key] || "";
      fillSelect(fields.gym, data.gyms, f.gym);
      fillSelect(fields.board, data.boards, f.board);
      filename.value = data.filename.replace(/\.md$/, "");
      form.hidden = false;
      status.textContent = data.issues.length ? `Check before saving: ${data.issues.join("; ")}.` : "Details detected. Review them, then save.";
    } catch (error) {
      status.textContent = error.message;
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(Object.entries(fields).map(([key, el]) => [key, el.value.trim()]));
    if (values.board) values.gym = "";
    try {
      const data = await post("/api/climbing/save-indoor", {
        fields: { ...values, youtube_url: youtubeUrl, instagram_url: instagramUrl },
        filename: filename.value.trim(),
        overwrite: overwrite.checked,
      });
      status.textContent = `Saved ${data.path}.`;
    } catch (error) {
      status.textContent = error.message;
    }
  });
})();
