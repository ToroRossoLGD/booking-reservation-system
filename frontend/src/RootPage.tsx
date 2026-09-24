import { lazy, Suspense } from "react";
import { useLocation } from "react-router-dom";
import App from "./App";
import PropertyHome from "./PropertyHome";
import StaysPage from "./StaysPage";
import RentalInquiriesPage from "./RentalInquiriesPage";
import SavedPropertiesPage from "./SavedPropertiesPage";

const PropertyDetailPage = lazy(() => import("./PropertyDetailPage"));

export default function RootPage() {
  const { pathname } = useLocation();
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
