# L4: visual

For UIs: the target must render the same as the original.

1. Build a route/state list: URL plus a setup script (log in, open a modal, fill a form) per screenshot.
2. Use Playwright on both apps with the same viewport(s), device scale factor, fonts, `prefers-color-scheme`, and locale. Freeze time (`page.clock`), disable animations (`reducedMotion: 'reduce'` plus a CSS override), and mock network responses that vary.
3. Capture full-page PNGs and an accessibility snapshot (`page.accessibility.snapshot()` or an ARIA snapshot) for each state.
4. Compare pixels with `pixelmatch` and a threshold (start at 0.1% differing pixels per screenshot), then compare the accessibility trees structurally. The accessibility diff catches broken semantics that pixels miss.
5. Save diff images to `.slopfork/visual/diffs/` and link them in the report.

Pixel-identical output across frameworks is rarely worth it. Agree with the user on a threshold per page, and accept known differences (font rendering, scrollbar) explicitly.
