/**
 * FOLDO — progressive UI enhancements (ES6 module).
 *
 * Every page works with JavaScript disabled; these only add small comforts on
 * top of the server-rendered Django templates. Each feature is opt-in through a
 * data-* attribute so templates stay declarative.
 */

/** Top bar / navbar gets a border once the page is scrolled. */
function enableTopbarScrollState() {
  const bars = document.querySelectorAll("[data-topbar]");
  if (!bars.length) return;
  const apply = () => bars.forEach((bar) => bar.classList.toggle("is-scrolled", window.scrollY > 8));
  apply();
  window.addEventListener("scroll", apply, { passive: true });
}

/**
 * Toasts: success messages leave on their own after a few seconds (paused while
 * hovered or focused); warnings and errors stay until dismissed.
 */
function enableToasts() {
  const stack = document.querySelector("[data-toasts]");
  if (!stack) return;
  stack.classList.add("is-enhanced");
  stack.querySelectorAll(".foldo-toast--success, .foldo-toast--info").forEach((toast) => {
    let timer;
    const leave = () => {
      toast.classList.add("is-leaving");
      toast.addEventListener("animationend", () => toast.remove(), { once: true });
    };
    const start = () => { timer = window.setTimeout(leave, 5500); };
    const stop = () => window.clearTimeout(timer);
    toast.addEventListener("mouseenter", stop);
    toast.addEventListener("mouseleave", start);
    toast.addEventListener("focusin", stop);
    toast.addEventListener("focusout", start);
    start();
  });
}

/**
 * Loading state: a <form data-loading> disables its submit buttons on submit,
 * swaps in data-loading-text with a spinner and sets aria-busy.
 */
function enableFormLoadingState() {
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const submitter = event.submitter;
      form.setAttribute("aria-busy", "true");
      // Defer so the browser still sends the clicked button's name/value.
      window.setTimeout(() => {
        form.querySelectorAll('button[type="submit"]').forEach((button) => {
          button.disabled = true;
          if (button !== submitter && submitter) return;
          const text = button.dataset.loadingText;
          if (!text) return;
          const spinner = document.createElement("span");
          spinner.className = "spinner-border spinner-border-sm";
          spinner.setAttribute("aria-hidden", "true");
          button.replaceChildren(spinner, " ", text);
        });
      }, 0);
    });
  });
}

/** Copy to clipboard: <button data-copy="#input-id" data-copy-status="#status">. */
function enableCopyButtons() {
  document.querySelectorAll("[data-copy]").forEach((button) => {
    const source = document.querySelector(button.dataset.copy);
    if (!source) return;
    const status = document.querySelector(button.dataset.copyStatus || "");
    const label = button.querySelector("[data-copy-label]") || button;
    const original = label.textContent;
    button.hidden = false;

    const say = (message, ok) => {
      if (status) status.textContent = message;
      label.textContent = message;
      button.classList.toggle("is-copied", ok);
      window.setTimeout(() => {
        label.textContent = original;
        button.classList.remove("is-copied");
      }, 1800);
    };

    button.addEventListener("click", async () => {
      const text = source.value ?? source.textContent;
      try {
        if (!navigator.clipboard || !window.isSecureContext) throw new Error("no clipboard");
        await navigator.clipboard.writeText(text);
        say("คัดลอกแล้ว!", true);
      } catch {
        source.select?.();
        let ok = false;
        try { ok = document.execCommand("copy"); } catch { ok = false; }
        say(ok ? "คัดลอกแล้ว!" : "กด Ctrl+C เพื่อคัดลอก", ok);
      }
    });
  });
}

/** Native share sheet where supported: <button data-share-url="…" data-share-title="…" hidden>. */
function enableWebShare() {
  if (!navigator.share) return;
  document.querySelectorAll("[data-share-url]").forEach((button) => {
    button.hidden = false;
    button.addEventListener("click", () => {
      navigator.share({ title: button.dataset.shareTitle || document.title, url: button.dataset.shareUrl })
        .catch(() => {});
    });
  });
}

/**
 * Filter chips: <div data-filter-group="themes"> with <button data-filter="key">
 * filters items with data-filter-item="themes" data-filter-tags="key other".
 */
