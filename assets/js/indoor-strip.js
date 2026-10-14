(() => {
  const track = document.querySelector(".indoor-strip__track");
  const controls = document.querySelector("[data-indoor-controls]");
  const leftButton = document.querySelector("[data-pan-left]");
  const rightButton = document.querySelector("[data-pan-right]");
  if (!track || !controls || !leftButton || !rightButton) return;

  const updateControls = () => {
    const maxScroll = track.scrollWidth - track.clientWidth;
    controls.hidden = maxScroll <= 4;
    leftButton.disabled = track.scrollLeft <= 4;
    rightButton.disabled = maxScroll - track.scrollLeft <= 4;
  };

  const pan = (direction) => {
    const firstCard = track.querySelector(".indoor-card");
    if (!firstCard) return;

    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    const distance = (firstCard.getBoundingClientRect().width + gap) * 2;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    track.scrollBy({ left: direction * distance, behavior: reducedMotion ? "auto" : "smooth" });
  };

  leftButton.addEventListener("click", () => pan(-1));
  rightButton.addEventListener("click", () => pan(1));
  track.addEventListener("scroll", updateControls, { passive: true });
  window.addEventListener("resize", updateControls);
  window.addEventListener("load", updateControls);
  new ResizeObserver(updateControls).observe(track);
  updateControls();
})();
