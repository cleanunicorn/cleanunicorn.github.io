/* Article narration player. Without JS the native <audio controls> stays visible. */
(() => {
  const SPEEDS = [1, 1.25, 1.5, 1.75, 2, 0.75];

  const format = seconds => {
    if (!Number.isFinite(seconds)) return "--:--";
    const s = Math.floor(seconds);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const pad = n => String(n).padStart(2, "0");
    return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
  };

  document.querySelectorAll(".article-audio").forEach(root => {
    const audio = root.querySelector("audio");
    const player = root.querySelector(".article-audio__player");
    if (!audio || !player) return;

    const play = player.querySelector(".article-audio__play");
    const icon = player.querySelector(".article-audio__icon");
    const seek = player.querySelector(".article-audio__seek");
    const current = player.querySelector(".article-audio__current");
    const duration = player.querySelector(".article-audio__duration");
    const speed = player.querySelector(".article-audio__speed");

    audio.controls = false;
    audio.hidden = true;
    player.hidden = false;
    play.setAttribute("aria-pressed", "false");

    const render = () => {
      const total = audio.duration;
      const known = Number.isFinite(total) && total > 0;
      current.textContent = format(audio.currentTime);
      duration.textContent = known ? format(total) : "--:--";
      seek.max = known ? Math.floor(total) : 0;
      seek.value = Math.floor(audio.currentTime);
      seek.style.setProperty("--progress", known ? `${(audio.currentTime / total) * 100}%` : "0%");
      seek.setAttribute("aria-valuetext", `${format(audio.currentTime)} of ${known ? format(total) : "unknown"}`);
    };

    const setPlaying = playing => {
      play.setAttribute("aria-pressed", String(playing));
      play.setAttribute("aria-label", playing ? "Pause" : "Play");
      icon.textContent = playing ? "❚❚" : "▶";
    };

    play.addEventListener("click", () => {
      if (audio.paused) audio.play().catch(() => setPlaying(false));
      else audio.pause();
    });
    seek.addEventListener("input", () => {
      audio.currentTime = Number(seek.value);
      render();
    });
    speed.addEventListener("click", () => {
      const next = SPEEDS[(SPEEDS.indexOf(audio.playbackRate) + 1) % SPEEDS.length];
      audio.playbackRate = next;
      speed.textContent = `${next}×`;
      speed.setAttribute("aria-label", `Playback speed ${next}×`);
    });

    audio.addEventListener("play", () => setPlaying(true));
    audio.addEventListener("pause", () => setPlaying(false));
    audio.addEventListener("ended", () => setPlaying(false));
    ["timeupdate", "loadedmetadata", "durationchange", "seeked"].forEach(type => audio.addEventListener(type, render));
  });
})();
