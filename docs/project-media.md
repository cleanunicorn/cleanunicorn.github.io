# Project media

Featured project images live in `static/images/projects/`; the Power Mode
recording lives in `static/videos/`. Both the homepage and Projects page read
their paths, descriptions and dimensions from `data/projects.toml`.

- Earheart: existing overlay screenshot, retained.
- drove: `assets/cli-status.svg` from the drove repository, a Rich terminal export.
- Agents Library: `docs/assets/manager-workflow.png` from the repository. This is
  a workflow diagram, identified as such in its caption and alt text.
- dispatch: `docs/images/slack-permission.svg` from the repository, a sanitized
  illustration of its Slack permission flow.
- Quill: final frame (43) of `static/demo.gif` from the Quill repository.
- Chief of Staff: live BB pipeline and workflow-editor screenshots captured
  on 2026-11-08. No task or configuration changes were made for these captures.
- Power Mode: `docs/media/power-mode-demo.mp4` and its poster, copied from commit
  `81cac1e19cfeefbdefe92c90ce5973d0f70b509c` of `cleanunicorn/bb-plugin-power-mode`.
  The existing recording is 83.97 seconds, H.264, 1280×800, with no audio.
  Its upstream `docs/demo-video.md` describes the recording and reproduction.

The video is served locally with native controls, inline playback, no autoplay
and `preload="none"`. It includes a poster, a scene summary, and a direct video
link. Screenshots load lazily and declare their dimensions to reserve space.
