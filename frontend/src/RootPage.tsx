import { lazy, Suspense } from "react";
import { useLocation } from "react-router-dom";
import App from "./App";
import PropertyHome from "./PropertyHome";
import StaysPage from "./StaysPage";
import RentalInquiriesPage from "./RentalInquiriesPage";
import SavedPropertiesPage from "./SavedPropertiesPage";

const PropertyDetailPage = lazy(() => import("./PropertyDetailPage"));
const OwnerPropertyPreview = lazy(() => import("./OwnerPropertyPreview"));
const OwnerPropertyAnalytics = lazy(() => import("./OwnerPropertyAnalytics"));

export default function RootPage() {
  const { pathname } = useLocation();
  const preview = pathname.match(/^\/owner\/properties\/([^/]+)\/preview\/?$/);
  if (preview) return <Suspense fallback={<p role="status">Učitavanje pregleda…</p>}><OwnerPropertyPreview key={preview[1]} id={preview[1]} /></Suspense>;
  if (pathname === "/owner/analytics") return <Suspense fallback={<p role="status">Učitavanje analitike…</p>}><OwnerPropertyAnalytics /></Suspense>;
  if (pathname.startsWith("/properties/")) {
    const id = pathname.slice("/properties/".length).replace(/\/$/, "");
    return <Suspense fallback={<p role="status">Učitavanje oglasa…</p>}><PropertyDetailPage key={id} id={id} /></Suspense>;
  }
  if (pathname === "/saved") return <SavedPropertiesPage />;
  if (pathname === "/rentals") return <RentalInquiriesPage key="renter" />;
  if (pathname === "/owner/rentals") return <RentalInquiriesPage key="landlord" owner />;
  if (pathname === "/stays") return <StaysPage key="guest" />;
  if (pathname === "/owner/stays") return <StaysPage key="owner" owner />;
  return pathname === "/" ? <PropertyHome /> : <App />;
}
