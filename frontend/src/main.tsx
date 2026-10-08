import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import RootPage from "./RootPage";
import DemoBanner from "./DemoBanner";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <DemoBanner />
      <RootPage />
    </BrowserRouter>
  </StrictMode>,
);
