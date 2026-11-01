import { useCallback, useEffect, useRef, useState } from "react";
import { getRunway, getRunwaySettings, updateRunwaySettings } from "@/api/runway";
import { ApiError } from "@/types/api";
import type { RunwayResponse, RunwaySettingsResponse } from "@/types/runway";

export function useRunway() {
  const [data, setData] = useState<RunwayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<RunwaySettingsResponse | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [draftIds, updateDraft] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const active = useRef(false);
  const resultGeneration = useRef(0);
  const settingsGeneration = useRef(0);
  const savingRef = useRef(false);

  const refresh = useCallback(async () => {
    if (savingRef.current) return;
    const generation = ++resultGeneration.current;
    setLoading(true);
    setError(null);
    try {
      const response = await getRunway();
      if (!active.current || generation !== resultGeneration.current) return;
      setData(response);
    } catch {
      if (!active.current || generation !== resultGeneration.current) return;
      setError("Could not load runway. Retry using local sources.");
    } finally {
      if (active.current && generation === resultGeneration.current) setLoading(false);
    }
  }, []);

  const retrySettings = useCallback(async () => {
    if (savingRef.current) return;
    const generation = ++settingsGeneration.current;
    setSettingsLoading(true);
    setSettingsError(null);
    setSaveError(null);
    setSaved(false);
    try {
      const response = await getRunwaySettings();
      if (!active.current || generation !== settingsGeneration.current) return;
      setSettings(response);
      updateDraft(response.liquid_account_ids);
    } catch {
      if (!active.current || generation !== settingsGeneration.current) return;
      setSettingsError("Could not load runway settings. Save is disabled until a successful retry.");
    } finally {
      if (active.current && generation === settingsGeneration.current) setSettingsLoading(false);
    }
  }, []);

  useEffect(() => {
    active.current = true;
    void refresh();
    void retrySettings();
    return () => {
      active.current = false;
      ++resultGeneration.current;
      ++settingsGeneration.current;
    };
  }, [refresh, retrySettings]);

  const setDraftIds = useCallback((ids: string[]) => {
    if (savingRef.current) return;
    updateDraft(ids);
    setSaved(false);
    setSaveError(null);
  }, []);

  const save = useCallback(async () => {
    if (!settings || settingsLoading || settingsError || savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    // Superseded result must not confirm a newer selection.
    ++resultGeneration.current;
    setLoading(false);
    const generation = ++settingsGeneration.current;
    try {
      const response = await updateRunwaySettings({ liquid_account_ids: draftIds });
      if (!active.current || generation !== settingsGeneration.current) return;
      setSettings(response);
      updateDraft(response.liquid_account_ids);
      setSaved(true);
      setData(null);
      savingRef.current = false;
      void refresh();
    } catch (err) {
      if (!active.current || generation !== settingsGeneration.current) return;
      setSaveError(err instanceof ApiError && err.status === 400
        ? "Selection not accepted. Select only eligible checking or savings accounts with recorded balances, then retry."
        : err instanceof ApiError && err.status === 409
          ? "Local sources changed. Retry saving when stable."
          : "Save could not be confirmed. Draft kept; retry or reload the saved selection to check.");
    } finally {
      if (active.current && generation === settingsGeneration.current) {
        savingRef.current = false;
        setSaving(false);
      }
    }
  }, [settings, settingsLoading, settingsError, draftIds, refresh]);

  const dirty = settings !== null && (
    draftIds.length !== settings.liquid_account_ids.length ||
    draftIds.some((id) => !settings.liquid_account_ids.includes(id))
  );

  return {
    data, loading, error, refresh,
    settings, settingsLoading, settingsError, retrySettings,
    draftIds, setDraftIds, dirty, save, saving, saved, saveError,
  };
}

export type RunwayState = ReturnType<typeof useRunway>;
