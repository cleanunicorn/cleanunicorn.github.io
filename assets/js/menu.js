/* Mobile disclosure only. The HTML leaves links visible when JS is unavailable. */
(() => {
  const nav = document.querySelector(".navigation-menu--mobile");
  if (!nav) return;

  const button = nav.querySelector(".mobile-nav__toggle");
  const links = document.getElementById(button.getAttribute("aria-controls"));
  if (!links) return;

  const setExpanded = expanded => {
    links.hidden = !expanded;
    button.setAttribute("aria-expanded", String(expanded));
  };

  setExpanded(false);
  button.hidden = false;
  button.addEventListener("click", () => setExpanded(button.getAttribute("aria-expanded") !== "true"));
  nav.addEventListener("keydown", event => {
    if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
      setExpanded(false);
      button.focus();
    }
  });
  // Match the theme's menu.css breakpoint and assets/css/z-layout.css.
  window.matchMedia("(max-width: 684px)").addEventListener("change", () => setExpanded(false));
})();
