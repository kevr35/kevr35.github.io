document.addEventListener("DOMContentLoaded", () => {
  const browser = document.querySelector("[data-climbing-browser]");
  if (!browser) return;

  const cards = [...browser.querySelectorAll("[data-route-card]")];
  const filters = [...browser.querySelectorAll("[data-filter]")];
  const sortSelect = browser.querySelector("[data-sort]");
  const grid = browser.querySelector("[data-route-grid]");
  const resultCount = browser.querySelector("[data-results]");
  const empty = browser.querySelector("[data-empty]");
  const rangeGroups = [...browser.querySelectorAll("[data-grade-range]")];
  const ranges = {};
  const ydsGrades = [
    ...Array.from({ length: 10 }, (_, index) => `5.${index}`),
    ...Array.from({ length: 6 }, (_, index) => 10 + index).flatMap((number) => ["a", "b", "c", "d"].map((letter) => `5.${number}${letter}`)),
  ];
  const normalizeFilterValue = (value) => {
    const decoder = document.createElement("textarea");
    decoder.innerHTML = value || "";
    return decoder.value.toLowerCase();
  };

  const queryFilters = new URLSearchParams(window.location.search);
  let scopedLocation = normalizeFilterValue(queryFilters.get("location"));
  let scopedCrag = normalizeFilterValue(queryFilters.get("crag"));
  let scopedWall = normalizeFilterValue(queryFilters.get("wall"));
  let scopedMapLocation = normalizeFilterValue(queryFilters.get("map"));
  const mapElement = document.querySelector("[data-map-points]");
  const mapReset = document.querySelector("[data-map-reset]");
  if (mapReset && (window.location.search.includes("location=") || window.location.search.includes("crag=") || window.location.search.includes("wall=") || window.location.search.includes("map="))) mapReset.hidden = false;
  let refreshMap = () => {};
  const currentScope = () => ({
    location: normalizeFilterValue(document.querySelector('[data-filter="location"]')?.value) || scopedLocation,
    crag: normalizeFilterValue(document.querySelector('[data-filter="crag"]')?.value) || scopedCrag,
    wall: scopedWall,
    mapLocation: scopedMapLocation,
  });
  const showMapFallback = (message = "Map tiles could not be loaded. The climbing location data is still available below.") => {
    if (mapElement && !mapElement.dataset.mapInitialized) {
      mapElement.dataset.mapFailed = "true";
      mapElement.innerHTML = `<p class="climbing-map-fallback">${message}</p>`;
    }
  };

  const initializeMap = () => {
    if (!mapElement || !window.L || mapElement.dataset.mapInitialized || mapElement.dataset.mapFailed) return Boolean(window.L);
    try {
      const map = L.map(mapElement).setView([39.8, -81.5], 7);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);

      const points = JSON.parse(mapElement.dataset.mapPoints);
    const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[character]));
    const locationLink = (point) => {
      const query = new URLSearchParams();
      if (point.level === "location") query.set("map", point.name);
      else {
        if (point.filterLocation) query.set("location", point.filterLocation);
        if (point.filterCrag) query.set("crag", point.filterCrag);
      }
      return `<a href="/climbing/?${query.toString()}">${escapeHtml(point.name)}</a>`;
    };
    const hasMultipleCrags = (point) => points.filter((candidate) => candidate.parent === point.name && candidate.level === "crag").length > 1;
    const hasMultipleLocations = (point) => points.filter((candidate) => candidate.parent === point.name && candidate.level === "location").length > 0;
    // States provide geographic context; single-crag locations can use the crag pin directly.
    const overviewPoints = () => points
      .filter((point) => point.level === "location")
      .flatMap((location) => {
        const crags = points.filter((point) => point.parent === location.name && point.level === "crag");
        return crags.length === 1 ? crags : [location];
      });
    const scopedMapPoints = () => {
      const scope = currentScope();
      const selectedCrag = scope.crag;
      const selectedLocation = scope.location;
      const selectedWall = scope.wall;
      const selectedMapLocation = scope.mapLocation;
      if (selectedMapLocation) {
        const children = points.filter((point) => normalizeFilterValue(point.parent) === selectedMapLocation);
        return children.length
          ? children
          : points.filter((point) => normalizeFilterValue(point.name) === selectedMapLocation);
      }
      if (!selectedCrag && !selectedLocation) return points;
      const crag = points.find((point) => normalizeFilterValue(point.name) === selectedCrag);
      const childCrags = points.filter((point) => normalizeFilterValue(point.parent) === (selectedCrag || selectedLocation));
      return points.filter((point) => {
        const pointName = normalizeFilterValue(point.name);
        const pointParent = normalizeFilterValue(point.parent);
        const selectedParent = normalizeFilterValue(crag?.parent);
        if (selectedLocation && !selectedCrag) return pointParent === selectedLocation;
        if (selectedCrag) return pointName === selectedCrag;
        if (!selectedWall && childCrags.length) return pointParent === selectedCrag;
        return pointName === selectedCrag || pointParent === selectedCrag || (selectedParent && pointName === selectedParent);
      });
    };
    const renderLocationMarkers = (fitToScope = false) => {
      map.eachLayer((layer) => {
        if (layer instanceof L.Marker) map.removeLayer(layer);
      });
      const scopedPoints = scopedMapPoints();
      const zoomedIn = map.getZoom() >= 9;
      const hasScope = scopedPoints !== points;
      const visiblePoints = hasScope ? scopedPoints : scopedPoints.filter((point) => zoomedIn ? point.level === "crag" : overviewPoints().includes(point));
      const markers = visiblePoints.map((point) => {
        const parent = point.parent ? points.find((candidate) => candidate.name === point.parent) : null;
        const children = points.filter((candidate) => candidate.parent === point.name);
        const titlePoint = point;
        const related = point.level === "location" ? children : [];
        const links = [...new Map(related.map((relatedPoint) => [relatedPoint.name, locationLink(relatedPoint)])).values()];
        const popup = `<strong>${locationLink(titlePoint)}</strong>${links.length ? `<ul>${links.map((link) => `<li>${link}</li>`).join("")}</ul>` : ""}`;
        return L.marker([Number(point.latitude), Number(point.longitude)]).addTo(map).bindPopup(popup);
      });
      if (fitToScope && markers.length) map.fitBounds(L.featureGroup(markers).getBounds().pad(0.25));
    };

    refreshMap = () => renderLocationMarkers(true);
    renderLocationMarkers(true);
      map.on("zoomend", () => renderLocationMarkers(false));
      const hasLocationScope = new URLSearchParams(window.location.search).has("location") || new URLSearchParams(window.location.search).has("crag") || new URLSearchParams(window.location.search).has("map");
      const initialPoints = overviewPoints();
      if (!hasLocationScope && initialPoints.length) map.fitBounds(L.featureGroup(initialPoints.map((point) => L.marker([Number(point.latitude), Number(point.longitude)]))).getBounds().pad(0.25));
      mapElement.dataset.mapInitialized = "true";
      return true;
    } catch (error) {
      console.error("Climbing map initialization failed", error);
      showMapFallback("The climbing map could not be initialized. The climbing location data is still available below.");
      return false;
    }
  };

  if (mapElement && !initializeMap()) {
    const leafletScript = document.querySelector('script[src*="unpkg.com/leaflet"]');
    if (leafletScript) {
      leafletScript.addEventListener("load", () => initializeMap());
      leafletScript.addEventListener("error", showMapFallback);
      window.addEventListener("load", () => initializeMap(), { once: true });
      window.setTimeout(() => {
        if (!mapElement.dataset.mapInitialized && !window.L) showMapFallback();
      }, 2500);
    } else {
      showMapFallback();
    }
  }

  const gradeInfo = (card) => {
    const grade = card.dataset.grade.toLowerCase();
    const boulder = grade.match(/^v(\d+)/);
    if (boulder) return { kind: "bouldering", value: Number(boulder[1]), minimum: Number(boulder[1]), maximum: Number(boulder[1]), label: `V${boulder[1]}` };

    const sport = grade.match(/^5\.(\d+)([a-d]?)/);
    if (sport) {
      const label = `5.${sport[1]}${sport[2]}`;
      const value = ydsGrades.indexOf(label);
      if (value >= 0) return { kind: "sport", value, minimum: value, maximum: value, label };
      const number = Number(sport[1]);
      if (!sport[2] && number >= 10) {
        const minimum = ydsGrades.indexOf(`5.${number}a`);
        const maximum = ydsGrades.indexOf(`5.${number}d`);
        if (minimum >= 0 && maximum >= 0) return { kind: "sport", value: minimum, minimum, maximum, label: `5.${number}` };
      }
    }

    return { kind: "unknown", value: 0, label: card.dataset.grade };
  };

  const cardGrades = new Map(cards.map((card) => [card, gradeInfo(card)]));

