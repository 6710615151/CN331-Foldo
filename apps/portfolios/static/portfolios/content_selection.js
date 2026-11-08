// Progressive enhancement for the content selection page (FOLDO-06).
// Without JS the checkboxes and Save button still work; this adds live counts
// and per-section "All / None" buttons.
(function () {
  document.querySelectorAll("[data-cs-section]").forEach(function (section) {
    var boxes = Array.prototype.slice.call(section.querySelectorAll('input[type="checkbox"]'));
    var count = section.querySelector("[data-cs-count]");
    var bulk = section.querySelector("[data-cs-bulk]");

    function update() {
      if (!count) return;
      var on = boxes.filter(function (b) { return b.checked; }).length;
      count.textContent = on + " / " + boxes.length;
    }

    boxes.forEach(function (box) { box.addEventListener("change", update); });

    if (bulk) {
      bulk.hidden = false;
      bulk.addEventListener("click", function (event) {
        var button = event.target.closest("button[data-cs-set]");
        if (!button) return;
        var checked = button.getAttribute("data-cs-set") === "all";
        boxes.forEach(function (box) { box.checked = checked; });
        update();
      });
    }
    update();
  });
})();
