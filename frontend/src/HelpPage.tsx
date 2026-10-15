import { Link } from "react-router-dom";
import "./help-page.css";

export default function HelpPage() {
  return <div className="help-page">
    <header><Link to="/" className="ph-brand">bookica.</Link><Link to="/account">Moj nalog</Link></header>
    <main id="main-content" tabIndex={-1}>
      <p className="ph-eyebrow">VODIČ KROZ BOOKICU</p>
      <h1>Kako funkcioniše Bookica?</h1>
      <p className="help-intro">Pronađi smeštaj za odmor, stan za dugoročni najam ili nekretninu za kupovinu. Svaka vrsta ponude ima svoj način dogovora.</p>
      <nav aria-label="Teme vodiča"><a href="#boravci">Boravci i plaćanje</a><a href="#najam">Najam i kupovina</a><a href="#vlasnici">Za vlasnike</a><a href="#pomoc">Nalog i prijave oglasa</a></nav>

      <section id="boravci" aria-labelledby="stays-help-title">
        <h2 id="stays-help-title">Boravci i plaćanje</h2>
        <ol><li>Na oglasu za kraći boravak izaberi dolazak, odlazak i broj gostiju.</li><li>Zatraži obračun i proveri ukupnu cenu, valutu i vreme dolaska i odlaska.</li><li>Prijavi se i potvrdi rezervaciju. Za nove rezervacije potrebna je potvrđena email adresa.</li></ol>
        <p><strong>Plaćanje je na licu mesta.</strong> Bookica trenutno ne naplaćuje online boravke niti depozit. Rezervacija se potvrđuje odmah ako je termin i dalje slobodan; obračun sam po sebi ne čuva termin.</p>
        <details><summary>Kako otkazujem ili menjam datume?</summary><p>U odeljku „Moji boravci“ možeš da otkažeš boravak bez naknade pre datuma dolaska, prema vremenskoj zoni smeštaja. Proveri dostupne radnje na svojoj rezervaciji.</p><p>Za druge datume pošalji zahtev za izmenu sa novim obračunom. Stara rezervacija ostaje aktivna dok vlasnik ne odobri izmenu.</p></details>
        <Link to="/stays">Otvori moje boravke</Link>
      </section>

      <section id="najam" aria-labelledby="inquiries-help-title">
        <h2 id="inquiries-help-title">Dugoročni najam i kupovina</h2>
        <p>Na oglasu pošalji upit vlasniku. Za najam navedi željeni datum useljenja, trajanje i poruku; za kupovinu napiši šta te zanima. Potrebni su prijavljen nalog i potvrđena email adresa.</p>
        <details><summary>Da li slanjem upita rezervišem stan?</summary><p>Upit otvara razgovor sa vlasnikom; ne rezerviše nekretninu i ne pokreće naplatu. Bookica ne naplaćuje mesečnu kiriju ili depozit, ne sklapa ugovor o zakupu i ne obavlja kupoprodaju.</p></details>
        <details><summary>Kako dogovaram obilazak i pratim odgovore?</summary><p>Odgovori i predlozi obilaska pojavljuju se u tvojim upitima. Proveri datum, vreme i prikazanu vremensku zonu pre potvrde. Obaveštenja o ovim dogovorima dostupna su u aplikaciji; ne oslanjaj se na email ili push obaveštenja.</p></details>
        <div className="help-links"><Link to="/rentals">Moji upiti za najam</Link><Link to="/sales">Moji upiti za kupovinu</Link><Link to="/account/notifications">Obaveštenja</Link></div>
      </section>

      <section id="vlasnici" aria-labelledby="owners-help-title">
        <h2 id="owners-help-title">Objavljivanje oglasa</h2>
        <p>Obična registracija pravi korisnički nalog. Vlasnički pristup trenutno odobrava operater projekta; registracija ga ne dodeljuje automatski. Ako učestvuješ u testiranju kao vlasnik, dogovori odobrenje sa operaterom koji ti je omogućio pristup.</p>
        <p>Sa odobrenim pristupom u vlasničkom panelu unesi podatke o nekretnini, vrstu ponude, cenu i fotografije. Proveri pregled oglasa i izaberi objavljivanje. Nacrt nije vidljiv u javnoj ponudi.</p>
        <details><summary>Šta ako je oglas povučen ili suspendovan?</summary><p>Oglas koji nije objavljen ne pojavljuje se u javnoj ponudi. Za suspendovan oglas prati obrazloženje moderacije i dostupnu mogućnost ponovnog pregleda u vlasničkom panelu. Suspenzija sama po sebi ne otkazuje postojeće rezervacije.</p></details>
        <Link to="/owner">Otvori vlasnički panel</Link>
      </section>

      <section id="pomoc" aria-labelledby="account-help-title">
        <h2 id="account-help-title">Nalog i prijave oglasa</h2>
        <details><summary>Ne mogu da pristupim nalogu ili da potvrdim email</summary><p>Zatraži novi link za lozinku ili potvrdu email adrese. Proveri i spam folder. Ako link istekne, zatraži drugi umesto ponovnog korišćenja starog.</p><div className="help-links"><Link to="/forgot-password">Obnovi lozinku</Link><Link to="/verify-email">Potvrdi email adresu</Link></div></details>
        <details><summary>Kako prijavljujem problematičan oglas?</summary><p>Otvori stranicu oglasa i koristi obrazac za prijavu oglasa. Navedi razlog i kratak opis problema. Prijavu razmatra administrator; prijava ne znači automatsko uklanjanje oglasa.</p></details>
        <p>Sačuvan oglas je prečica za kasniji pregled — ne rezerviše nekretninu. Stari sistem rezervacija prostora po satu ima odvojen tok i pravila od boravaka opisanih ovde.</p>
      </section>
      <p className="help-note">Projekat je u izgradnji. Ovaj vodič opisuje trenutne funkcije aplikacije; nije zamena za uslove korišćenja i politiku privatnosti koji još treba da budu objavljeni pre javnog lansiranja.</p>
      <Link to="/">Nazad na ponudu nekretnina</Link>
    </main>
  </div>;
}