// Make whole card clickable (except internal links)
cards.forEach(card => {
  card.addEventListener('click', (e) => {
    // If click originated from a link, let default behavior occur
    if (e.target.closest('a')) return;
    const mediaLink = card.querySelector('a.climbing-card__media');
    const titleLink = card.querySelector('h2 a');
    const target = mediaLink || titleLink;
    if (target && target.href) {
      window.location.href = target.href;
    }
  });
});
  const cragFilter = browser.querySelector('[data-filter="crag"]');
  const locationFilter = browser.querySelector('[data-filter="location"]');
  const initialLocation = scopedLocation;
  const initialCrag = scopedCrag;
  const cragLabels = new Map([...cragFilter.options].map((option) => [normalizeFilterValue(option.value), option.textContent]));
  const updateCragOptions = (locationValue) => {
    const selectedCrag = normalizeFilterValue(cragFilter.value);
    const availableCrags = [...new Set(cards
      .filter((card) => !locationValue || normalizeFilterValue(card.dataset.location) === locationValue)
      .map((card) => normalizeFilterValue(card.dataset.crag))
      .filter(Boolean))]
      .sort((left, right) => (cragLabels.get(left) || left).localeCompare(cragLabels.get(right) || right));
    cragFilter.replaceChildren(new Option("All crags", ""), ...availableCrags.map((crag) => new Option(cragLabels.get(crag) || crag, crag)));
    cragFilter.value = availableCrags.includes(selectedCrag) ? selectedCrag : "";
  };
  if (initialLocation && locationFilter) {
    const matchingLocation = [...locationFilter.options].find((option) => normalizeFilterValue(option.value) === initialLocation);
    if (matchingLocation) locationFilter.value = matchingLocation.value;
  }
  updateCragOptions(normalizeFilterValue(locationFilter?.value));
  if (initialCrag) {
    const matchingOption = [...cragFilter.options].find((option) => normalizeFilterValue(option.value) === initialCrag);
    if (matchingOption) cragFilter.value = matchingOption.value;
  }

  ["bouldering", "sport"].forEach((kind) => {
    const values = cards.map((card) => cardGrades.get(card)).filter((grade) => grade.kind === kind).flatMap((grade) => [grade.minimum, grade.maximum]);
    if (!values.length) return;

    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    ranges[kind] = { minimum, maximum };

    ["min", "max"].forEach((bound) => {
      const input = browser.querySelector(`[data-grade-input="${kind}-${bound}"]`);
      input.min = minimum;
      input.max = maximum;
      input.step = 1;
      input.value = bound === "min" ? minimum : maximum;
      input.addEventListener("input", () => {
        const other = browser.querySelector(`[data-grade-input="${kind}-${bound === "min" ? "max" : "min"}"]`);
        if (bound === "min" && Number(input.value) > Number(other.value)) input.value = other.value;
        if (bound === "max" && Number(input.value) < Number(other.value)) input.value = other.value;
        updateRangeTrack(kind);
        update();
      });
    });
  });

  const formatGrade = (kind, value) => {
    if (kind === "bouldering") return `V${value}`;
    return ydsGrades[Math.round(value)] || "5.0";
  };

  const updateRangeLabels = () => {
    Object.keys(ranges).forEach((kind) => {
      ["min", "max"].forEach((bound) => {
        const input = browser.querySelector(`[data-grade-input="${kind}-${bound}"]`);
        const output = browser.querySelector(`[data-grade-output="${kind}-${bound}"]`);
        output.textContent = formatGrade(kind, Number(input.value));
      });
    });
  };

  const updateRangeTrack = (kind) => {
    const minimum = browser.querySelector(`[data-grade-input="${kind}-min"]`);
    const maximum = browser.querySelector(`[data-grade-input="${kind}-max"]`);
    const track = browser.querySelector(`[data-grade-range="${kind}"] .climbing-dual-range__track`);
    if (!minimum || !maximum || !track || Number(minimum.max) === Number(minimum.min)) return;
    const start = ((Number(minimum.value) - Number(minimum.min)) / (Number(minimum.max) - Number(minimum.min))) * 100;
    const end = ((Number(maximum.value) - Number(maximum.min)) / (Number(maximum.max) - Number(maximum.min))) * 100;
    track.style.setProperty("--range-start", `${start}%`);
    track.style.setProperty("--range-end", `${end}%`);
  };

  const update = () => {
    const activeFilters = Object.fromEntries(filters.map((filter) => [filter.dataset.filter, normalizeFilterValue(filter.value)]));
    const selectedType = activeFilters.discipline;
    const selectedBouldering = selectedType === "boulder" || selectedType === "bouldering";

    rangeGroups.forEach((group) => {
      group.hidden = Boolean(selectedType && group.dataset.gradeRange !== (selectedBouldering ? "bouldering" : "sport"));
    });
    updateRangeLabels();
    updateRangeTrack("bouldering");
    updateRangeTrack("sport");

    const visible = cards.filter((card) => {
      const grade = cardGrades.get(card);
      const matchesBasicFilters = Object.entries(activeFilters).every(([key, value]) => !value || card.dataset[key] === value);
      const scope = currentScope();
      const matchesMapScope = scope.mapLocation
        ? normalizeFilterValue(card.dataset.location) === scope.mapLocation || normalizeFilterValue(card.dataset.crag) === scope.mapLocation
        : (!scope.location || normalizeFilterValue(card.dataset.location) === scope.location)
          && (!scope.crag || normalizeFilterValue(card.dataset.crag) === scope.crag)
          && (!scope.wall || normalizeFilterValue(card.dataset.wall).startsWith(scope.wall));
      const range = ranges[grade.kind];
      if (!matchesBasicFilters || !matchesMapScope || !range) return matchesBasicFilters && matchesMapScope;

      const minimum = Number(browser.querySelector(`[data-grade-input="${grade.kind}-min"]`).value);
      const maximum = Number(browser.querySelector(`[data-grade-input="${grade.kind}-max"]`).value);
      return grade.maximum >= minimum && grade.minimum <= maximum;
    });
    cards.forEach((card) => { card.hidden = !visible.includes(card); });
    [...visible].sort((left, right) => {
      const videoPriority = Number(right.dataset.video) - Number(left.dataset.video);
      if (videoPriority) return videoPriority;
      const mode = sortSelect.value;
      if (mode === "title") return left.dataset.title.localeCompare(right.dataset.title);
      if (mode === "location") return left.dataset.location.localeCompare(right.dataset.location);
      if (mode === "grade") {
        const leftGrade = cardGrades.get(left);
        const rightGrade = cardGrades.get(right);
        return leftGrade.kind.localeCompare(rightGrade.kind) || rightGrade.value - leftGrade.value;
      }
      const comparison = left.dataset.date.localeCompare(right.dataset.date);
      return mode === "date-asc" ? comparison : -comparison;
    }).forEach((card) => grid.appendChild(card));

    resultCount.textContent = `${visible.length} ${visible.length === 1 ? "entry" : "entries"}`;
    empty.hidden = visible.length !== 0;
  };

  filters.forEach((filter) => filter.addEventListener("change", () => {
    if (filter.dataset.filter === "location") {
      scopedLocation = normalizeFilterValue(filter.value);
      scopedCrag = "";
      updateCragOptions(scopedLocation);
      const url = new URL(window.location.href);
      if (filter.value) url.searchParams.set("location", filter.value);
      else url.searchParams.delete("location");
      url.searchParams.delete("crag");
      url.searchParams.delete("wall");
      window.history.replaceState({}, "", url);
      scopedWall = "";
      if (cragFilter) cragFilter.value = "";
      if (mapReset) mapReset.hidden = !filter.value;
    } else if (filter.dataset.filter === "crag") {
      scopedCrag = normalizeFilterValue(filter.value);
      scopedWall = "";
      const url = new URL(window.location.href);
      if (filter.value) url.searchParams.set("crag", filter.value);
      else url.searchParams.delete("crag");
      url.searchParams.delete("wall");
      window.history.replaceState({}, "", url);
      if (mapReset) mapReset.hidden = !filter.value;
    }
    update();
    refreshMap();
  }));
  sortSelect.addEventListener("change", update);
  update();
});
