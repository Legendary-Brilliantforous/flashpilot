#!/usr/bin/env bash
# Build a self-contained .deb package for FlashPilot.
#
# The package bundles a full Python venv (with PyQt6 + segno) so it has no
# dependency on distro PyQt6 packages - only the matching CPython minor
# interpreter is required. A compiled Rust bridge, udev rules, desktop entry
# and icons complete the layout:
#
#   /usr/bin/flashpilot                     launcher
#   /usr/lib/flashpilot/flashpilot-bridge    compiled Rust bridge
#   /usr/lib/flashpilot/venv/               bundled Python venv (PyQt6 + segno)
#   /usr/share/flashpilot/                  python/, main.py, scripts/, root/,
#                                          pit/, docs/, LICENSE, README
#   /usr/lib/udev/rules.d/60-odin4.rules   Samsung USB rules (no sudo flashing)
#   /usr/share/applications/flashpilot.desktop
#   /usr/share/icons/hicolor/{256,512}x{256,512}/apps/flashpilot.png
#
# The proprietary odin4 binary is NOT shipped (legal); users fetch it via
# /usr/share/flashpilot/scripts/fetch-odin4.sh after install.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(.venv/bin/python -c "import tomllib,pathlib;print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])")"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
PYVER="$(/usr/bin/python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
PKG="flashpilot_${VERSION}_${ARCH}.deb"
STAGE="$ROOT/packaging/_stage"
DIST="$ROOT/dist"

echo "== Packaging FlashPilot ${VERSION} (${ARCH}) with bundled venv (cp${PYVER})"

# 1. Build the Rust bridge (release).
echo "-- cargo build --release"
cargo build --release --locked
[ -x target/release/flashpilot-bridge ] || { echo "bridge build failed"; exit 1; }

# 2. Clean staging dir.
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN"
mkdir -p "$STAGE/usr/bin"
mkdir -p "$STAGE/usr/lib/flashpilot"
mkdir -p "$STAGE/usr/share/flashpilot"
mkdir -p "$STAGE/usr/lib/udev/rules.d"
mkdir -p "$STAGE/usr/share/applications"
mkdir -p "$STAGE/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$STAGE/usr/share/icons/hicolor/512x512/apps"

# 3. Rust bridge.
install -m 0755 target/release/flashpilot-bridge "$STAGE/usr/lib/flashpilot/flashpilot-bridge"

# 4. Bundled venv (PyQt6 + segno + lz4). Reuses the repo's .venv when present
#    (the user's environment), otherwise builds a fresh one with the system
#    interpreter. Either way the CPython ABI must match the target's python3
#    minor, which is enforced in Depends.
SRC_VENV="$ROOT/.venv"
if [ -x "$SRC_VENV/bin/python" ] && [ -d "$SRC_VENV/lib/python$PYVER/site-packages/PyQt6" ]; then
    echo "-- reusing repo .venv (PyQt6 present)"
    cp -a "$SRC_VENV" "$STAGE/usr/lib/flashpilot/venv"
else
    echo "-- building fresh venv (pip install PyQt6 segno lz4)"
    /usr/bin/python3 -m venv "$STAGE/usr/lib/flashpilot/venv"
    PIP_DISABLE_PIP_VERSION_CHECK=1 "$STAGE/usr/lib/flashpilot/venv/bin/pip" install --quiet \
        --only-binary=:all: --no-input "PyQt6>=6.5" "segno>=1.6" "lz4>=4.0" "samloader>=0.2.0" "requests>=2.28.0" "tqdm>=4.0"
fi

V="$STAGE/usr/lib/flashpilot/venv"
SP="$V/lib/python$PYVER/site-packages"
QT6="$SP/PyQt6"

# 4a. Strip the venv: no pip/setuptools, no dev tools, no caches. The app only
#     imports stdlib + PyQt6 (plus lazy segno/lz4) at runtime.
rm -rf "$SP/pip" "$SP/setuptools"
rm -f "$V/bin/pip" "$V/bin/pip3" "$V/bin/activate" "$V/bin/activate.csh" \
      "$V/bin/activate.fish" "$V/bin/Activate.ps1"
rm -rf "$V/include"
# dev / runtime-unused packages.
rm -rf "$SP/pytest" "$SP/_pytest" "$SP/pluggy" "$SP/iniconfig"
rm -rf "$SP/Pygments" "$SP/pygments" "$SP/packaging"
rm -f "$V/bin/py.test" "$V/bin/pytest" "$V/bin/pygmentize" \
      "$V/bin/pip3.12"