function enableFilters() {
  document.querySelectorAll("[data-filter-group]").forEach((group) => {
    const name = group.dataset.filterGroup;
    const items = document.querySelectorAll(`[data-filter-item="${name}"]`);
    const count = document.querySelector(`[data-filter-count="${name}"]`);
    group.hidden = false;
    group.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-filter]");
      if (!chip) return;
      const key = chip.dataset.filter;
      group.querySelectorAll("[data-filter]").forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
      let shown = 0;
      items.forEach((item) => {
        const match = key === "all" || (item.dataset.filterTags || "").split(" ").includes(key);
        item.hidden = !match;
        if (match) shown += 1;
      });
      if (count) count.textContent = String(shown);
    });
  });
}

/**
 * Live preview: <span data-live-source="#id_full_name"> mirrors that input as
 * the user types (data-live-fallback when empty; data-live-initials for "AB").
 */
function enableLivePreview() {
  document.querySelectorAll("[data-live-source]").forEach((target) => {
    const input = document.querySelector(target.dataset.liveSource);
    if (!input) return;
    const update = () => {
      const value = input.value.trim();
      if (target.hasAttribute("data-live-initials")) {
        target.textContent = value.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase() || "?";
      } else {
        target.textContent = value || target.dataset.liveFallback || "";
      }
    };
    input.addEventListener("input", update);
  });
}

/**
 * Error summary: after a failed submit, move focus to the summary so everyone
 * hears what went wrong; its links focus (not just scroll to) the bad field.
 */
function enableErrorSummary() {
  const summary = document.querySelector("[data-error-summary]");
  if (!summary) return;
  summary.focus({ preventScroll: false });
  summary.addEventListener("click", (event) => {
    const link = event.target.closest("a[href^='#']");
    if (!link) return;
    const target = document.getElementById(link.getAttribute("href").slice(1));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ block: "center" });
    target.focus({ preventScroll: true });
  });
}

/**
 * Deep links such as /profiles/3/edit/#id_headline (from "next step" cards and
 * Quality Check) land on the field itself: focus it and briefly highlight it.
 */
function enableFieldDeepLinks() {
  const id = decodeURIComponent(window.location.hash.slice(1));
  if (!id) return;
  const target = document.getElementById(id);
  if (!target || !target.matches("input, select, textarea, fieldset, section")) return;
  const box = target.closest(".mb-3, .foldo-switch-row, fieldset, section") || target;
  window.requestAnimationFrame(() => {
    target.scrollIntoView({ block: "center" });
    if (target.matches("input, select, textarea")) target.focus({ preventScroll: true });
    box.classList.add("is-spotlit");
    window.setTimeout(() => box.classList.remove("is-spotlit"), 2400);
  });
}

/**
 * Unsaved changes: <form data-unsaved-guard> warns before the page is left with
 * edits that were never saved (a re-shown form after a failed save counts as
 * unsaved). An optional [data-unsaved-note] inside the form says so in words.
 */
function enableUnsavedGuard() {
  const forms = Array.from(document.querySelectorAll("form[data-unsaved-guard]"));
  if (!forms.length) return;

  const snapshot = (form) => {
    const parts = [];
    new FormData(form).forEach((value, key) => {
      if (key === "csrfmiddlewaretoken") return;
      parts.push(`${key}=${value instanceof File ? `${value.name}:${value.size}` : value}`);
    });
    return parts.join("&");
  };

  const state = new Map();
  forms.forEach((form) => {
    const note = form.querySelector("[data-unsaved-note]");
    const original = note ? note.textContent : "";
    const entry = {
      initial: snapshot(form),
      // A form re-shown with errors holds typed-but-unsaved data from the start.
      forced: Boolean(form.querySelector(".is-invalid")),
      submitting: false,
    };
    state.set(form, entry);

    const refresh = () => {
      const dirty = entry.forced || snapshot(form) !== entry.initial;
      form.classList.toggle("is-dirty", dirty);
      if (note) {
        note.textContent = dirty ? "มีการเปลี่ยนแปลงที่ยังไม่บันทึก" : original;
        note.classList.toggle("is-dirty", dirty);
      }
    };
    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);
    form.addEventListener("submit", () => { entry.submitting = true; });
    refresh();
  });

  window.addEventListener("beforeunload", (event) => {
    for (const [form, entry] of state) {
      if (entry.submitting) continue;
      if (entry.forced || snapshot(form) !== entry.initial) {
        event.preventDefault();
        event.returnValue = "";
        return;
      }
    }
  });
}

