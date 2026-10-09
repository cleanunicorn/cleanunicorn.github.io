"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { createServer } = require("node:http");
const { readdir, readFile, stat } = require("node:fs/promises");
const path = require("node:path");
const { test } = require("node:test");
const { chromium } = require("playwright-core");

const publicDir = path.resolve(__dirname, "..", "public");
const tweets = [
  {
    path: "posts/the-right-way-to-use-transient-storage-eip-1153/",
    text: "Be EXTREMELY careful with EIP1153 Transient Storage\n\nHere is why \u{1F447}\u{1F447}\u{1F447} https://t.co/eFPPyy6AIQ",
    author: "BountyHunt3r (@Bount3yHunt3r)",
    link: "January 27, 2024 · View on X",
    href: "https://twitter.com/Bount3yHunt3r/status/1751059387555135777",
  },
  {
    path: "posts/the-inception-of-doppelganger-networks/",
    text: "1/ We\u2019re thrilled to announce our $9M seed round led by @Paradigm pic.twitter.com/LPnJBXC564",
    author: "Shadow (@shadowxyz)",
    link: "December 5, 2023 · View on X",
    href: "https://twitter.com/shadowxyz/status/1732049145140015142",
  },
];
const expected = ["About", "Projects", "Work", "Posts", "Contact"];
const mime = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2" };

function browserPath() {
  if (process.env.CHROME) return process.env.CHROME;
  for (const name of ["chromium", "chromium-browser", "google-chrome"]) {
    try {
      return execFileSync("which", [name], { encoding: "utf8" }).trim();
    } catch {
      // Try the next installed browser.
    }
  }
  throw new Error("Install Chromium or set CHROME to its executable path");
}

function siteServer() {
  return createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
      let file = path.resolve(publicDir, `.${pathname}`);
      if (file !== publicDir && !file.startsWith(`${publicDir}${path.sep}`)) throw new Error("outside public");
      if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
      response.setHeader("Content-Type", mime[path.extname(file)] || "application/octet-stream");
      response.end(await readFile(file));
    } catch {
      response.writeHead(404).end("Not found");
    }
  });
}

test("mobile disclosure and desktop navigation work in Chromium", { timeout: 30000 }, async () => {
  const server = siteServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: browserPath(), headless: true, args: ["--no-sandbox"] });
    const url = `http://127.0.0.1:${server.address().port}/`;
    const mobile = await browser.newPage({ viewport: { width: 375, height: 812 } });
    await mobile.goto(url);
    const button = mobile.locator(".mobile-nav__toggle");
    const list = mobile.locator("#mobile-nav-links");
    assert.equal(await button.isVisible(), true);
    assert.ok((await button.boundingBox()).height >= 44, "mobile Menu target must be at least 44px high");
    assert.equal(await button.getAttribute("aria-expanded"), "false");
    assert.equal(await list.isVisible(), false);
    assert.equal(await mobile.locator(".navigation-menu:not(.navigation-menu--mobile)").isVisible(), false);

    await button.focus();
    await mobile.keyboard.press("Enter");
    assert.equal(await button.getAttribute("aria-expanded"), "true");
    assert.equal(await list.isVisible(), true);
    const focused = [];
    for (const _ of expected) {
      await mobile.keyboard.press("Tab");
      focused.push(await mobile.evaluate(() => document.activeElement.textContent.trim()));
    }
    assert.deepEqual(focused, expected);
    await mobile.keyboard.press("Escape");
    assert.equal(await button.getAttribute("aria-expanded"), "false");
    assert.equal(await list.isVisible(), false);
    assert.equal(await button.evaluate(element => element === document.activeElement), true);
    await mobile.keyboard.press("Space");
    assert.equal(await button.getAttribute("aria-expanded"), "true");
    await mobile.keyboard.press("Space");
    assert.equal(await button.getAttribute("aria-expanded"), "false");

    await mobile.keyboard.press("Enter");
    assert.equal(await button.getAttribute("aria-expanded"), "true");
    await mobile.setViewportSize({ width: 1024, height: 768 });
    await mobile.waitForFunction(() => {
      const toggle = document.querySelector(".mobile-nav__toggle");
      const links = document.querySelector("#mobile-nav-links");
      return toggle?.getAttribute("aria-expanded") === "false" && links?.hidden;
    });
    assert.equal(await button.getAttribute("aria-expanded"), "false");
    assert.equal(await list.evaluate(element => element.hidden), true);

    const desktop = await browser.newPage({ viewport: { width: 1024, height: 768 } });
    await desktop.goto(url);
    assert.equal(await desktop.locator(".navigation-menu--mobile").isVisible(), false);
    const desktopLinks = desktop.locator(".navigation-menu:not(.navigation-menu--mobile) a");
    assert.deepEqual(await desktopLinks.allTextContents(), expected);
    await desktopLinks.first().focus();
    const desktopFocused = [await desktop.evaluate(() => document.activeElement.textContent.trim())];
    for (let i = 1; i < expected.length; i++) {
      await desktop.keyboard.press("Tab");
      desktopFocused.push(await desktop.evaluate(() => document.activeElement.textContent.trim()));
    }
    assert.deepEqual(desktopFocused, expected);

    const about = await browser.newPage({ viewport: { width: 375, height: 812 } });
    await about.goto(`${url}about/`);
    for (const nav of [".navigation-menu--mobile", ".navigation-menu:not(.navigation-menu--mobile)"]) {
      assert.equal(await about.locator(`${nav} a[href="/about/"]`).getAttribute("aria-current"), "page");
    }

    const noJs = await browser.newPage({ viewport: { width: 375, height: 812 }, javaScriptEnabled: false });
    await noJs.goto(url);
    assert.equal(await noJs.locator(".mobile-nav__toggle").isVisible(), false);
    assert.deepEqual(await noJs.locator(".mobile-nav__links a:visible").allTextContents(), expected);
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});

