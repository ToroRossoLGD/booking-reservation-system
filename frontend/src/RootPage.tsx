import { useLocation } from "react-router-dom";
import App from "./App";
import PropertyHome from "./PropertyHome";

export default function RootPage() {
  const { pathname } = useLocation();
  return pathname === "/" ? <PropertyHome /> : <App />;
}
