"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { createServer } = require("node:http");
const { readFile, stat } = require("node:fs/promises");
const path = require("node:path");
const { test } = require("node:test");
const { chromium } = require("playwright-core");

const publicDir = path.resolve(__dirname, "..", "public");
const expected = ["About", "Work", "Posts", "Contact"];
const mime = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript" };

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
