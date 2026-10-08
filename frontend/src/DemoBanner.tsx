import { useEffect, useState } from "react";

export default function DemoBanner() {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${import.meta.env.VITE_API_URL ?? "/api"}/runtime-config`, { signal: controller.signal, cache: "no-store" })
      .then(async response => {
        if (!response.ok) return;
        const config = await response.json();
        if (!controller.signal.aborted) setDemo(config.demo === true);
      }).catch(() => {});
    return () => controller.abort();
  }, []);
  if (!demo) return null;
  return <aside role="note" className="demo-banner"><strong>DEMO — izmišljeni podaci.</strong> Bez stvarnih plaćanja i slanja poruka. Upload i registracija su isključeni. Koristite dodeljeni demo nalog; ne unosite lične podatke. Podaci se mogu resetovati.</aside>;
}
