import { useCallback, useEffect, useMemo, useState } from 'react';
import type { TradeTableConfig } from '../components/tradeTable/types';
import { getTradeTableRegistryEntry } from '../config/tradeTableRegistry';
import {
  getCachedUiPageConfig,
  invalidateUiPageConfig,
  loadUiPageConfig,
  setCachedUiPageConfig,
  subscribeUiPageConfig,
} from '../config/uiConfigCache';
import type { UiPageConfig } from '../types';

function fallbackConfig(pageId: string): UiPageConfig | undefined {
  const entry = getTradeTableRegistryEntry(pageId);
  if (!entry) return undefined;
  const cfg = entry.config;
  return {
    pageId,
    searchEnabled: Boolean(cfg.searchEnabled),
    searchField: cfg.searchField ?? null,
    defaultPageSize: cfg.defaultPageSize ?? 25,
    allowedPageSizes: cfg.allowedPageSizes ?? [25, 50, 100],
    density: cfg.density === 'comfortable' ? 'comfortable' : 'compact',
    selectionEnabled: Boolean(cfg.selectionEnabled),
    defaultSort: cfg.defaultSort ?? null,
    mobilePrimaryFields: cfg.mobilePrimaryFields ?? [],
    mobileDetailFields: cfg.mobileDetailFields ?? [],
    columns: (cfg.columns ?? []).map((c) => ({
      id: c.id,
      label: c.label,
      dataType: c.dataType,
      visible: c.visible,
      sortable: c.sortable,
      filterable: c.filterable,
      position: c.position,
      required: c.required,
      mobilePrimary: c.mobilePrimary,
      mobileDetail: c.mobileDetail,
      width: c.width,
    })),
    _meta: { source: 'default', schemaVersion: 1, updatedAt: null, updatedBy: null },
  };
}

export function uiPageConfigToTradeTableConfig<T extends { id: string | number } = { id: string | number }>(
  pageId: string,
  config: UiPageConfig,
  base?: TradeTableConfig<T>,
): TradeTableConfig<T> {
  const baseCols = (base?.columns ?? []) as TradeTableConfig<T>['columns'];
  const baseById = new Map(baseCols.map((c) => [c.id, c]));
  const density: TradeTableConfig<T>['density'] = config.density === 'comfortable' ? 'comfortable' : 'compact';
  return {
    pageId,
    searchEnabled: config.searchEnabled,
    searchField: config.searchField ?? undefined,
    defaultSort: config.defaultSort ?? null,
    defaultPageSize: config.defaultPageSize,
    allowedPageSizes: config.allowedPageSizes,
    density,
    selectionEnabled: config.selectionEnabled,
    mobilePrimaryFields: config.mobilePrimaryFields,
    mobileDetailFields: config.mobileDetailFields,
    columns: config.columns.map((col, idx) => {
      const baseCol = baseById.get(col.id);
      return {
        ...(baseCol ?? {}),
        id: col.id,
        label: col.label ?? baseCol?.label ?? col.id,
        dataType: (col.dataType ?? baseCol?.dataType ?? 'text') as any,
        visible: col.visible,
        sortable: col.sortable,
        filterable: col.filterable,
        position: typeof col.position === 'number' ? col.position : idx,
        required: col.required ?? baseCol?.required,
        mobilePrimary: col.mobilePrimary ?? baseCol?.mobilePrimary,
        mobileDetail: col.mobileDetail ?? baseCol?.mobileDetail,
        width: col.width ?? baseCol?.width,
      } as any;
    }) as TradeTableConfig<T>['columns'],
  };
}

export function useUiPageConfig(pageId: string) {
  const [config, setConfig] = useState<UiPageConfig | undefined>(() => getCachedUiPageConfig(pageId) ?? fallbackConfig(pageId));
  const [loading, setLoading] = useState<boolean>(() => !getCachedUiPageConfig(pageId));
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await loadUiPageConfig(pageId, force);
      setConfig(loaded);
      return loaded;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load UI configuration';
      setError(message);
      const fb = fallbackConfig(pageId);
      if (fb) {
        setConfig(fb);
        // Do not poison cache with fallback; allow retry.
      }
      return fb;
    } finally {
      setLoading(false);
    }
  }, [pageId]);

  useEffect(() => {
    let mounted = true;
    const sync = () => {
      if (!mounted) return;
      const cached = getCachedUiPageConfig(pageId);
      if (cached) setConfig(cached);
    };
    const unsub = subscribeUiPageConfig(sync);
    void refresh(false);
    return () => {
      mounted = false;
      unsub();
    };
  }, [pageId, refresh]);

  const updateCache = useCallback((next: UiPageConfig) => {
    setCachedUiPageConfig(pageId, next);
    setConfig(next);
  }, [pageId]);

  const invalidate = useCallback(() => {
    invalidateUiPageConfig(pageId);
  }, [pageId]);

  return useMemo(() => ({ config, loading, error, refresh, updateCache, invalidate }), [config, loading, error, refresh, updateCache, invalidate]);
}