/**
 * Busy links: <a href="…/pdf/" data-busy-text="กำลังสร้าง PDF…"> shows a spinner
 * while the server builds a download (the page itself does not change).
 */
function enableBusyLinks() {
  document.querySelectorAll("a[data-busy-text]").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (link.getAttribute("aria-busy") === "true") {
        event.preventDefault();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.shiftKey) return;
      const original = Array.from(link.childNodes).map((node) => node.cloneNode(true));
      const spinner = document.createElement("span");
      spinner.className = "spinner-border spinner-border-sm";
      spinner.setAttribute("aria-hidden", "true");
      link.setAttribute("aria-busy", "true");
      link.classList.add("is-busy");
      link.replaceChildren(spinner, " ", link.dataset.busyText);
      window.setTimeout(() => {
        link.replaceChildren(...original);
        link.removeAttribute("aria-busy");
        link.classList.remove("is-busy");
      }, 6000);
    });
  });
}

/**
 * Publish switch: explain the consequence of turning publishing on or off
 * before the user saves ([data-publish-note="on|off"] next to #id_is_published).
 */
function enablePublishNotes() {
  const toggle = document.getElementById("id_is_published");
  if (!toggle) return;
  const notes = document.querySelectorAll("[data-publish-note]");
  if (!notes.length) return;
  const wasOn = toggle.checked;
  const apply = () => {
    notes.forEach((note) => {
      const kind = note.dataset.publishNote;
      note.hidden = !((kind === "off" && wasOn && !toggle.checked) || (kind === "on" && !wasOn && toggle.checked));
    });
  };
  toggle.addEventListener("change", apply);
  apply();
}

/**
 * Project Story meter: <div data-story-meter> counts how many of the story
 * textareas ([data-story-field]) have text, live, so progress is visible.
 */
function enableStoryMeter() {
  const meter = document.querySelector("[data-story-meter]");
  if (!meter) return;
  const fields = Array.from(document.querySelectorAll("[data-story-field] textarea, [data-story-field] input"));
  const count = meter.querySelector("[data-story-count]");
  const bar = meter.querySelector("[data-story-bar]");
  const update = () => {
    const filled = fields.filter((field) => field.value.trim()).length;
    if (count) count.textContent = String(filled);
    if (bar) bar.style.width = `${(100 * filled) / (fields.length || 1)}%`;
    meter.classList.toggle("is-complete", filled === fields.length);
  };
  fields.forEach((field) => field.addEventListener("input", update));
  update();
}

/**
 * Field map: <li data-fieldmap="id_headline"> turns "done" as soon as that
 * field has a value, so the checklist beside a form is never stale.
 */
function enableFieldMap() {
  document.querySelectorAll("[data-fieldmap]").forEach((item) => {
    const input = document.getElementById(item.dataset.fieldmap);
    const icon = item.querySelector(".foldo-icon");
    if (!input || !icon) return;
    const optional = item.classList.contains("is-optional");
    const update = () => {
      const done = input.type === "file" ? input.files.length > 0 || item.classList.contains("is-done") : Boolean(input.value.trim());
      item.classList.toggle("is-done", done);
      icon.className = `foldo-icon foldo-icon--${done ? "check-circle" : optional ? "info" : "x"}`;
    };
    input.addEventListener("input", update);
    input.addEventListener("change", update);
  });
}

/** Builder stepper: on narrow screens it scrolls sideways; keep the current step visible. */
function revealCurrentStep() {
  const current = document.querySelector('.foldo-flow [aria-current="step"]');
  const strip = current && current.closest(".foldo-flow");
  if (!strip || strip.scrollWidth <= strip.clientWidth) return;
  strip.scrollLeft = current.parentElement.offsetLeft - 16;
}

function init() {
  enableTopbarScrollState();
  enableToasts();
  enableFormLoadingState();
  enableCopyButtons();
  enableWebShare();
  enableFilters();
  enableLivePreview();
  enableErrorSummary();
  enableFieldDeepLinks();
  enableUnsavedGuard();
  enableBusyLinks();
  enablePublishNotes();
  enableStoryMeter();
  enableFieldMap();
  revealCurrentStep();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