rm -rf "$SP"/*.dist-info
find "$V" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$V" -name "*.pyc" -delete

# 4b. Remove Qt components the widgets-only app never imports (Qt QML / Quick,
#     Multimedia, PDF, Designer, DB drivers, ...). Keeps QtCore/Gui/Widgets/
#     Network/Svg/OpenGL + the platform plugins intact. Verified below by
#     constructing the real main window with QT_QPA_PLATFORM=offscreen.
rm -rf "$QT6/Qt6/qml" "$QT6/Qt6/translations" "$QT6/Qt6/qsci"
rm -rf "$QT6/bindings/QtDesigner" "$QT6/uic"
rm -f "$QT6"/QtQuick.abi3.so "$QT6"/QtQuickWidgets.abi3.so \
      "$QT6"/QtQml.abi3.so "$QT6"/QtQmlModels.abi3.so \
      "$QT6"/QtMultimedia.abi3.so "$QT6"/QtMultimediaWidgets.abi3.so \
      "$QT6"/QtPdf.abi3.so "$QT6"/QtPdfWidgets.abi3.so \
      "$QT6"/QtDesigner.abi3.so "$QT6"/QtTest.abi3.so \
      "$QT6"/QtSql.abi3.so "$QT6"/QtBluetooth.abi3.so "$QT6"/QtNfc.abi3.so \
      "$QT6"/QtPositioning.abi3.so "$QT6"/QtWebSockets.abi3.so \
      "$QT6"/QtWebChannel.abi3.so "$QT6"/QtSensors.abi3.so \
      "$QT6"/QtGamepad.abi3.so "$QT6"/QtRemoteObjects.abi3.so \
      "$QT6"/QtSerialPort.abi3.so "$QT6"/QtSerialBus.abi3.so \
      "$QT6"/QtTextToSpeech.abi3.so "$QT6"/QtCharts.abi3.so \
      "$QT6"/QtDataVisualization.abi3.so "$QT6"/QtSpatialAudio.abi3.so \
      "$QT6"/QtLocation.abi3.so "$QT6"/QtScxml.abi3.so
QLIB="$QT6/Qt6/lib"
rm -f "$QLIB"/libQt6Quick*.so* "$QLIB"/libQt6Qml*.so* \
      "$QLIB"/libQt6Quick3D*.so* "$QLIB"/libQt6ShaderTools*.so* \
      "$QLIB"/libQt6Multimedia*.so* "$QLIB"/libQt6Pdf*.so* \
      "$QLIB"/libQt6Designer*.so* "$QLIB"/libQt6Sql*.so* \
      "$QLIB"/libQt6Test*.so* "$QLIB"/libQt6Bluetooth*.so* \
      "$QLIB"/libQt6Nfc*.so* "$QLIB"/libQt6Positioning*.so* \
      "$QLIB"/libQt6Sensors*.so* "$QLIB"/libQt6Gamepad*.so* \
      "$QLIB"/libQt6RemoteObjects*.so* "$QLIB"/libQt6WebChannel*.so* \
      "$QLIB"/libQt6WebSockets*.so* "$QLIB"/libQt6SerialPort*.so* \
      "$QLIB"/libQt6SerialBus*.so* "$QLIB"/libQt6TextToSpeech*.so* \
      "$QLIB"/libQt6Charts*.so* "$QLIB"/libQt6DataVisualization*.so* \
      "$QLIB"/libQt6SpatialAudio*.so* "$QLIB"/libQt6Location*.so* \
      "$QLIB"/libQt6Scxml*.so* "$QLIB"/libQt6StateMachine*.so* \
      "$QLIB"/libQt6HttpServer*.so* "$QLIB"/libQt6OpenGLWidgets*.so* \
      "$QLIB"/libavcodec*.so* "$QLIB"/libavformat*.so* "$QLIB"/libavutil*.so* \
      "$QLIB"/libswscale*.so* "$QLIB"/libswresample*.so*
rm -rf "$QT6/Qt6/plugins/qmltooling" "$QT6/Qt6/plugins/sqldrivers" \
       "$QT6/Qt6/plugins/sceneparsers"
echo "   venv after strip: $(du -sh "$V" | cut -f1)"

# 5. Application (python + assets).
cp main.py "$STAGE/usr/share/flashpilot/"
cp -r python "$STAGE/usr/share/flashpilot/"
cp -r scripts "$STAGE/usr/share/flashpilot/"
# root/ is copied EXCEPT root/tools/odin4: the proprietary Samsung binary is
# never redistributed (see fetch-odin4.sh for the after-install download).
rsync -a --exclude 'tools/odin4' root/ "$STAGE/usr/share/flashpilot/root/"
cp -r pit "$STAGE/usr/share/flashpilot/"
cp -r docs "$STAGE/usr/share/flashpilot/"
cp LICENSE README.md DESCRIPTION.md "$STAGE/usr/share/flashpilot/"
find "$STAGE/usr/share/flashpilot" -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf "$STAGE/usr/share/flashpilot/tests"
find "$STAGE/usr/share/flashpilot" -type f ! -name "*.sh" -exec chmod 0644 {} +
find "$STAGE/usr/share/flashpilot" -type f -name "*.sh" -exec chmod 0755 {} +
find "$STAGE/usr/share/flashpilot" -type d -exec chmod 0755 {} +

# 6. Udev rules: Samsung (04e8), MediaTek (0e8d), Spreadtrum/UNISOC (1782)
#    -> plugdev users get device access without sudo.
install -m 0644 root/60-odin4.rules "$STAGE/usr/lib/udev/rules.d/60-odin4.rules"
install -m 0644 root/60-flashpilot-mtk.rules "$STAGE/usr/lib/udev/rules.d/60-flashpilot-mtk.rules"
install -m 0644 root/60-flashpilot-spd.rules "$STAGE/usr/lib/udev/rules.d/60-flashpilot-spd.rules"

# 7. Launcher.
install -m 0755 packaging/launcher.sh "$STAGE/usr/bin/flashpilot"

# 8. Desktop entry + icons.
install -m 0644 packaging/flashpilot.desktop "$STAGE/usr/share/applications/flashpilot.desktop"
install -m 0644 docs/logo_256.png "$STAGE/usr/share/icons/hicolor/256x256/apps/flashpilot.png"
install -m 0644 docs/logo_512.png "$STAGE/usr/share/icons/hicolor/512x512/apps/flashpilot.png"

# 9. Verify the stripped venv actually builds the real GUI (headless).
echo "-- smoke test: construct the real main window (QT_QPA_PLATFORM=offscreen)"
if ! QT_QPA_PLATFORM=offscreen "$V/bin/python" -c "
import sys
sys.path.insert(0, '$STAGE/usr/share/flashpilot')
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from python.gui.qt_app import FrpWindow
w = FrpWindow()
print('   FrpWindow constructed OK')
" 2>&1 | tail -3; then
    echo "ERROR: stripped venv fails to build the GUI" >&2
    rm -rf "$STAGE"
    exit 1
fi

# 10. Debian metadata. Depends pins the CPython minor the bundled wheels were
#     compiled for; everything else is self-contained.
PYTHON_DEP="python3 (>= ${PYVER}), python3 (<< ${PYVER%.*}.$(( ${PYVER#*.} + 1 )))"
sed -e "s/@VERSION@/${VERSION}/g" \
    -e "s/@ARCH@/${ARCH}/g" \
    -e "s/@PYTHON_DEP@/${PYTHON_DEP}/g" \
    packaging/debian/control > "$STAGE/DEBIAN/control"
install -m 0755 packaging/debian/postinst "$STAGE/DEBIAN/postinst"
install -m 0755 packaging/debian/prerm "$STAGE/DEBIAN/prerm"

# 11. Build the package.
mkdir -p "$DIST"
echo "-- dpkg-deb --build"
dpkg-deb --root-owner-group --build "$STAGE" "$DIST/$PKG"
rm -rf "$STAGE"

echo ""
echo "== Built: $DIST/$PKG  ($(du -h "$DIST/$PKG" | cut -f1))"
dpkg-deb --info "$DIST/$PKG" | grep -E "^( Package| Version| Architecture| Depends| Recommends| Installed-Size)"
echo ""
echo "Install with:  sudo dpkg -i $DIST/$PKG"
echo "Then run:      flashpilot"
echo "USB rules are applied automatically on install."
echo "Fetch odin4 (Samsung download mode): bash /usr/share/flashpilot/scripts/fetch-odin4.sh"
