/**
 * FOLDO — progressive UI enhancements (ES6 module).
 *
 * Kept deliberately small: this file only adds small, non-essential
 * interactions on top of server-rendered Django templates. The page must work
 * perfectly with JavaScript disabled.
 */

/**
 * Add a subtle shadow to the sticky navbar once the page is scrolled.
 * Uses a passive listener so scrolling stays smooth on mobile.
 */
function enableNavbarScrollShadow() {
  const navbar = document.querySelector(".foldo-navbar");
  if (!navbar) return;

  const applyState = () => navbar.classList.toggle("is-scrolled", window.scrollY > 8);

  applyState();
  window.addEventListener("scroll", applyState, { passive: true });
}

/** Boot the enhancements once the DOM is parsed. */
function init() {
  enableNavbarScrollShadow();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
