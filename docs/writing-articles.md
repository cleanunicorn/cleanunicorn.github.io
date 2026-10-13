# Writing articles

What worked for [My Agents Prompt Each Other More Than I Prompt Them](../content/posts/one-prompt-a-whole-team/index.md),
written down so the next article starts from it. Use it as the brief when drafting with an agent.

## The structure

Every article follows the same arc: **say what you will show, show it, then recap what you showed.**
Inside that arc, these sections, in this order:

| # | Section | Job | In the herdr article |
|---|---------|-----|----------------------|
| 1 | **Proof** | Open with numbers from real usage, so the reader knows this is not theory. | "Three weeks in numbers": prompts I wrote against prompts my agents wrote |
| 2 | **Results** | Show the outcome working, before explaining anything. Demos first. | "Watch this first": two recordings and a diagram, then "What that adds up to" |
| 3 | **Contradiction** | State the common belief, then contradict it: not A, not B, actually C. This is the reason to keep reading. | "It is not the model" (not the model, not the prompt, the structure) |
| 4 | **What I did** | The path, as good / better / best. Each step names what it fixed and what it still got wrong. | "Good, better, best" |
| 5 | **Re-hook** | Real, everyday use after the showpiece. Smaller and more frequent than the demo. | "What I actually do all day": real prompts from history |
| 6 | **Get started** | Step by step, copiable commands, links. Gets the reader started, not all the way there. Ends with the order to learn things in. | "Get started in ten minutes" and "Where to go from there" |
| 7 | **It will not work unless** | The non-negotiables. Each one is a mistake I made once. | "It will not work unless" |
| 8 | **Recap** | Close by repeating what the article explained, then tie back to the opening. One call to action. | "The short version" |
| 9 | **P.S.** *(optional)* | A teaser for a related topic. Short: two or three sentences and an image, never a section. | Earheart |

Write the opening last-but-one and the recap last: the opening promises, the recap proves the promise was kept.

## Principles

### Show, don't claim

- **Lead with evidence from my own history.** Count it (Claude Code and Codex histories, git, logs). A table of four numbers beats a paragraph of adjectives.
- **Round honestly.** If a number comes from a classifier or a heuristic, say "about" and keep the exact figures and the method in the draft notes.
- **Record it.** A terminal workflow gets an asciinema recording (`{{< asciinema src="x.cast" >}}`). Set `start` and `poster` so the player opens on the interesting frame, not a blank prompt.
- **Use a diagram instead of a third demo** when the point is how parts relate, not what it looks like. Mermaid sequence diagrams work well for "who talks to whom and who trusts whom".
- **Quote real prompts and real output**, verbatim, not cleaned-up examples. Typos in quoted prompts can stay.

### Explain what the reader just watched

- Right after each demo, say in one paragraph what happened.
- **Explain every project-specific thing on screen** (custom Make targets, private tooling). The reader does not know `make branch-test` is mine, not a feature of the tool.
- **Name the likely misunderstanding and kill it.** "There is no `docker exec` anywhere in that recording." If a reader could wrongly guess how it works, say how it does not work.
- Show the exact commands the agent ran, in a code block, after the recording.

### Make it easy to follow

- **Bold the one sentence per section that carries the point.** A skimmer reading only the bold should get the argument.
- Short paragraphs. Plain words. One idea per paragraph.
- Use a table when comparing options, roles or keys; use a list for rules.
- **Break up long sections visually.** Good/better/best got one meme per step, each captioned to the exact point of that step (the Obama self-medal for "an agent reviewing its own code"). Memes go at the top of their sub-section.
- Merge sections that say the same thing. Two lists of advice in different places become one.
- Cut anything that does not serve the arc, however much I like it. The P.S. started as a section and became three sentences.

### Get-started sections

- Numbered steps, each with a heading, one command block, and a link to the official docs.
- Give the convenient install and the auditable one (the `curl | sh` line, and where to read the script first).
- Include a **check step** ("it should print `1`; if it prints nothing, you started it outside Herdr").
- End with first prompts to try, in order of how much they do, and the learning order after that.
- Promise only what the steps deliver: "This will not get you to the full setup. It gets you to …"

### Honesty

- Do not overstate. "I don't type any of my prompts" became "I don't type most of them".
- Say where it breaks. The "it will not work unless" list comes from real failures, told as such ("I skipped every item below once").
- Mark limits on the claim: "Unattended has an asterisk, and it should."

## Titles

- **Pick the title after the article is finished**, from its strongest claim. The working title ("One prompt, a whole team") became the description and the closing line.
- A good title is a surprising, checkable statement backed by the article's numbers: "My Agents Prompt Each Other More Than I Prompt Them".
- Ask for several options and pick one; do not let the first draft's title stick by default.
- Rename the folder slug to match only before publishing; after that, the URL is fixed.

## Images and media

- Save images in the page bundle next to `index.md`, never hotlinked (memes from imgflip are downloaded).
- Every image needs real alt text describing what it shows and what the caption says (`make check-alt-text` fails on placeholders).
- A screenshot of a tool makes a mention of it worth reading (the Earheart overlay).
- Recordings: scan `.cast` files before committing for keys, tokens, connection strings, emails, IPs, customer names and private repo details. Note what remains visible in the draft notes.

## Workflow

1. Agent drafts the whole article against the structure above, with placeholders for recordings.
2. Record demos; agent writes the explanation around each one.
3. **Check the draft against the structure** explicitly, section by section, and fix gaps.
4. Look at it rendered on the dev server (`make dev`), at desktop and phone width: text width, title width, heading styles, spacing around links. Fix CSS site-wide, not per post, and open an issue for other pages that may share the problem.
5. Tightening pass: shorter, merged, bolded, easier to follow.
6. Pick the title.
7. Pre-publish checklist (below), then PR.
8. Social posts and analytics (below).

Keep a `<!-- DRAFT NOTES -->` comment at the top while drafting: recording status, structure, the source and method of every number, and open questions.

## Pre-publish checklist

- [ ] Every section of the structure is present and in order; the ending recaps the middle.
- [ ] Every number is traceable to its source in the draft notes, and rounded honestly.
- [ ] Private projects named only with consent; recordings and screenshots scanned.
- [ ] **Delete the DRAFT NOTES comment.** Hugo drops it from the page, but the repo is public, so it is readable in the source.
- [ ] `description` is 160 characters or fewer (`make check-positioning`).
- [ ] All images have alt text (`make check-alt-text`).
- [ ] `draft = false`, `make test` and `make build` pass.
- [ ] Rendered page checked at desktop and phone width; images and recordings load.

