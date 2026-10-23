import json

import streamlit as st
import streamlit.components.v1 as components


# Runs in the parent Streamlit page: adds a sun/moon switch to the top toolbar. Streamlit 1.40
# has no API for switching themes, so the button writes the theme Streamlit restores from
# localStorage and reloads the page.
THEME_TOGGLE_SCRIPT = '''
(() => {
  if (window.__btcThemeToggleInstalled) return;
  window.__btcThemeToggleInstalled = true;
  const BUTTON_ID = 'btc-theme-toggle';
  const STORAGE_KEY = `stActiveTheme-${window.location.pathname}-v1`;
  const THEME_COOKIE = 'btc_theme';
  const ICON_ATTRIBUTES = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    + 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
  const SUN_ICON = `<svg ${ICON_ATTRIBUTES}><circle cx="12" cy="12" r="4"/>`
    + '<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2'
    + 'M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
  const MOON_ICON = `<svg ${ICON_ATTRIBUTES}><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;

  function isDarkTheme() {
    const app = document.querySelector('[data-testid="stApp"]');
    if (!app) return false;
    const channels = getComputedStyle(app).color.match(/[\\d.]+/g)?.map(Number);
    if (!channels || channels.length < 3) return false;
    const linear = channels.slice(0, 3).map(channel => {
      const normalized = channel / 255;
      return normalized <= 0.04045
        ? normalized / 12.92
        : ((normalized + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2] > 0.38;
  }

  const initialThemeCookie = readThemeCookie();
  let reloading = false;

  function readThemeCookie() {
    return document.cookie.match(new RegExp(`(?:^|; )${THEME_COOKIE}=(\\\\w+)`))?.[1];
  }

  // The dataframe grid paints on a canvas that CSS cannot restyle, so Python reads the theme
  // from this cookie and colors the cells itself.
  function setThemeCookie(dark) {
    document.cookie = `${THEME_COOKIE}=${dark ? 'dark' : 'light'}; path=/; max-age=31536000; SameSite=Lax`;
  }

  function syncThemeCookie(dark) {
    if (reloading) return;
    setThemeCookie(dark);
    // Python only sees the cookies sent when the session opened, so reload once when it saw
    // another theme. The check on the stored value avoids a reload loop if cookies are blocked.
    if ((initialThemeCookie === 'dark') !== dark && readThemeCookie() === (dark ? 'dark' : 'light')) {
      reloading = true;
      window.location.reload();
    }
  }

  function syncButton(button) {
    const dark = isDarkTheme();
    // main.css keys the dark palette on this class; the price chart sets it too, but only once it loads.
    document.body.classList.toggle('btc-dark-theme', dark);
    syncThemeCookie(dark);
    if (button.dataset.dark === String(dark)) return;
    button.dataset.dark = String(dark);
    button.setAttribute('aria-checked', String(dark));
    button.innerHTML = `<span class="btc-theme-toggle-knob">${dark ? MOON_ICON : SUN_ICON}</span>`;
    const label = dark ? 'Switch to light theme' : 'Switch to dark theme';
    button.title = label;
    button.setAttribute('aria-label', label);
  }

  function toggleTheme(event) {
    const dark = isDarkTheme();
    try {
      if (dark) {
        // Without a stored theme Streamlit falls back to the light theme from config.toml.
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify({name: 'Dark'}));
      }
    } catch (_) {
      return;
    }
    // Keeps the periodic sync from writing the old theme back before the reload.
    reloading = true;
    setThemeCookie(!dark);
    // Let the knob slide across before the reload applies the new theme.
    const button = event.currentTarget;
    button.setAttribute('aria-checked', String(!dark));
    button.querySelector('.btc-theme-toggle-knob').innerHTML = dark ? SUN_ICON : MOON_ICON;
    setTimeout(() => window.location.reload(), 200);
  }

  function mountButton() {
    const toolbar = document.querySelector('[data-testid="stToolbar"]');
    if (!toolbar) return;
    let button = document.getElementById(BUTTON_ID);
    if (!button) {
      button = document.createElement('button');
      button.id = BUTTON_ID;
      button.type = 'button';
      button.setAttribute('role', 'switch');
      button.addEventListener('click', toggleTheme);
      toolbar.prepend(button);
    }
    syncButton(button);
  }

  mountButton();
  // Streamlit can re-render the header, and the theme can also change from its settings menu.
  new MutationObserver(mountButton).observe(document.body, {childList: true, subtree: true});
  setInterval(mountButton, 1000);
})();
'''


def is_dark_theme():
    return st.context.cookies.get('btc_theme') == 'dark'


def render_theme_toggle():
    script = json.dumps(THEME_TOGGLE_SCRIPT).replace('</', '<\\/')
    with st.container(key='theme_toggle'):
        components.html(
            '<script>'
            'const script = window.parent.document.createElement("script");'
            f'script.textContent = {script};'
            'window.parent.document.head.appendChild(script);'
            '</script>',
            height=0,
        )
