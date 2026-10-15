import { lazy, Suspense, useEffect, useSyncExternalStore } from "react";
import { useLocation } from "react-router-dom";
import "./oauthRedirect";
import RouteBoundary from "./RouteBoundary";
import OAuthFeedback from "./OAuthFeedback";
import NotFoundPage from "./NotFoundPage";
import { isKnownPage, normalizePagePath } from "./routing";
import PropertyHome from "./PropertyHome";
import SkipToContent from "./SkipToContent";
import { initialPasswordResetToken } from "./passwordResetToken";
import { routeMetadata, usePageMetadata } from "./page-metadata";
import { getEmailVerificationToken, subscribeEmailVerificationToken, syncEmailVerificationToken } from "./emailVerificationToken";

const PropertyDetailPage = lazy(() => import("./PropertyDetailPage"));
const HelpPage = lazy(() => import("./HelpPage"));
const App = lazy(() => import("./App"));
const StaysPage = lazy(() => import("./StaysPage"));
const RentalInquiriesPage = lazy(() => import("./RentalInquiriesPage"));
const SavedPropertiesPage = lazy(() => import("./SavedPropertiesPage"));
const EmailVerification = lazy(() => import("./EmailVerification"));
const AccountSecurity = lazy(() => import("./AccountSecurity"));
const ForgotPasswordPage = lazy(() => import("./PasswordRecovery").then(module => ({ default: module.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import("./PasswordRecovery").then(module => ({ default: module.ResetPasswordPage })));
const OwnerPropertyPreview = lazy(() => import("./OwnerPropertyPreview"));
const OwnerPropertyAnalytics = lazy(() => import("./OwnerPropertyAnalytics"));
const PropertyModerationPage = lazy(() => import("./PropertyModerationPage"));

export default function RootPage() {
  const pathname = normalizePagePath(useLocation().pathname);
  // Public listing pages own their loading/error/detail metadata.
  usePageMetadata(pathname.startsWith("/properties/") ? null : routeMetadata(pathname));
  return <><SkipToContent /><OAuthFeedback /><RouteBoundary key={pathname}>
    <Suspense fallback={<main id="main-content" tabIndex={-1}><p role="status">Učitavanje stranice…</p></main>}>
      <PageContent />
    </Suspense>
  </RouteBoundary></>;
}

function PageContent() {
  const { pathname: rawPathname, hash } = useLocation();
  const pathname = normalizePagePath(rawPathname);
  const verificationToken = useSyncExternalStore(subscribeEmailVerificationToken, getEmailVerificationToken);
  useEffect(() => { syncEmailVerificationToken(); }, [pathname, hash]);
  if (!isKnownPage(pathname)) return <NotFoundPage />;
  if (pathname === "/help") return <HelpPage />;
  if (pathname === "/account/security") return <AccountSecurity />;
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
