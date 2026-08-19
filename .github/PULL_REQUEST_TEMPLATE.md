## What does this PR do?

<!-- Brief summary. Link any issues: "Fixes #123". -->

- [ ] New flow (Python) / new Rust command / GUI change / fix / docs

## Checklist

- [ ] `cargo build --release` passes.
- [ ] `cargo test --release` passes (or note why not runnable).
- [ ] `pytest tests/ -q` passes (or the 5 pre-existing failures are unchanged).
- [ ] New flow wired into `JOBS` so it appears in the GUI.
- [ ] New Rust command: usage text in `main.rs` + `bridge.py` wrapper.
- [ ] GUI: themed colors (`C[...]`), signal-based updates, scroll-safe layout.
- [ ] No secrets, binaries, or device-identifying data added.
- [ ] README feature matrix updated if capability changed.

## Test evidence

<!-- Paste `flashpilot-bridge detect` output, logs, or pytest results. -->

## Screenshots (if UI)

<!-- Optional but very welcome. -->