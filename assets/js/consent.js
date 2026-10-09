// Consent banner for Google Analytics (Consent Mode v2). The default-denied
// state is set in layouts/partials/analytics.html; this only records a choice.
// Without JS the banner stays hidden and analytics stays denied.
(() => {
  const KEY = "consent.v1";
  const banner = document.getElementById("consent-banner");
  if (!banner) return;

  const opener = document.getElementById("consent-open");
  const title = document.getElementById("consent-title");
  let fromOpener = false;

  const read = () => {
    try { return localStorage.getItem(KEY); } catch { return null; }
  };
  const write = value => {
    try { localStorage.setItem(KEY, value); } catch { /* choice lasts for this page only */ }
  };
  const clearAnalyticsCookies = () => {
    const hosts = [location.hostname, "." + location.hostname, "." + location.hostname.split(".").slice(-2).join(".")];
    document.cookie.split(";").map(c => c.split("=")[0].trim()).filter(name => /^_ga(_|$)/.test(name)).forEach(name => {
      hosts.forEach(domain => { document.cookie = `${name}=; Max-Age=0; path=/; domain=${domain}`; });
      document.cookie = `${name}=; Max-Age=0; path=/`;
    });
  };

  const choose = granted => {
    write(granted ? "granted" : "denied");
    if (typeof gtag === "function") gtag("consent", "update", { analytics_storage: granted ? "granted" : "denied" });
    if (!granted) clearAnalyticsCookies();
    banner.hidden = true;
    if (fromOpener && opener) opener.focus();
    fromOpener = false;
  };

  banner.querySelector("[data-consent=accept]").addEventListener("click", () => choose(true));
  banner.querySelector("[data-consent=reject]").addEventListener("click", () => choose(false));

  if (opener) {
    opener.hidden = false;
    opener.addEventListener("click", () => {
      fromOpener = true;
      banner.hidden = false;
      if (title) title.focus();
    });
  }

  if (read() === null) banner.hidden = false;
})();
