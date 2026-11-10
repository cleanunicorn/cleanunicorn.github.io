(() => {
  const title = document.querySelector('.page-title');
  if (!title || !title.textContent.trimEnd().endsWith('λ')) return;

  const text = title.lastChild;
  if (!text || text.nodeType !== Node.TEXT_NODE) return;
  text.textContent = text.textContent.replace(/λ\s*$/, '');
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'lambda-trigger';
  trigger.textContent = 'λ';
  trigger.setAttribute('aria-label', 'Lambda');
  title.append(trigger);

  const hud = document.createElement('aside');
  hud.className = 'lambda-hud';
  hud.hidden = true;
  hud.setAttribute('aria-label', 'A familiar pattern');
  hud.innerHTML = `
    <span class="lambda-hud__symbol" aria-hidden="true">λ</span>
    <div class="lambda-hud__message" role="status" aria-live="polite"></div>
    <button type="button" class="lambda-hud__close" aria-label="Dismiss Easter egg">×</button>`;
  document.body.append(hud);
  const message = hud.querySelector('[role="status"]');
  const dismiss = () => {
    const restoreFocus = hud.contains(document.activeElement);
    hud.hidden = true;
    message.replaceChildren();
    if (restoreFocus) trigger.focus();
  };
  hud.querySelector('button').addEventListener('click', dismiss);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !hud.hidden) dismiss();
  });

  let clicks = 0;
  let pulse;
  trigger.addEventListener('click', () => {
    clicks += 1;
    trigger.classList.remove('lambda-trigger--pulse');
    void trigger.offsetWidth;
    trigger.classList.add('lambda-trigger--pulse');
    clearTimeout(pulse);
    pulse = setTimeout(() => trigger.classList.remove('lambda-trigger--pulse'), 700);
    if (clicks % 3 !== 0) return;

    hud.hidden = false;
    message.innerHTML = `<strong>PATTERN DETECTED · 03</strong>
      <p>The first time, you do it.<br>The second time, you notice it.<br>
      The third time, you build it into the system.</p>
      <small>Welcome to the Lambda Complex.</small>`;
    hud.classList.remove('lambda-hud--arrive');
    void hud.offsetWidth;
    hud.classList.add('lambda-hud--arrive');
  });
})();
