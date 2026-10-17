# Alaska Salmon Openings - cloud refresher

Keeps https://alaska-salmon-openings.netlify.app current.

- Every 15 minutes `ci_refresh.py` runs the newest engine's `engine/cloud.py`:
  it reads ADF&G, rebuilds, runs the ship gates, and writes the news to the
  `data` branch (`overlay.json`, plus every announcement it has read).
- The public page reads `overlay.json` from this repository, so the news costs
  nothing on Netlify. The chart itself is redeployed only when the engine or
  the geometry changes, or once a week.
- The repository is public so the page can read the overlay. It holds no
  secrets: the Netlify token lives in Settings -> Secrets -> Actions.
- The engine is `engine-code-<version>.zip` here (its code; the chart's fixed
  geometry comes from the site's own engine, downloaded once and kept on the
  `data` branch). To move it forward, add a newer `engine-code-*.zip` or a whole
  `app-src.zip`, or let the desktop app publish its engine to the site.
- The workflow needs `pdfminer.six` (installed in the run) and the secret
  `NETLIFY_AUTH_TOKEN`; Netlify tokens last 90 days.
