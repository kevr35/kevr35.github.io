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

  const mapElement = document.querySelector("[data-map-points]");
  if (mapElement && window.L) {
    const map = L.map(mapElement).setView([39.8, -81.5], 7);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);

    const points = JSON.parse(mapElement.dataset.mapPoints);
    const areas = new Map();
    points.forEach((point) => {
      if (!areas.has(point.location)) areas.set(point.location, { ...point, routes: [] });
      areas.get(point.location).routes.push(point);
    });

    const markers = [...areas.values()].map((area) => {
      const routeLinks = area.routes.map((route) => `<li><a href="${route.url}">${route.title} <span>${route.grade}</span></a></li>`).join("");
      return L.marker([Number(area.latitude), Number(area.longitude)]).addTo(map).bindPopup(`<strong>${area.location}</strong><ul>${routeLinks}</ul>`);
    });

    if (markers.length) map.fitBounds(L.featureGroup(markers).getBounds().pad(0.25));
  }

  const gradeInfo = (card) => {
    const grade = card.dataset.grade.toLowerCase();
    const boulder = grade.match(/^v(\d+)/);
    if (boulder) return { kind: "bouldering", value: Number(boulder[1]), label: `V${boulder[1]}` };

    const sport = grade.match(/^5\.(\d+)([a-d]?)/);
    if (sport) {
      const letter = sport[2] ? sport[2].charCodeAt(0) - 96 : 0;
      return { kind: "sport", value: Number(sport[1]) * 10 + letter, label: `5.${sport[1]}${sport[2]}` };
    }

    return { kind: "unknown", value: 0, label: card.dataset.grade };
  };

  const cardGrades = new Map(cards.map((card) => [card, gradeInfo(card)]));

  ["bouldering", "sport"].forEach((kind) => {
    const values = cards.map((card) => cardGrades.get(card)).filter((grade) => grade.kind === kind).map((grade) => grade.value);
    if (!values.length) return;

    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    ranges[kind] = { minimum, maximum };

    ["min", "max"].forEach((bound) => {
      const input = browser.querySelector(`[data-grade-input="${kind}-${bound}"]`);
      input.min = minimum;
      input.max = maximum;
      input.value = bound === "min" ? minimum : maximum;
      input.addEventListener("input", () => {
        const other = browser.querySelector(`[data-grade-input="${kind}-${bound === "min" ? "max" : "min"}"]`);
        if (bound === "min" && Number(input.value) > Number(other.value)) input.value = other.value;
        if (bound === "max" && Number(input.value) < Number(other.value)) input.value = other.value;
        update();
      });
    });
  });

  const formatGrade = (kind, value) => {
    if (kind === "bouldering") return `V${value}`;
    const number = Math.floor(value / 10);
    const letter = value % 10;
    return `5.${number}${letter ? String.fromCharCode(96 + letter) : ""}`;
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

  const update = () => {
    const activeFilters = Object.fromEntries(filters.map((filter) => [filter.dataset.filter, filter.value]));
    const selectedType = activeFilters.discipline;
    const selectedBouldering = selectedType === "boulder" || selectedType === "bouldering";

    rangeGroups.forEach((group) => {
      group.hidden = Boolean(selectedType && group.dataset.gradeRange !== (selectedBouldering ? "bouldering" : "sport"));
    });
    updateRangeLabels();

    const visible = cards.filter((card) => {
      const grade = cardGrades.get(card);
      const matchesBasicFilters = Object.entries(activeFilters).every(([key, value]) => !value || card.dataset[key] === value);
      const range = ranges[grade.kind];
      if (!matchesBasicFilters || !range) return matchesBasicFilters;

      const minimum = Number(browser.querySelector(`[data-grade-input="${grade.kind}-min"]`).value);
      const maximum = Number(browser.querySelector(`[data-grade-input="${grade.kind}-max"]`).value);
      return grade.value >= minimum && grade.value <= maximum;
    });

    cards.forEach((card) => { card.hidden = !visible.includes(card); });
    [...visible].sort((left, right) => {
      const mode = sortSelect.value;
      if (mode === "title") return left.dataset.title.localeCompare(right.dataset.title);
      if (mode === "grade") {
        const leftGrade = cardGrades.get(left);
        const rightGrade = cardGrades.get(right);
        return leftGrade.kind.localeCompare(rightGrade.kind) || leftGrade.value - rightGrade.value;
      }
      const comparison = left.dataset.date.localeCompare(right.dataset.date);
      return mode === "date-asc" ? comparison : -comparison;
    }).forEach((card) => grid.appendChild(card));

    resultCount.textContent = `${visible.length} ${visible.length === 1 ? "entry" : "entries"}`;
    empty.hidden = visible.length !== 0;
  };

  filters.forEach((filter) => filter.addEventListener("change", update));
  sortSelect.addEventListener("change", update);
  update();
});
