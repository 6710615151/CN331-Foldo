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

/**
 * Generic loading state: a <form data-loading> disables its submit button on
 * submit, swaps in the button's data-loading-text with a spinner and sets
 * aria-busy. Without JavaScript the form simply submits as normal.
 */
function enableFormLoadingState() {
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", () => {
      form.setAttribute("aria-busy", "true");
      form.querySelectorAll('button[type="submit"]').forEach((button) => {
        // Defer so the browser still submits the form before the button is disabled.
        setTimeout(() => {
          button.disabled = true;
          const text = button.dataset.loadingText;
          if (!text) return;
          const spinner = document.createElement("span");
          spinner.className = "spinner-border spinner-border-sm me-2";
          spinner.setAttribute("aria-hidden", "true");
          button.replaceChildren(spinner, text);
        }, 0);
      });
    });
  });
}

/** Boot the enhancements once the DOM is parsed. */
function init() {
  enableNavbarScrollShadow();
  enableFormLoadingState();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
