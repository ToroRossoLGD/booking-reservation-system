import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return <main id="main-content" tabIndex={-1} className="recovery-page">
    <Link to="/">Bookica</Link>
    <p>404</p>
    <h1>Stranica nije pronađena.</h1>
    <p>Link možda nije ispravan ili je stranica premeštena. Nastavi pretragu nekretnina ili otvori svoj nalog.</p>
    <p><Link to="/">Pogledaj ponudu nekretnina</Link></p>
    <p><Link to="/account">Moj nalog</Link></p>
  </main>;
}
