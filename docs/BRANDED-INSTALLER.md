# Branded installer — included in stable 1.0.5

The 1.0.5 installer uses native Inno Setup dark styling with FDGCast charcoal,
orange accents, original logo artwork, plain-language welcome/upgrade copy,
readable license and setup pages, real file-phase progress, and a connection
guide link on the finish screen. Desktop shortcuts and launching Companion are
optional. No stream starts automatically.

The application identity, OBS module paths, configuration location, protected
credentials and uninstall behavior are preserved. This is the plugin + Companion
installer. Stable 1.0.5 includes the previously reviewed branding and the expanded
Stream Doctor / Windows streaming profile. Installing updates the existing
plugin + Companion installation; it does not create a separate OBS installation.

Build with Inno Setup 6.7.4 (pinned in CI). All installed license notices remain
included; the additional raw Markdown information page has been removed from the
wizard, while LICENSING.md remains installed. Native styles automatically defer
to Windows high-contrast accessibility settings.

The checked-in PNG is generated from packaging/installer/welcome.svg. To update
it, run scripts/build_installer_artwork.py with Inkscape available. Artwork uses
the existing FDGCast icon and repository-native vector geometry/text; it is not
a generated screenshot of the installer.

CI runs tests/installer/run.py on the actual Windows installer, capturing fresh
install and upgrade pages and verifying settings preservation. Screenshots are
uploaded as the installer-appearance artifact for visual review. Build-only
pywinauto/Pillow are installed after freezing Companion and are not shipped.
