import { lazy, Suspense, useEffect, useSyncExternalStore } from "react";
import { useLocation } from "react-router-dom";
import App from "./App";
import PropertyHome from "./PropertyHome";
import StaysPage from "./StaysPage";
import RentalInquiriesPage from "./RentalInquiriesPage";
import SavedPropertiesPage from "./SavedPropertiesPage";
import SkipToContent from "./SkipToContent";
import { ForgotPasswordPage, ResetPasswordPage } from "./PasswordRecovery";
import { initialPasswordResetToken } from "./passwordResetToken";
import EmailVerification from "./EmailVerification";
import { getEmailVerificationToken, subscribeEmailVerificationToken, syncEmailVerificationToken } from "./emailVerificationToken";

const PropertyDetailPage = lazy(() => import("./PropertyDetailPage"));
const OwnerPropertyPreview = lazy(() => import("./OwnerPropertyPreview"));
const OwnerPropertyAnalytics = lazy(() => import("./OwnerPropertyAnalytics"));
const PropertyModerationPage = lazy(() => import("./PropertyModerationPage"));

export default function RootPage() {
  return <><SkipToContent /><PageContent /></>;
}

function PageContent() {
  const { pathname, hash } = useLocation();
  const verificationToken = useSyncExternalStore(subscribeEmailVerificationToken, getEmailVerificationToken);
  useEffect(() => { syncEmailVerificationToken(); }, [pathname, hash]);
  if (pathname === "/verify-email") return <EmailVerification key={verificationToken} token={verificationToken} />;
  if (pathname === "/forgot-password") return <ForgotPasswordPage />;
  if (pathname === "/reset-password") return <ResetPasswordPage token={initialPasswordResetToken} />;
  if (pathname === "/moderation") return <Suspense fallback={<main id="main-content" tabIndex={-1}><p role="status">Učitavanje moderacije…</p></main>}><PropertyModerationPage /></Suspense>;
  const preview = pathname.match(/^\/owner\/properties\/([^/]+)\/preview\/?$/);
  if (preview) return <Suspense fallback={<main id="main-content" tabIndex={-1}><p role="status">Učitavanje pregleda…</p></main>}><OwnerPropertyPreview key={preview[1]} id={preview[1]} /></Suspense>;
  if (pathname === "/owner/analytics") return <Suspense fallback={<main id="main-content" tabIndex={-1}><p role="status">Učitavanje analitike…</p></main>}><OwnerPropertyAnalytics /></Suspense>;
  if (pathname.startsWith("/properties/")) {
    const id = pathname.slice("/properties/".length).replace(/\/$/, "");
    return <Suspense fallback={<main id="main-content" tabIndex={-1}><p role="status">Učitavanje oglasa…</p></main>}><PropertyDetailPage key={id} id={id} /></Suspense>;
  }
  if (pathname === "/saved") return <SavedPropertiesPage />;
  if (pathname === "/rentals") return <RentalInquiriesPage key="renter" />;
  if (pathname === "/sales") return <RentalInquiriesPage key="buyer" sale />;
  if (pathname === "/owner/sales") return <RentalInquiriesPage key="seller" owner sale />;
  if (pathname === "/owner/rentals") return <RentalInquiriesPage key="landlord" owner />;
  if (pathname === "/stays") return <StaysPage key="guest" />;
  if (pathname === "/owner/stays") return <StaysPage key="owner" owner />;
  return pathname === "/" ? <PropertyHome /> : <App />;
}