// Text, author and date are X's oEmbed responses for these tweets (#52).
test("X embeds read without widgets.js and fit narrow screens", { timeout: 60000 }, async () => {
  const server = siteServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: browserPath(), headless: true, args: ["--no-sandbox"] });
    const url = `http://127.0.0.1:${server.address().port}/`;
    for (const javaScriptEnabled of [false, true]) {
      for (const width of [390, 1024]) {
        const context = await browser.newContext({ viewport: { width, height: 844 }, javaScriptEnabled });
        // Stay offline: abort everything that is not the local site, widgets.js included.
        const blocked = [];
        await context.route("**/*", route => {
          if (new URL(route.request().url()).hostname === "127.0.0.1") return route.continue();
          blocked.push(route.request().url());
          return route.abort();
        });
        for (const tweet of tweets) {
          const label = `${tweet.path} js=${javaScriptEnabled} width=${width}`;
          const page = await context.newPage();
          await page.goto(url + tweet.path, { waitUntil: "load" });
          const card = page.locator("blockquote.twitter-tweet");
          assert.equal(await card.count(), 1, label);
          assert.ok(await card.isVisible(), label);
          assert.equal(await card.locator("p").innerText(), tweet.text, label);
          assert.match(await card.innerText(), new RegExp(`— ${tweet.author.replace(/[()]/g, "\\$&")}`), label);
          const link = card.getByRole("link", { name: tweet.link, exact: true });
          assert.ok(await link.isVisible(), label);
          assert.equal(await link.getAttribute("href"), tweet.href, label);
          const fit = await card.evaluate(element => {
            const box = element.getBoundingClientRect();
            return {
              documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              cardOverflow: element.scrollWidth - element.clientWidth,
              right: box.right,
              viewport: window.innerWidth,
            };
          });
          assert.ok(fit.documentOverflow <= 0, `${label}: page scrolls sideways ${JSON.stringify(fit)}`);
          assert.ok(fit.cardOverflow <= 0, `${label}: card overflows ${JSON.stringify(fit)}`);
          assert.ok(fit.right <= fit.viewport, `${label}: card past viewport ${JSON.stringify(fit)}`);
          await page.close();
        }
        if (javaScriptEnabled) {
          assert.ok(blocked.some(request => request.startsWith("https://platform.twitter.com/widgets.js")),
            "widgets.js should be requested (and blocked) on embed pages");
        }
        await context.close();
      }
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});

