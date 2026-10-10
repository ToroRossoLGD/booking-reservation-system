# Production browser security headers

The production/demo frontend image sends common security headers from
`deploy/security-headers.conf`. The server and both locations that define cache
headers explicitly include this file: nginx 1.28 does not inherit parent
`add_header` directives when a location has its own. `always` also covers errors.
HTML, hashed assets, missing assets, API responses and redirects retain their
existing cache behavior.

| Header | Behavior |
| --- | --- |
| `X-Content-Type-Options: nosniff` | Disables MIME-type guessing |
| `X-Frame-Options: DENY` | Rejects embedding, including same-origin frames |
| `Referrer-Policy: strict-origin-when-cross-origin` | Sends only the origin to other HTTPS sites, preserving OpenStreetMap attribution requirements without leaking paths/query strings |
| `Permissions-Policy` | Disables camera, microphone, geolocation and Payment Request; does not disable the file picker, manual map selection or clipboard sharing |
| `Content-Security-Policy` | Enforced resource restrictions for frontend documents |

The SPA CSP allows scripts and fetches only from the same origin. It blocks
inline scripts, external scripts, plugins, base URL changes, frames and form
submissions to other origins. It is an enforced policy, not report-only.

Compatibility exceptions are explicit:

- Inline **styles** remain allowed for React/Leaflet positioning and existing
  components. Inline **scripts** and `eval` are not allowed.
- Google Fonts stylesheet/font hosts are allowed. Other stylesheet hosts are not.
- HTTPS images remain allowed for configured storage and OpenStreetMap tiles.
  `data:` and `blob:` images support existing previews and protected-photo fetches.
  This broad HTTPS image allowance is not an exfiltration-proof sandbox; review
  narrower storage origins when a provider is selected.
- API documents such as `/api/docs` do not receive the SPA CSP, since Swagger has
  separate script requirements. They still receive the common headers. The rule
  uses the original request URI, so nginx's API rewrite cannot change the choice.
- Top-level OAuth navigation and payment redirects are not iframe integrations;
  they are unaffected. Future embedded payments, third-party scripts, workers or
  cross-origin API hosting need an explicit policy review and browser tests.

The policy is installed in the production nginx image, not the Vite development
server or a separately hosted API. Do not serve user-controlled scripts/HTML from
the trusted frontend origin. CSP complements escaping and validation; it does not
replace the remaining XSS/token-storage review or make localStorage immune to XSS.

## Validation and rollout

Production CI asserts headers on real nginx responses, including SPA routes,
assets, 404/401 errors, OAuth redirects and API responses. Chromium against the
same built image verifies that injected scripts, external fetches and iframe
embedding are rejected. Selected existing desktop/mobile tests exercise maps,
protected blob photos, recovery, verification and account-wide logout under the
policy. Their API/provider responses are mocked; this does not complete real
provider or private HTTPS staging acceptance.

Before hosting, verify that the outer TLS/access-control proxy preserves these
headers without appending conflicting CSPs. Configure HSTS at that TLS boundary
only after the actual domain and HTTPS coverage are verified. This internal HTTP
listener intentionally does not emit HSTS or force resource upgrades based on
untrusted forwarded headers. Check browser console violations against real photo
storage, maps, fonts and OAuth before closing the staging item.

When adding a new nginx location with `add_header`, include the shared file and
extend the real-stack smoke assertions. Keep both CI Playwright image versions
aligned with `frontend/package-lock.json`.

References: [nginx header inheritance and always](https://nginx.org/en/docs/http/ngx_http_headers_module.html),
[Mozilla CSP reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy),
[Mozilla Permissions-Policy reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy).
