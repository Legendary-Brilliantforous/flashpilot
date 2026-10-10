#!/bin/bash
# Build FlashPilotDPC.apk with the Android SDK command-line tools only
# (no Gradle): aapt2 -> javac -> d8 -> zipalign -> apksigner.
# Usage: ./build.sh   (reads ANDROID_SDK_ROOT or ~/.android-sdk)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_SDK_ROOT:-$HOME/.android-sdk}"
BT="$SDK/build-tools/34.0.0"
AJAR="$SDK/platforms/android-28/android.jar"
for f in "$BT/aapt2" "$BT/d8" "$BT/zipalign" "$BT/apksigner" "$AJAR"; do
    [ -e "$f" ] || { echo "missing: $f (install: platforms;android-28 + build-tools;34.0.0)"; exit 1; }
done
OUT="$HERE/build"
APK_OUT="${APK_OUT:-$HERE/../../mdm_qr/serve/flashpilot-dpc.apk}"
# Access email baked into the app (the gate in MainActivity).
# Override per build: FP_ACCESS_EMAIL=tech@shop.example ./build.sh
ACCESS_EMAIL="${FP_ACCESS_EMAIL:-flashpilot@local}"
rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/resflat" "$OUT/gen/org/flashpilot/dpc"
cat > "$OUT/gen/org/flashpilot/dpc/AccessConfig.java" <<EOF
package org.flashpilot.dpc;
final class AccessConfig {
    static final String ACCESS_EMAIL = "$ACCESS_EMAIL";
}
EOF
echo "access email: $ACCESS_EMAIL"
"$BT/aapt2" compile --dir "$HERE/res" -o "$OUT/resflat.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$AJAR" \
    --manifest "$HERE/AndroidManifest.xml" "$OUT/resflat.zip"
javac --release 8 -cp "$AJAR" -d "$OUT/classes" \
    "$HERE/src/org/flashpilot/dpc/"*.java "$OUT/gen/org/flashpilot/dpc/AccessConfig.java"
"$BT/d8" --output "$OUT" $(find "$OUT/classes" -name "*.class")
cp "$OUT/base.apk" "$OUT/unaligned.apk"
(cd "$OUT" && zip -q -j unaligned.apk classes.dex)
KS="$HERE/debug.keystore"
if [ ! -f "$KS" ]; then
    keytool -genkeypair -keystore "$KS" -alias androiddebugkey \
        -storepass android -keypass android -keyalg RSA -keysize 2048 \
        -validity 10950 -dname "CN=Android Debug,O=Android,C=US"
fi
"$BT/zipalign" -f 4 "$OUT/unaligned.apk" "$OUT/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass:android \
    --out "$APK_OUT" "$OUT/aligned.apk"
"$BT/apksigner" verify --print-certs "$APK_OUT" | head -3
echo "APK: $APK_OUT"
CERTDER="$OUT/cert.der"
"$BT/apksigner" verify --print-certs "$APK_OUT" >/dev/null
# Extract the signing cert (v1 RSA block) and print the provisioning checksum:
# SHA-256 of the DER cert, base64url, no padding.
python3 - "$APK_OUT" <<'EOF'
import sys, zipfile, hashlib, base64
z = zipfile.ZipFile(sys.argv[1])
rsa = [n for n in z.namelist() if n.startswith("META-INF/") and n.endswith((".RSA", ".DSA", ".EC"))]
der = z.read(rsa[0])
# PKCS#7 SignedData -> first certificate (works for apksigner v1 blocks too)
from subprocess import run
p = run(["openssl", "pkcs7", "-inform", "DER", "-in", "/dev/stdin",
         "-print_certs", "-outform", "DER"], input=der, capture_output=True)
cert = p.stdout if p.returncode == 0 else der
h = hashlib.sha256(cert).digest()
print("CERT_SHA256_HEX=" + h.hex())
print("CERT_CHECKSUM_B64URL=" + base64.urlsafe_b64encode(h).decode().rstrip("="))
EOF
