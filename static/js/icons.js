/* ============================================================
   BAY-E · Iconografía SVG en línea (sin dependencias externas).
   Uso: <i data-icon="home"></i>  →  Icons.hydrate(root)
   ============================================================ */
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  chat: '<path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"/><path d="M8 11h8M8 14h5"/>',
  brain: '<path d="M9.5 3A3.5 3.5 0 0 0 6 6.5c-2 .5-3 2-3 3.8 0 1.2.5 2.2 1.3 2.9-.2 2 1.3 3.8 3.4 3.8.4 1.7 1.9 3 3.8 3V3h-2z"/><path d="M14.5 3A3.5 3.5 0 0 1 18 6.5c2 .5 3 2 3 3.8 0 1.2-.5 2.2-1.3 2.9.2 2-1.3 3.8-3.4 3.8-.4 1.7-1.9 3-3.8 3V3h2z"/>',
  heart: '<path d="M12 20.5S4 14.5 4 9.3C4 6.4 6.2 4.5 8.6 4.5c1.6 0 2.8.8 3.4 1.9.6-1.1 1.8-1.9 3.4-1.9C17.8 4.5 20 6.4 20 9.3c0 5.2-8 11.2-8 11.2z"/>',
  eye: '<path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.8"/>',
  eyeoff: '<path d="M3 3l18 18"/><path d="M10.6 6.1A9.9 9.9 0 0 1 12 6c6.5 0 10 6 10 6a17 17 0 0 1-3.3 4M6.2 8.2A16.6 16.6 0 0 0 2 12s3.5 6 10 6a9.7 9.7 0 0 0 4-.85"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  gamepad: '<rect x="2" y="7" width="20" height="10" rx="5"/><path d="M7 12h3M8.5 10.5v3"/><circle cx="16" cy="11" r=".9" fill="currentColor"/><circle cx="18" cy="13.5" r=".9" fill="currentColor"/>',
  bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.4 1.1 2.2h5c0-.8.4-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>',
  list: '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4.5" cy="6" r="1.3" fill="currentColor"/><circle cx="4.5" cy="12" r="1.3" fill="currentColor"/><circle cx="4.5" cy="18" r="1.3" fill="currentColor"/>',
  map: '<path d="m3 6 6-2 6 2 6-2v14l-6 2-6-2-6 2V6z"/><path d="M9 4v14M15 6v14"/>',
  box: '<path d="m12 2 8 4.2v9.6L12 20l-8-4.2V6.2L12 2z"/><path d="m4 6.2 8 4.3 8-4.3M12 10.5V20"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5 5l2.1 2.1M16.9 16.9 19 19M19 5l-2.1 2.1M7.1 16.9 5 19"/>',
  shield: '<path d="M12 2.5 20 6v6c0 5-3.4 8.3-8 9.5C7.4 20.3 4 17 4 12V6l8-3.5z"/><path d="m9 12 2 2 4-4.5"/>',
  terminal: '<rect x="2.5" y="4" width="19" height="16" rx="2.5"/><path d="m6.5 9 3 3-3 3M12.5 15h5"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/>',
  speaker: '<path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4z"/><path d="M16.5 9a4.5 4.5 0 0 1 0 6M19 6.5a8 8 0 0 1 0 11"/>',
  wifi: '<path d="M2.5 9a15 15 0 0 1 19 0M6 12.5a10 10 0 0 1 12 0M9.3 16a5 5 0 0 1 5.4 0"/><circle cx="12" cy="19.3" r="1.2" fill="currentColor"/>',
  battery: '<rect x="2.5" y="8" width="17" height="8" rx="2"/><path d="M21.5 11v2"/>',
  sparkle: '<path d="m12 3 1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4L12 3z"/><path d="m18.5 16.5.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5 5-2z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  send: '<path d="m21.5 2.5-9.5 19-2.4-7.6L2.5 11l19-8.5z"/><path d="m21.5 2.5-11.9 11.4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6.5 7l1 13h9l1-13"/><path d="M10 11v5M14 11v5"/>',
  edit: '<path d="M14.5 5.5 18.5 9.5 8 20H4v-4L14.5 5.5z"/><path d="M12.5 7.5 16.5 11.5"/>',
  pin: '<path d="M12 21v-7"/><path d="M8.5 3h7l-1 6 3 3H6.5l3-3-1-6z"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1.5"/><path d="M5 9v10.5h14V9M10 13h4"/>',
  merge: '<circle cx="6" cy="6" r="2.6"/><circle cx="6" cy="18" r="2.6"/><path d="M6 8.6v6.8M8.6 6H13a4 4 0 0 1 4 4v4m-4-4 4 4 4-4" transform="translate(-2 0) scale(.85)"/><path d="M14 16.5 17 19.5 20 16.5" opacity="0"/>',
  download: '<path d="M12 3v12M6.5 10.5 12 16l5.5-5.5M4 20.5h16"/>',
  upload: '<path d="M12 16V4M6.5 9.5 12 4l5.5 5.5M4 20.5h16"/>',
  x: '<path d="M6 6 18 18M18 6 6 18"/>',
  check: '<path d="m5 13 4.5 4.5L19 7"/>',
  alert: '<path d="M12 3 2.5 20h19L12 3z"/><path d="M12 10v4.5"/><circle cx="12" cy="17.5" r="1" fill="currentColor"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 8-8M16.5 6.5l2 2M14 9l2 2"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  refresh: '<path d="M20 11A8 8 0 0 0 6.3 5.7L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 13.7 5.3L20 16"/><path d="M20 20v-4h-4"/>',
  power: '<path d="M12 3v8"/><path d="M7 6a7.5 7.5 0 1 0 10 0"/>',
  star: '<path d="m12 3.5 2.6 5.6 6 .8-4.4 4.2 1.1 6-5.3-2.9L7.3 20l1.1-6L4 9.9l6-.8L12 3.5z"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".8" fill="currentColor"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M17.5 14.4A6 6 0 0 1 21 20"/>',
  save: '<path d="m5 3h11l3 3v15H5V3z"/><path d="M8 3v6h7V3M8 15h8v6H8v-6z"/>',
  puzzle: '<path d="M10 3.5a2 2 0 1 1 4 0V5h3.5v3.5H20a2 2 0 1 1 0 4h-2.5V16h-3.5v2.5a2 2 0 1 1-4 0V16H6.5v-3.5H4a2 2 0 1 1 0-4h2.5V5H10V3.5z"/>',
  voice: '<path d="M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z"/><path d="M6.5 11a5.5 5.5 0 0 0 11 0M12 16.5V21M8.5 21h7"/>',
  pulse: '<path d="M2 12h4l3-8 4 16 3-8h6"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.3 9.3a2.8 2.8 0 1 1 4 2.8c-.9.6-1.3 1.1-1.3 2.1"/><circle cx="12" cy="17" r="1" fill="currentColor"/>',
  up: '<path d="m6 14 6-6 6 6"/>', down: '<path d="m6 10 6 6 6-6"/>',
  left: '<path d="m14 6-6 6 6 6"/>', right: '<path d="m10 6 6 6-6 6"/>',
  stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
};

const Icons = {
  svg(name, cls = "") {
    const p = ICONS[name] || ICONS.sparkle;
    return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
  },
  hydrate(root = document) {
    root.querySelectorAll("i[data-icon]").forEach((el) => {
      if (el.dataset.done) return;
      el.outerHTML = Icons.svg(el.dataset.icon);
      // outerHTML rompe el nodo; marcamos para no repetir en re-hidrataciones
    });
  },
};
