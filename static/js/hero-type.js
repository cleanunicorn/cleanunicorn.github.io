/* Hero typewriter — types out the role line after the `~$ whoami` prompt.
   Progressive enhancement: the full text is in the HTML, so it's always
   readable without JS. Skipped entirely when the visitor prefers reduced
   motion (the text just shows as-is). */
(function () {
  "use strict";

  var el = document.querySelector(".home-hero__roles[data-typewriter]");
  if (!el) return;

  var reduce = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;

  var full = el.textContent;
  el.textContent = "";

  var i = 0;
  function tick() {
    el.textContent = full.slice(0, i);
    if (i < full.length) {
      i += 1;
      // Slightly irregular cadence reads more like real typing.
      setTimeout(tick, 32 + Math.random() * 34);
    }
  }

  // Small delay so the prompt registers before typing begins.
  setTimeout(tick, 300);
})();