test("post end blocks fit at 390px and 1300px on every post", { timeout: 60000 }, async () => {
  const entries = await readdir(path.join(publicDir, "posts"), { withFileTypes: true });
  const posts = entries.filter(entry => entry.isDirectory() && entry.name !== "page").map(entry => entry.name);
  assert.ok(posts.length >= 2, "expected built posts under public/posts/");
  const server = siteServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: browserPath(), headless: true, args: ["--no-sandbox"] });
    const url = `http://127.0.0.1:${server.address().port}/`;
    for (const width of [390, 1300]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      for (const slug of posts) {
        await page.goto(`${url}posts/${slug}/`);
        await page.evaluate(() => document.fonts.ready);
        const where = `${slug} at ${width}px`;
        assert.equal(await page.locator(".post-cta").isVisible(), true, `${where}: CTA visible`);
        // body has overflow-x: clip (z-base.css), so scrollWidth alone cannot
        // see overflow: check every box in the new blocks against the viewport.
        const outside = await page.evaluate(() => {
          const width = document.documentElement.clientWidth;
          return [...document.querySelectorAll(".post-nav, .post-nav *, .post-cta, .post-cta *")]
            .map(element => ({ element, box: element.getBoundingClientRect() }))
            .filter(({ box }) => box.width && (box.left < 0 || box.right > width + 0.5))
            .map(({ element, box }) => `${element.tagName}.${element.className} ${box.left}-${box.right}`);
        });
        assert.deepEqual(outside, [], `${where}: boxes outside the viewport`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), `${where}: page scrolls sideways`);
        for (const link of await page.locator(".post-nav a, .post-cta a").all()) {
          await link.focus();
          assert.equal(await link.evaluate(element => element === document.activeElement), true, `${where}: link focusable`);
          const box = await link.boundingBox();
          assert.ok(box && box.width > 0 && box.height > 0, `${where}: link has a box`);
        }
      }
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});

test("About prose fills the content column and no page scrolls sideways", { timeout: 60000 }, async () => {
  const server = siteServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: browserPath(), headless: true, args: ["--no-sandbox"] });
    const base = `http://127.0.0.1:${server.address().port}`;
    for (const width of [1300, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      for (const route of ["/", "/about/", "/work/", "/contact/", "/posts/", "/404.html"]) {
        await page.goto(`${base}${route}`);
        await page.evaluate(() => document.fonts.ready);
        const { scroll, client } = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          client: document.documentElement.clientWidth,
        }));
        assert.ok(scroll <= client, `${route} at ${width}px scrolls sideways: ${scroll} > ${client}`);
      }

      await page.goto(`${base}/about/`);
      await page.evaluate(() => document.fonts.ready);
      const { column, blocks } = await page.evaluate(() => {
        const content = document.querySelector(".index-content--about");
        return {
          column: content.getBoundingClientRect().width,
          blocks: [...content.querySelectorAll(":scope > p, :scope > ul, :scope > ol")].map(element => {
            const style = getComputedStyle(element);
            return {
              tag: element.tagName,
              text: element.textContent.trim().slice(0, 40),
              outer: element.getBoundingClientRect().width + parseFloat(style.marginLeft) + parseFloat(style.marginRight),
            };
          }),
        };
      });
      assert.ok(blocks.some(block => block.tag === "P"), "About must have direct paragraphs to measure");
      for (const block of blocks) {
        assert.ok(Math.abs(block.outer - column) <= 1,
          `About ${block.tag} "${block.text}" at ${width}px is ${block.outer}px, column is ${column}px`);
      }
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});

