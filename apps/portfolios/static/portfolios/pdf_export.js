// Export page for a portfolio version (FOLDO-11). Progressive enhancement: without
// JavaScript the form is a plain download of the chosen page size. With it, the PDF is
// requested in the background so the page can show progress, success, failure and retry.
(function () {
  var root = document.querySelector("[data-export]");
  if (!root) return;

  var form = root.querySelector("[data-export-form]");
  var panels = {};
  root.querySelectorAll("[data-state-panel]").forEach(function (el) {
    panels[el.getAttribute("data-state-panel")] = el;
  });
  var timeoutMs = (parseInt(root.getAttribute("data-timeout"), 10) || 150) * 1000;
  var controller = null, timer = null, started = 0, objectUrl = null;

  function show(name) {
    Object.keys(panels).forEach(function (key) { panels[key].hidden = key !== name; });
    form.hidden = name === "progress";
  }

  function clearTimer() { if (timer) { window.clearInterval(timer); timer = null; } }

  function releaseResult() {
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
  }

  function fail(message) {
    clearTimer();
    root.querySelector("[data-error-text]").textContent = message;
    show("failure");
  }

  function sizeText(bytes) {
    return bytes > 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function filenameFrom(response, fallback) {
    var match = /filename="?([^";]+)"?/i.exec(response.headers.get("Content-Disposition") || "");
    return match ? match[1] : fallback;
  }

  function start() {
    releaseResult();
    var size = (form.querySelector('input[name="size"]:checked') || {}).value || "";
    var url = form.getAttribute("action") + "?size=" + encodeURIComponent(size);
    controller = new AbortController();
    var timedOut = false;
    var killer = window.setTimeout(function () { timedOut = true; controller.abort(); }, timeoutMs);

    started = Date.now();
    root.querySelector("[data-elapsed]").textContent = "0";
    clearTimer();
    timer = window.setInterval(function () {
      root.querySelector("[data-elapsed]").textContent = Math.floor((Date.now() - started) / 1000);
    }, 500);
    show("progress");

    fetch(url, { credentials: "same-origin", signal: controller.signal, headers: { "X-Foldo-Export": "1" } })
      .then(function (response) {
        var type = response.headers.get("Content-Type") || "";
        if (response.ok && type.indexOf("application/pdf") === 0) {
          return response.blob().then(function (blob) {
            if (!blob.size) throw new Error("ไฟล์ PDF ที่ได้ว่างเปล่า ลองอีกครั้ง");
            return { blob: blob, name: filenameFrom(response, "portfolio.pdf") };
          });
        }
        // A server-side failure comes back as JSON; anything else (e.g. a login page) is not a PDF.
        return response.json().catch(function () { return {}; }).then(function (body) {
          throw new Error(body.error || "เซิร์ฟเวอร์ไม่ได้ส่ง PDF กลับมา (รหัส " + response.status + ") ลองอีกครั้ง");
        });
      })
      .then(function (result) {
        window.clearTimeout(killer);
        clearTimer();
        objectUrl = URL.createObjectURL(result.blob);
        var download = root.querySelector("[data-export-download]");
        download.href = objectUrl;
        download.setAttribute("download", result.name);
        root.querySelector("[data-export-open]").href = objectUrl;
        root.querySelector("[data-result-name]").textContent = result.name;
        root.querySelector("[data-result-size]").textContent = sizeText(result.blob.size);
        show("success");
      })
      .catch(function (error) {
        window.clearTimeout(killer);
        if (error && error.name === "AbortError") {
          if (timedOut) {
            fail("ใช้เวลานานเกินไป ลองอีกครั้ง หรือเลือกเนื้อหาให้น้อยลง");
          } else { // the user pressed Cancel: back to the form
            clearTimer(); hideAll(); form.hidden = false;
          }
          return;
        }
        fail(error && error.message ? error.message : "ติดต่อเซิร์ฟเวอร์ไม่ได้ ตรวจอินเทอร์เน็ตแล้วลองอีกครั้ง");
      });
  }

  function hideAll() {
    Object.keys(panels).forEach(function (key) { panels[key].hidden = true; });
  }

  form.addEventListener("submit", function (event) {
    if (!window.fetch || !window.AbortController || !window.URL || !URL.createObjectURL) return; // plain download
    event.preventDefault();
    start();
  });
  root.querySelector("[data-export-retry]").addEventListener("click", start);
  root.querySelector("[data-export-again]").addEventListener("click", function () {
    releaseResult(); hideAll(); form.hidden = false;
  });
  root.querySelector("[data-export-cancel]").addEventListener("click", function () {
    if (controller) controller.abort();
  });
})();
