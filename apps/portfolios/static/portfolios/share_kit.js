// Copy-link button for the Share Kit (FOLDO-17). Progressive enhancement: the
// button stays hidden without JS, and the URL field can always be selected by hand.
(function () {
  var button = document.getElementById("sk-copy");
  if (!button) return;
  var input = document.querySelector(button.getAttribute("data-copy-target"));
  var status = document.getElementById("sk-copy-status");
  button.hidden = false;

  function say(message) {
    if (status) status.textContent = message;
    var label = button.textContent;
    button.textContent = message;
    window.setTimeout(function () { button.textContent = label; }, 1800);
  }

  button.addEventListener("click", function () {
    var text = input.value;
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(
        function () { say("Copied!"); },
        function () { input.select(); say("Press Ctrl+C to copy"); }
      );
    } else {
      input.select();
      try { say(document.execCommand("copy") ? "Copied!" : "Press Ctrl+C to copy"); }
      catch (error) { say("Press Ctrl+C to copy"); }
    }
  });
})();
