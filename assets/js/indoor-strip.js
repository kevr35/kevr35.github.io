(() => {
  const track = document.querySelector(".indoor-strip__track");
  const hint = document.querySelector("[data-scroll-hint]");
  if (!track || !hint) return;

  // Only show the hint while there are cards scrolled out of view to the right.
  const updateHint = () => {
    hint.hidden = track.scrollWidth - track.clientWidth - track.scrollLeft <= 4;
  };
  track.addEventListener("scroll", updateHint, { passive: true });
  window.addEventListener("resize", updateHint);
  window.addEventListener("load", updateHint);
  // Re-measure when the strip is shown again after being hidden by a map scope.
  new ResizeObserver(updateHint).observe(track);
  updateHint();
})();
