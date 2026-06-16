/* Hero typewriter — types out the role line after the `~$ whoami` prompt.
   Progressive enhancement: the full text is in the HTML, so it's always
   readable without JS. Skipped entirely when the visitor prefers reduced
   motion (the text just shows as-is). */
(function () {
  "use strict";

  var CHAR_DELAY_MS = 32;   // base delay between characters
  var CHAR_JITTER_MS = 34;  // random extra delay, for an irregular human cadence
  var START_DELAY_MS = 300; // pause before typing so the prompt registers first

  var el = document.querySelector(".hero__roles[data-typewriter]");
  if (!el) return;

  var reduce = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;

  var full = el.textContent;

  // Reserve the rendered height before clearing so the block doesn't collapse
  // vertically as it types (avoids layout shift / a jumping headline). Height,
  // not width — reserving width overflows the column on narrow screens where
  // the role line wraps.
  el.style.display = "inline-block";
  el.style.minHeight = el.getBoundingClientRect().height + "px";

  el.textContent = "";

  var i = 0;
  function tick() {
    el.textContent = full.slice(0, i);
    if (i < full.length) {
      i += 1;
      // Slightly irregular cadence reads more like real typing.
      setTimeout(tick, CHAR_DELAY_MS + Math.random() * CHAR_JITTER_MS);
    }
  }

  setTimeout(tick, START_DELAY_MS);
})();
