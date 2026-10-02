import "./skip-to-content.css";

export default function SkipToContent() {
  return <a className="skip-to-content" href="#main-content" onClick={event => {
    const main = document.getElementById("main-content");
    if (!main) return;
    event.preventDefault();
    main.focus({ preventScroll: true });
    main.scrollIntoView({ behavior: "instant", block: "start" });
  }}>Preskoči na sadržaj</a>;
}
