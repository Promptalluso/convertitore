# Version 0.1 public release gate

The development artifacts from `check.yml` are unsigned test packages. Do not publish them as follower downloads.

1. Choose final public app name, icon, bundle identifier and publisher identity. Replace the working name `Convertitore` in the UI, archives and notices before signing.
2. Build one macOS universal2 app from a Python 3.12 universal2 runtime with universal2 Pillow and PySide6 wheels. Check the executable and every bundled Mach-O with `lipo`; run a packaged conversion on both Intel and Apple silicon Macs. Use macOS 14.4 or newer for the older Mac check.
3. Sign every nested Mac executable and the app with Developer ID and hardened runtime. Verify with `codesign --verify --deep --strict`. Notarize with Apple's `notarytool`, staple the ticket, then test the downloaded DMG on a fresh Mac.
4. Build the Windows x64 package on Windows. Sign the executable with a verified publisher identity. Run the downloaded ZIP on Windows 10 and 11 x64, including a real conversion and a check that Windows sees the publisher identity.
5. Verify the bundled GPLv3, LGPLv3, PSF, Pillow and PyInstaller license texts, matching source snapshot, dependency versions and the notices. Review all source files and icons for proper origin.
6. Compute SHA-256 after signing and final packaging. Publish the source, Mac DMG, Windows ZIP and hashes together in a tagged GitHub Release. Update the README download links to that release.

Signing credentials belong in the publisher's secret storage, never in Git history.
