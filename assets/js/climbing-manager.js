(() => {
  const isLocalEditor = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const editMode = new URLSearchParams(window.location.search).get("edit") === "1";
  const browser = document.querySelector("[data-climbing-browser]");
  if (!isLocalEditor || !editMode || !browser) return;

  browser.classList.add("climbing-browser--editing");
  document.querySelectorAll("[data-route-card]").forEach((card) => {
    const routeTitle = card.querySelector("h2")?.textContent.trim() || "route";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "climbing-card__edit";
    button.setAttribute("aria-label", `Edit ${routeTitle}`);
    button.innerHTML = "&#9998; Edit route";
    button.addEventListener("click", () => window.openClimbingRouteEditor?.(card.dataset.routeFile, routeTitle));
    card.querySelector(".climbing-card__body")?.append(button);
  });

  const notice = document.createElement("p");
  notice.className = "climbing-results";
  notice.textContent = "Local edit mode: choose Edit route on any card to update it and rebuild the site.";
  browser.prepend(notice);
})();
