import { useEffect } from "react";
import { api } from "./api";

export default function PropertyViewTracker({ propertyId }: { propertyId: number }) {
  useEffect(() => {
    async function track() {
      try {
        if (navigator.doNotTrack === "1") return;
        const key = "bookica_view_session";
        const day = new Date().toISOString().slice(0, 10);
        const saved = sessionStorage.getItem(key)?.split("|");
        const id = saved?.[0] === day && saved[1] ? saved[1] : crypto.randomUUID();
        sessionStorage.setItem(key, `${day}|${id}`);
        await api.recordPropertyView(propertyId, id);
      } catch { /* Analytics must never block reading or booking a listing. */ }
    }
    void track();
  }, [propertyId]);
  return null;
}
