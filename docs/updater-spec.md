# Self-Update Specification

Seedance Watermark Remover is distributed as a Windows one-folder portable ZIP. The updater must preserve that model: keep the EXE together with `_internal`, avoid editing the original video workflow, and never partially replace files while the app is still running.

## Version Source

- The app checks the public GitHub Releases API endpoint:
  `https://api.github.com/repos/bakhtiersizhaev/seedance-watermark-remover/releases/latest`
- The release tag must use semver: `vMAJOR.MINOR.PATCH`.
- The Windows asset must be named `SeedanceWatermarkRemover-Windows-x64-portable.zip`.
- A newer release is detected only when the latest semver tuple is greater than the local `APP_VERSION`.

## User Experience

- On startup, the app performs a quiet background check.
- The footer button starts as `Check updates`.
- If no update is available, a manual check shows `Up to date`.
- If an update is available, the footer button changes to `Update to vX.Y.Z` and briefly pulses.
- Clicking the update button asks for confirmation before downloading or replacing anything.
- All update strings are localized in English, Russian, and Chinese.

## Install Flow

1. Download the latest Windows ZIP into a temporary update folder.
2. Extract the ZIP and verify that it contains `SeedanceWatermarkRemover/SeedanceWatermarkRemover.exe`.
3. Generate a small Windows `.cmd` helper in the same temporary folder.
4. Launch the helper and close the running app.
5. The helper stops the old process, renames the old app folder as a rollback backup, copies the new portable folder into the old location, starts the new EXE, then removes the backup.
6. If replacement fails, the helper attempts rollback and opens the GitHub Release page.

## Safety Rules

- Source-mode runs do not self-update. They open the release page instead.
- Non-Windows runs do not self-update.
- The updater never changes user videos or output folders.
- The app keeps GitHub Release download as the fallback path.
- The updater does not require GitHub credentials.

## Test Coverage

- Unit tests cover semver parsing and comparison.
- Unit tests verify that source-mode self-update is rejected.
- GUI layout tests verify the footer update button is visible on a standard 900x1032 window.
- CI runs lint, unit tests, GUI self-test, and processing smoke test on Windows.
