(() => {
  const root = document.querySelector("[data-hierarchy-editor]");
  if (!root) return;

  const graph = root.querySelector("[data-hierarchy-graph]");
  const fields = root.querySelector("[data-hierarchy-fields]");
  const actions = root.querySelector("[data-hierarchy-actions]");
  const oldName = root.querySelector("[data-hierarchy-old-name]");
  const name = root.querySelector("[data-hierarchy-name]");
  const parent = root.querySelector("[data-hierarchy-parent]");
  const latitude = root.querySelector("[data-hierarchy-latitude]");
  const longitude = root.querySelector("[data-hierarchy-longitude]");
  const impact = root.querySelector("[data-hierarchy-impact]");
  const status = root.querySelector("[data-hierarchy-status]");
  const save = root.querySelector("[data-hierarchy-save]");
  const remove = root.querySelector("[data-hierarchy-delete]");
  const refreshCoordinates = root.querySelector("[data-refresh-coordinates]");
  const newLevel = root.querySelector("[data-new-level]");
  const newName = root.querySelector("[data-new-name]");
  const newParent = root.querySelector("[data-new-parent]");
  const newLatitude = root.querySelector("[data-new-latitude]");
  const newLongitude = root.querySelector("[data-new-longitude]");
  const newSave = root.querySelector("[data-new-save]");
  const newStatus = root.querySelector("[data-new-status]");
  let locations = [];
  let routes = [];
  let selected = "";
  const expanded = new Set();

  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  const children = (node) => locations.filter((candidate) => (candidate.parent || "") === node);
  const routeCount = (node) => locations.find((candidate) => candidate.name === node)?.route_count || 0;
  const descendants = (node, seen = new Set()) => {
    if (seen.has(node)) return seen;
    seen.add(node);
    children(node).forEach((child) => descendants(child.name, seen));
    return seen;
  };
  const routesFor = (node) => {
    const names = descendants(node);
    return routes.filter((route) => names.has(route.crag));
  };
  const renderNode = (node, seen = new Set()) => {
    if (seen.has(node.name)) return "";
    const next = new Set(seen).add(node.name);
    const nested = children(node.name).map((child) => renderNode(child, next)).join("");
    const count = routeCount(node.name);
    const routeItems = routesFor(node.name).map((route) => `<li><button type="button" class="climbing-editor__button climbing-hierarchy-route" data-route-file="${escapeHtml(route.filename)}">${escapeHtml(route.title || route.filename)}</button><small>${escapeHtml(route.crag || "no crag")}${route.wall ? ` / ${escapeHtml(route.wall)}` : ""}</small></li>`).join("");
    const routeList = expanded.has(node.name) && routeItems ? `<ul class="climbing-hierarchy-route-list">${routeItems}</ul>` : "";
    return `<li><button type="button" class="climbing-hierarchy-node" data-node="${escapeHtml(node.name)}" aria-pressed="${node.name === selected}">${escapeHtml(node.name)} <small>${escapeHtml(node.level || "crag")}${count ? ` · ${count} route${count === 1 ? "" : "s"}` : ""}</small></button>${routeList}${nested ? `<ul>${nested}</ul>` : ""}</li>`;
  };
  const render = () => {
    const roots = locations.filter((node) => !node.parent || !locations.some((candidate) => candidate.name === node.parent));
    graph.innerHTML = roots.length ? `<ul class="climbing-hierarchy-tree">${roots.map((node) => renderNode(node)).join("")}</ul>` : "<p>No location records found.</p>";
    graph.querySelectorAll("[data-node]").forEach((button) => button.addEventListener("click", () => {
      const nodeName = button.dataset.node;
      if (expanded.has(nodeName)) expanded.delete(nodeName);
      else expanded.add(nodeName);
      select(nodeName);
    }));
    graph.querySelectorAll("[data-route-file]").forEach((button) => button.addEventListener("click", () => {
      const route = routes.find((candidate) => candidate.filename === button.dataset.routeFile);
      if (route) window.openClimbingRouteEditor?.(route.filename, route.title || route.filename);
    }));
  };
  const select = (nodeName) => {
    const node = locations.find((candidate) => candidate.name === nodeName);
    if (!node) return;
    selected = node.name;
    oldName.value = node.name;
    name.value = node.name;
    latitude.value = node.latitude || "";
    longitude.value = node.longitude || "";
    const parentLevel = node.level === "location" ? "state" : node.level === "crag" ? "location" : "";
    const options = locations.filter((candidate) => candidate.level === parentLevel && candidate.name !== node.name);
    parent.innerHTML = node.level === "state" ? "<option value=\"\">No parent</option>" : `<option value=\"\">Choose a ${parentLevel}</option>${options.map((candidate) => `<option value=\"${escapeHtml(candidate.name)}\"${candidate.name === node.parent ? " selected" : ""}>${escapeHtml(candidate.name)}</option>`).join("")}`;
    parent.disabled = node.level === "state";
    const hasChildren = children(node.name).length > 0;
    const count = Number(node.route_count || 0);
    impact.textContent = hasChildren || count ? `${count} route${count === 1 ? "" : "s"}; ${hasChildren ? "has child records" : "empty of child records"}.` : "No routes or child records. This node may be deleted.";
    remove.disabled = Boolean(hasChildren || count);
    refreshCoordinates.hidden = node.level !== "location";
    fields.hidden = false;
    actions.hidden = false;
    render();
  };
  const load = async () => {
    try {
      const response = await fetch("/api/climbing/locations");
      if (!response.ok) throw new Error("Could not load location records.");
      locations = await response.json();
      const routesResponse = await fetch("/api/climbing/routes");
      if (routesResponse.ok) routes = await routesResponse.json();
      updateNewParents();
      render();
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message;
    }
  };
  const updateNewParents = () => {
    const level = newLevel.value;
    const parentLevel = level === "location" ? "state" : level === "crag" ? "location" : "";
    const options = locations.filter((node) => node.level === parentLevel);
    newParent.disabled = !parentLevel;
    newParent.innerHTML = level === "state" ? "<option value=\"\">No parent</option>" : `<option value=\"\">Choose a ${parentLevel}</option>${options.map((node) => `<option value=\"${escapeHtml(node.name)}\">${escapeHtml(node.name)}</option>`).join("")}`;
  };
  newLevel.addEventListener("change", updateNewParents);
  newSave.addEventListener("click", async () => {
    newSave.disabled = true;
    newStatus.textContent = "Adding approved hierarchy node...";
    try {
      const response = await fetch("/api/climbing/create-hierarchy-node", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ level: newLevel.value, name: newName.value, parent: newParent.value, latitude: newLatitude.value, longitude: newLongitude.value }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not add hierarchy node.");
      newStatus.textContent = `${result.node} added. Reloading...`;
      window.location.reload();
    } catch (error) {
      newStatus.textContent = error.message;
      newSave.disabled = false;
    }
  });
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      const response = await fetch("/api/climbing/hierarchy-node", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ old_name: oldName.value, name: name.value, parent: parent.value, latitude: latitude.value, longitude: longitude.value }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save hierarchy changes.");
      status.textContent = `${result.node} saved. Reloading...`;
      window.location.reload();
    } catch (error) {
      status.textContent = error.message;
      save.disabled = false;
    }
  });
  remove.addEventListener("click", async () => {
    if (!window.confirm(`Delete empty node "${oldName.value}"?`)) return;
    remove.disabled = true;
    try {
      const response = await fetch("/api/climbing/delete-hierarchy-node", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: oldName.value }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not delete hierarchy node.");
      status.textContent = `${result.node} deleted. Reloading...`;
      window.location.reload();
    } catch (error) {
      status.textContent = error.message;
      remove.disabled = false;
    }
  });
  refreshCoordinates.addEventListener("click", async () => {
    const locationName = oldName.value;
    if (!window.confirm(`Refresh coordinates for every crag under "${locationName}" from Mountain Project?`)) return;
    refreshCoordinates.disabled = true;
    status.textContent = "Refreshing child crag coordinates...";
    try {
      const response = await fetch("/api/climbing/refresh-location-coordinates", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: locationName }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not refresh coordinates.");
      const failed = result.failed.length ? ` Failed: ${result.failed.join(", ")}.` : "";
      status.textContent = `${result.updated.length} crag coordinate${result.updated.length === 1 ? "" : "s"} refreshed.${failed}`;
      await load();
      select(locationName);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      refreshCoordinates.disabled = false;
    }
  });
  load();
})();
