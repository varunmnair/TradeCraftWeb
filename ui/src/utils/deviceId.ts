const DEVICE_ID_KEY = 'tradecraftx_device_id';

/** Stable per-browser identifier used for device-scoped broker selection. */
export function getDeviceId(): string {
  if (typeof window === 'undefined') return 'server';
  let deviceId = window.localStorage.getItem(DEVICE_ID_KEY);
  if (!deviceId) {
    const cryptoRef = window.crypto as Crypto | undefined;
    deviceId =
      cryptoRef && typeof cryptoRef.randomUUID === 'function'
        ? cryptoRef.randomUUID()
        : `device-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(DEVICE_ID_KEY, deviceId);
  }
  return deviceId;
}