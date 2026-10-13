import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no native dialog implementation. Browser tests verify focus,
// background inertness and Escape behavior; this shim only models open/close.
HTMLDialogElement.prototype.showModal = function () { this.open = true; };
HTMLDialogElement.prototype.close = function () { this.open = false; };

afterEach(() => { cleanup(); window.history.replaceState(null, "", "/"); });
