# Cinder Launcher Self-Update

Every Cinder launcher (Win/Mac/Linux) checks `manifest.json` on each plug-in.
If `*_version` is higher than the launcher's embedded `LAUNCHER_VERSION`, the
launcher downloads the new file from `*_url`, verifies it against `*_sha256`,
atomically swaps in place, and re-execs itself.

Buyer's machine never sees a manual update step.

## To push a patch

1. Edit the launcher in `products/cinder-anythingllm/usb-launchers/`.
2. Bump `LAUNCHER_VERSION=N` at the top.
3. Copy to `cinder/launchers/v{N}/`.
4. Compute the SHA256: `sha256sum v{N}/start-cinder.sh`.
5. Update `manifest.json` — bump `*_version`, set `*_url` to v{N} path, paste the new SHA.
6. Commit + push to GitHub Pages. Live in ~1 minute.

## Kill switch

Buyers (or testers) who want to pin the launcher at the on-disk version can set:

    CINDER_NO_SELF_UPDATE=1

…before launching. The self-update block becomes a no-op.

## Failure modes (all silent fall-through)

- Offline / GitHub Pages down → no update, on-disk launcher runs as before.
- Manifest malformed → no update.
- Download fails or SHA mismatch → temp file deleted, no update.
- New launcher download has no `#!` shebang (bash) → rejected, no update.

## Existing 4 drives shipped before this hook

They will not auto-update — they have no manifest fetch in them. Their launchers
are still correct for everything except the orphan-ollama race on Mac+Linux,
which is patched in v1+ but unreachable for the v0 drives. They will keep
working; they just can't pull tomorrow's patches.
