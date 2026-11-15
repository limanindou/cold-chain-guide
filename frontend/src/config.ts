/**
 * Runtime config. The deploy script writes /config.json next to the build, so the same
 * build works for any stack (no rebuild per environment). Vite env vars are the
 * local-development fallback.
 */
export interface RuntimeConfig {
  apiUrl: string;
  deviceKey: string;
  siteUrl: string;
}

let config: RuntimeConfig = {
  apiUrl: import.meta.env.VITE_API_URL ?? '',
  deviceKey: import.meta.env.VITE_DEVICE_KEY ?? '',
  siteUrl: import.meta.env.VITE_SITE_URL ?? '',
};

export async function loadConfig(): Promise<RuntimeConfig> {
  try {
    const res = await fetch('/config.json', { cache: 'no-store' });
    if (res.ok) {
      const json = (await res.json()) as Partial<RuntimeConfig>;
      config = {
        apiUrl: json.apiUrl || config.apiUrl,
        deviceKey: json.deviceKey || config.deviceKey,
        siteUrl: json.siteUrl || config.siteUrl,
      };
    }
  } catch {
    /* fall back to env */
  }
  config.apiUrl = config.apiUrl.replace(/\/$/, '');
  config.siteUrl = config.siteUrl.replace(/\/$/, '');
  return config;
}

export function getConfig(): RuntimeConfig {
  return config;
}
