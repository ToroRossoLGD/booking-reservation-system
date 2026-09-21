import { useLocation } from "react-router-dom";
import App from "./App";
import PropertyHome from "./PropertyHome";
import StaysPage from "./StaysPage";

export default function RootPage() {
  const { pathname } = useLocation();
  if (pathname === "/stays") return <StaysPage key="guest" />;
  if (pathname === "/owner/stays") return <StaysPage key="owner" owner />;
  return pathname === "/" ? <PropertyHome /> : <App />;
}
