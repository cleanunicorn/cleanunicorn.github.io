/* Hero terminal — turns the `~$ whoami` eyebrow into a small, real terminal.
   Progressive enhancement: without JS the eyebrow stays a static prompt line.
   The prompt input appears once the whoami typewriter finishes (hero-type.js
   dispatches "hero-typed"), or after a fallback timeout.

   Everything is deliberately dependency-free and screen-reader friendly:
   output is a role="log" live region, the input is a real <input> (mobile
   keyboards work), and Escape blurs out of the terminal. */
(function () {
  "use strict";

  var eyebrow = document.querySelector(".poster__eyebrow");
  if (!eyebrow) return;

  /* ---- A greeting for the view-source crowd -------------------------------- */
  try {
    console.log(
      "%c~$ whoami%c\ncleanunicorn — builder, hacker, extropian." +
        "\n\nThe prompt on the homepage accepts input. `help` is a good start;" +
        "\n`ls -a` rewards the curious.\n",
      "color:#3fd68a;font-weight:bold", ""
    );
  } catch (e) { /* consoles are optional */ }

  /* ---- Virtual filesystem --------------------------------------------------- */
  var FILES = {
    "about.md": [
      "# Daniel Luca (CleanUnicorn)",
      "Builder, hacker, extropian — Bucharest, Romania.",
      "Shipping software since 2008, on Ethereum since 2017.",
      "What I do: `cat work.md`.",
      "Full story: /about/  (or just type: about)",
    ],
    "work.md": [
      "CTO @ Stealth Startup — since August 2026.",
      "Technical Partner @ Eden Block — research-driven diligence.",
      "Open-source projects: /about/#projects",
      "Prev: ConsenSys Diligence, Akira Tech, FiatDAO.",
      "Details: /work/  (or just type: work)",
    ],
    "contact.md": [
      "Fastest: DM @cleanunicorn on X, or book 30 min (type: book).",
      "Everything else: /contact/",
    ],
    "cv.pdf": null, // binary — handled specially by `cat`
    ".plan": [
      "secure the protocols.",
      "back the builders.",
      "ship the tools.",
    ],
    // base64 (ASCII payload — atob is Latin-1 only) so the flag doesn't show
    // up in a casual Ctrl+F of the source
    ".flag": ["ZmxhZ3t5MHVfcjM0ZF90aDNfczB1cmMzfSAtLSBETSBtZSB0aGlzIG9uIFg6IEBjbGVhbnVuaWNvcm4="],
  };
  var DIRS = ["posts"];

  /* ---- Command implementations ---------------------------------------------
     Each returns an array of output lines; navigation happens via `go`.
     A line can be a string or {text, cls} for styled output. */
  function go(url, external) {
    if (external) window.open(url, "_blank", "noopener");
    else window.location.href = url;
  }

  var COMMANDS = {
    help: function () {
      // Keep every line ≤ ~34ch so nothing wraps inside the chip on phones.
      return [
        "available commands:",
        "  about      who I am",
        "  work       what I've done",
        "  posts      what I write",
        "  contact    how to reach me",
        "  book       grab 30 min on cal.com",
        "  cv         open the CV (pdf)",
        "  ls · cat · pwd · clear · exit",
        "this is a security researcher's",
        "site — assume hidden surface.",
      ];
    },
    whoami: function () {
      return ["daniel — cleanunicorn. you, I don't know yet: type `contact`."];
    },
    pwd: function () {
      return ["/home/daniel"];
    },
    ls: function (args) {
      var all = args.indexOf("-a") !== -1 || args.indexOf("-la") !== -1 || args.indexOf("-al") !== -1;
      var names = DIRS.map(function (d) { return d + "/"; });
      for (var f in FILES) {
        if (f.charAt(0) === "." && !all) continue;
        names.push(f);
      }
      if (all) names = [".", ".."].concat(names);
      return [names.join("  ")];
    },
    cat: function (args) {
      var name = args[0];
      if (!name) return ["usage: cat <file> — try `ls`"];
      if (name === "cv.pdf") {
        go("/cv.pdf", true);
        return ["cv.pdf: binary file — opening the rendered copy…"];
      }
      if (name.replace(/\/$/, "") === "posts") return ["cat: posts/: Is a directory — type `posts`"];
      if (name === ".flag") {
        try { return [window.atob(FILES[".flag"][0])]; }
        catch (e) { return [FILES[".flag"][0]]; }
      }
      if (FILES[name]) return FILES[name];
      return ["cat: " + name + ": No such file or directory"];
    },
    cd: function (args) {
      var dir = (args[0] || "").replace(/\/$/, "");
      if (dir === "posts") { go("/posts/"); return ["→ /posts/"]; }
      if (!dir || dir === "~") return [];
      return ["cd: no such directory: " + dir];
    },
    about: function () { go("/about/"); return ["→ /about/"]; },
    work: function () { go("/work/"); return ["→ /work/"]; },
    posts: function () { go("/posts/"); return ["→ /posts/"]; },
    blog: function () { go("/posts/"); return ["→ /posts/"]; },
    contact: function () { go("/contact/"); return ["→ /contact/"]; },
    cv: function () { go("/cv.pdf", true); return ["opening cv.pdf…"]; },
    book: function () {
      go("https://cal.com/daniel-luca-cleanunicorn/30min", true);
      return ["opening the calendar — see you soon."];
    },
    sudo: function () {
      return [
        "daniel is not in the sudoers file.",
        "This incident will be reported (to @cleanunicorn, who will be delighted).",
      ];
    },
    rm: function (args) {
      if (args.join(" ").indexOf("-rf") !== -1) {
        return ["rm: permission denied — this system has been audited."];
      }
      return ["rm: read-only filesystem"];
    },
    hack: function () {
      return [
        "scanning target… 1 contract found.",
        "0 critical · 0 high · 1 informational:",
        "  [INFO] owner is friendly. severity: none. remediation: say hi.",
      ];
    },
    unicorn: function () {
      return [
        " _________________________",
        "< you found the unicorn 🦄 >",
        " -------------------------",
        "        \\   ^__^",
        "         \\  (oo)\\_______",
        "            (__)\\       )\\/\\",
        "                ||----w |",
        "                ||     ||",
        "   (yes, that's a cow. budget cuts.)",
      ];
    },
    echo: function (args) { return [args.join(" ")]; },
    date: function () { return [new Date().toString()]; },
    clear: null, // handled by the runner (needs access to the output node)
    exit: null,  // handled by the runner
  };
  COMMANDS.man = COMMANDS.help;
  COMMANDS["?"] = COMMANDS.help;

  /* ---- Terminal UI ----------------------------------------------------------- */
  var term = document.createElement("div");
  term.className = "term";
  term.innerHTML =
    '<div class="term__out" role="log" aria-live="polite"></div>' +
    '<form class="term__form">' +
    '<label class="sr-only" for="term-in">Terminal — type help and press enter</label>' +
    '<span class="term__ps1" aria-hidden="true">~$</span>' +
    '<input id="term-in" class="term__in" autocomplete="off" autocapitalize="none" ' +
    'autocorrect="off" spellcheck="false" enterkeyhint="send" placeholder=\'try "help"\'>' +
    "</form>";

  var out = term.querySelector(".term__out");
  var form = term.querySelector(".term__form");
  var input = term.querySelector(".term__in");

  function print(line, cls) {
    var el = document.createElement("div");
    el.className = "term__line" + (cls ? " " + cls : "");
    el.textContent = line;
    out.appendChild(el);
  }

  function run(raw) {
    var line = raw.trim();
    eyebrow.classList.add("poster__eyebrow--open");
    print("~$ " + line, "term__line--cmd");
    if (line) {
      var parts = line.split(/\s+/);
      var name = parts[0].toLowerCase();
      var args = parts.slice(1);
      if (name === "clear") {
        out.textContent = "";
      } else if (name === "exit" || name === "logout") {
        print("logout");
        input.blur();
        setTimeout(function () {
          out.textContent = "";
          eyebrow.classList.remove("poster__eyebrow--active", "poster__eyebrow--open");
        }, 600);
      } else if (COMMANDS[name]) {
        COMMANDS[name](args).forEach(function (l) { print(l); });
      } else {
        print("zsh: command not found: " + name + " — try `help`", "term__line--err");
      }
    }
    // Trim scrollback and keep the latest output in view.
    while (out.children.length > 300) out.removeChild(out.firstChild);
    out.scrollTop = out.scrollHeight;
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    run(input.value);
    input.value = "";
  });
  input.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") input.blur();
  });
  input.addEventListener("focus", function () {
    eyebrow.classList.add("poster__eyebrow--active");
  });
  input.addEventListener("blur", function () {
    eyebrow.classList.remove("poster__eyebrow--active");
  });
  // Clicking anywhere on the chip drops you into the prompt.
  eyebrow.addEventListener("click", function (ev) {
    if (ev.target.closest("a")) return; // keep the whoami link clickable
    input.focus({ preventScroll: true });
  });

  /* ---- Reveal: after the whoami line finishes typing ------------------------- */
  var revealed = false;
  function reveal() {
    if (revealed) return;
    revealed = true;
    eyebrow.appendChild(term);
    // Hide the decorative block cursor — the input carries the caret now.
    var cursor = eyebrow.querySelector(".poster__cursor");
    if (cursor) cursor.remove();
    eyebrow.classList.add("poster__eyebrow--term");
  }
  document.addEventListener("hero-typed", reveal);
  setTimeout(reveal, 4500); // fallback if the typewriter never signals
})();
