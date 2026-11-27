import { api } from '../api/client';
import type { UiPageConfig } from '../types';

type Listener = () => void;

const cache = new Map<string, UiPageConfig>();
const inflight = new Map<string, Promise<UiPageConfig>>();
const listeners = new Set<Listener>();

function notify() {
  listeners.forEach((l) => l());
}

export function getCachedUiPageConfig(pageId: string): UiPageConfig | undefined {
  return cache.get(pageId);
}

export function setCachedUiPageConfig(pageId: string, config: UiPageConfig): void {
  cache.set(pageId, config);
  notify();
}

export function invalidateUiPageConfig(pageId?: string): void {
  if (pageId) {
    cache.delete(pageId);
    inflight.delete(pageId);
  } else {
    cache.clear();
    inflight.clear();
  }
  notify();
}

export function subscribeUiPageConfig(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function loadUiPageConfig(pageId: string, force = false): Promise<UiPageConfig> {
  if (!force) {
    const cached = cache.get(pageId);
    if (cached) return cached;
    const pending = inflight.get(pageId);
    if (pending) return pending;
  }

  const promise = api
    .getUiPageConfig(pageId)
    .then((config) => {
      cache.set(pageId, config);
      inflight.delete(pageId);
      notify();
      return config;
    })
    .catch((err) => {
      inflight.delete(pageId);
      throw err;
    });

  inflight.set(pageId, promise);
  return promise;
}