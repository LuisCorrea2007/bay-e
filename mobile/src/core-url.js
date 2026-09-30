function isIpv4(host) {
  const parts = host.split(".");
  if (parts.length !== 4) return null;
  const nums = parts.map(Number);
  if (nums.some((n, i) => !Number.isInteger(n) || n < 0 || n > 255 || String(n) !== parts[i])) return null;
  return nums;
}

export function isPrivateLanHost(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  if (!host) return false;
  if (host === "localhost" || host === "::1" || host.endsWith(".local")) return true;
  if (host.startsWith("fc") || host.startsWith("fd")) return host.includes(":");
  if (/^fe[89ab][0-9a-f]:/i.test(host)) return true;
  const ip = isIpv4(host);
  if (!ip) return false;
  const [a, b] = ip;
  return a === 10
    || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && b === 168)
    || a === 127
    || (a === 169 && b === 254);
}

export function normalizeCoreUrl(raw) {
  const input = String(raw || "").trim();
  if (!input) throw new Error("Configura la URL de BAY-E Core");
  let url;
  try { url = new URL(input); }
  catch { throw new Error("La URL del Core no es válida"); }
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Usa http:// o https://");
  if (url.username || url.password) throw new Error("No pongas credenciales dentro de la URL");
  if (url.protocol === "http:" && !isPrivateLanHost(url.hostname)) {
    throw new Error("HTTP solo se permite para un Core local/privado; usa HTTPS fuera de la LAN");
  }
  url.hash = "";
  url.search = "";
  return url.toString().replace(/\/$/, "");
}
