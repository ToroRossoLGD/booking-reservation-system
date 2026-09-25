import { useState } from "react";
import type { CalendarDownload } from "./calendar-export";

export default function CalendarDownloadButton({ create }: { create: () => CalendarDownload | null }) {
  const [error, setError] = useState(false);
  function download() {
    setError(false);
    let url: string | undefined;
    let anchor: HTMLAnchorElement | undefined;
    try {
      const file = create();
      if (!file) return;
      url = URL.createObjectURL(new Blob([file.contents], { type: "text/calendar;charset=utf-8" }));
      anchor = document.createElement("a");
      anchor.href = url; anchor.download = file.filename;
      document.body.append(anchor); anchor.click();
    } catch { setError(true); }
    finally {
      anchor?.remove();
      if (url) { const downloadUrl = url; window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000); }
    }
  }
  return <div className="calendar-download">
    <button type="button" className="ph-outline" onClick={download}>Dodaj u kalendar (.ics)</button>
    <p>Preuzeti termin se ne ažurira automatski. Posle izmene ili otkazivanja ažuriraj i svoj kalendar.</p>
    {error && <p role="alert">Preuzimanje nije uspelo. Pokušaj ponovo.</p>}
  </div>;
}
