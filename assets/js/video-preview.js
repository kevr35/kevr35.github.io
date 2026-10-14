(() => {
  // Touch devices have no hover, so they keep the static thumbnail.
  if (!window.matchMedia("(hover: hover)").matches) return;

  document.querySelectorAll("[data-preview-media][data-youtube-id]").forEach((media) => {
    const card = media.closest(".climbing-card, .indoor-card, .home-climbing-card");
    if (!card) return;
    const id = media.dataset.youtubeId;
    let frame = null;

    const start = () => {
      if (frame) return;
      frame = document.createElement("iframe");
      frame.className = "video-preview";
      frame.tabIndex = -1;
      frame.setAttribute("aria-hidden", "true");
      frame.allow = "autoplay; encrypted-media";
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      // Muted autoplay is permitted by browsers; loop needs the playlist param.
      frame.src =
        `https://www.youtube-nocookie.com/embed/${id}` +
        `?autoplay=1&mute=1&controls=0&loop=1&playlist=${id}` +
        `&playsinline=1&modestbranding=1&rel=0&disablekb=1` +
        `&cc_load_policy=0&iv_load_policy=3&fs=0`;
      media.appendChild(frame);
    };

    const stop = () => {
      frame?.remove();
      frame = null;
    };

    card.addEventListener("mouseenter", start);
    card.addEventListener("mouseleave", stop);
    card.addEventListener("focusin", start);
    card.addEventListener("focusout", stop);
  });
})();