// Analytics consent (#44): denied by default, explicit choice, reopenable.
test("analytics consent banner defaults to denied and remembers a choice", { timeout: 60000 }, async () => {
  const server = siteServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let browser;
  const signals = ["analytics_storage", "ad_storage", "ad_user_data", "ad_personalization"];
  // Reads dataLayer entries as [command, action, params] for consent calls.
  const consentCalls = page => page.evaluate(() =>
    window.dataLayer.map(entry => Array.from(entry)).filter(entry => entry[0] === "consent"));
  try {
    browser = await chromium.launch({ executablePath: browserPath(), headless: true, args: ["--no-sandbox"] });
    const base = `http://127.0.0.1:${server.address().port}`;
    const open = async (context, url) => {
      const page = await context.newPage();
      // Keep the test offline: gtag.js never loads, so only the queue is observable.
      await page.route("https://www.googletagmanager.com/**", route =>
        route.fulfill({ status: 200, contentType: "text/javascript", body: "" }));
      await page.goto(url);
      return page;
    };

    for (const width of [390, 1300]) {
      const context = await browser.newContext({ viewport: { width, height: 800 } });
      const page = await open(context, `${base}/`);
      const banner = page.locator("#consent-banner");
      const accept = banner.getByRole("button", { name: "Accept analytics" });
      const reject = banner.getByRole("button", { name: "Reject" });

      // First visit: banner shown, default denied before anything else, no _ga cookie.
      assert.equal(await banner.isVisible(), true);
      const first = await consentCalls(page);
      assert.equal(first[0][1], "default");
      for (const signal of signals) assert.equal(first[0][2][signal], "denied");
      assert.equal(await page.evaluate(() => document.cookie.includes("_ga")), false);

      // Fit and equal prominence.
      const [a, r, box] = await Promise.all([accept.boundingBox(), reject.boundingBox(), banner.boundingBox()]);
      assert.ok(a.height >= 44 && r.height >= 44, "buttons must be at least 44px high");
      assert.ok(Math.abs(a.width - r.width) <= 2 && Math.abs(a.height - r.height) <= 2, "Accept and Reject must be the same size");
      assert.ok(box.height <= 800 / 2, `banner covers ${box.height}px of 800 at ${width}px`);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      assert.equal(await banner.getAttribute("aria-labelledby"), "consent-title");

      // The fixed banner must not hide the footer: scroll to the bottom and
      // check Cookie settings sits entirely above the banner.
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      const [openerBox, bannerBox] = await Promise.all([page.locator("#consent-open").boundingBox(), banner.boundingBox()]);
      assert.ok(openerBox.y + openerBox.height <= bannerBox.y,
        `Cookie settings (bottom ${openerBox.y + openerBox.height}) is covered by the banner (top ${bannerBox.y}) at ${width}px`);
      // The last text on the page (the Connect block after the footer) must clear it too.
      const lastBottom = await page.evaluate(() => Math.max(...[...document.querySelectorAll("body *")]
        .filter(el => !el.closest("#consent-banner, script") && !el.children.length && el.textContent.trim())
        .map(el => el.getBoundingClientRect())
        .filter(box => box.height > 0)
        .map(box => box.bottom)));
      assert.ok(lastBottom <= bannerBox.y, `last page content (bottom ${lastBottom}) is covered by the banner (top ${bannerBox.y}) at ${width}px`);
      await page.evaluate(() => window.scrollTo(0, 0));

      // Keyboard: Tab reaches Accept then Reject, Enter chooses.
      await page.locator("#consent-title").focus();
      await page.keyboard.press("Tab");
      assert.equal(await accept.evaluate(el => el === document.activeElement), true);
      await page.keyboard.press("Tab");
      assert.equal(await reject.evaluate(el => el === document.activeElement), true);
      await accept.focus();
      await page.keyboard.press("Enter");
      assert.equal(await banner.isVisible(), false);
      assert.equal(await page.evaluate(() => localStorage.getItem("consent.v1")), "granted");
      const accepted = await consentCalls(page);
      assert.deepEqual(accepted.at(-1).slice(1), ["update", { analytics_storage: "granted" }]);

      // The choice survives navigation: no banner, granted restored before config.
      const next = await open(context, `${base}/about/`);
      assert.equal(await next.locator("#consent-banner").isVisible(), false);
      const restored = await next.evaluate(() => window.dataLayer.map(entry => Array.from(entry)[0] + ":" + Array.from(entry)[1]));
      assert.deepEqual(restored.slice(0, 2), ["consent:default", "consent:update"]);
      assert.ok(restored[2].startsWith("js:"), `third dataLayer entry is ${restored[2]}`);
      assert.ok(restored.indexOf("consent:update") < restored.findIndex(entry => entry.startsWith("config")));

      // Cookie settings reopens the banner, and the choice flips.
      const opener = next.locator("#consent-open");
      assert.equal(await opener.isVisible(), true);
      await opener.click();
      assert.equal(await next.locator("#consent-banner").isVisible(), true);
      await next.locator("#consent-banner").getByRole("button", { name: "Reject" }).click();
      assert.equal(await next.locator("#consent-banner").isVisible(), false);
      assert.equal(await next.evaluate(() => localStorage.getItem("consent.v1")), "denied");
      assert.deepEqual((await consentCalls(next)).at(-1).slice(1), ["update", { analytics_storage: "denied" }]);
      assert.equal(await opener.evaluate(el => el === document.activeElement), true);
      await context.close();
    }

    // Storage that throws must not break the page or the banner.
    const broken = await browser.newContext({ viewport: { width: 390, height: 800 } });
    await broken.addInitScript(() => {
      Object.defineProperty(window, "localStorage", { get() { throw new Error("blocked"); } });
    });
    const blocked = await open(broken, `${base}/`);
    assert.equal(await blocked.locator("#consent-banner").isVisible(), true);
    await blocked.getByRole("button", { name: "Accept analytics" }).click();
    assert.equal(await blocked.locator("#consent-banner").isVisible(), false);
    await broken.close();

    // Without JS nothing is shown and nothing can be granted.
    const noJs = await browser.newContext({ viewport: { width: 390, height: 800 }, javaScriptEnabled: false });
    const plain = await noJs.newPage();
    await plain.goto(`${base}/`);
    assert.equal(await plain.locator("#consent-banner").isVisible(), false);
    assert.equal(await plain.locator("#consent-open").isVisible(), false);
    await noJs.close();
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
});
