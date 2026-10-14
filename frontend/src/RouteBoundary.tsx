import { Component, type ReactNode } from "react";

export default class RouteBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <main id="main-content" tabIndex={-1} className="dashboard-page">
      <h1>Stranica nije učitana.</h1>
      <p role="alert">Proveri vezu i pokušaj ponovo. Sačuvani podaci na nalogu ostaju dostupni.</p>
      <button className="button primary" onClick={() => window.location.reload()}>Učitaj ponovo</button>
      <p><a href="/">Vrati se na početnu</a></p>
    </main>;
    return this.props.children;
  }
}
