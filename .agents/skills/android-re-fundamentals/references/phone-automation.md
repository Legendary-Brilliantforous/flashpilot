# Phone UI Automation

When you need to repeatedly drive a target app's UI — to trigger a request, walk a flow, or run a task on many devices — pick an automation approach by app type. Two families exist: **accessibility-tree** automation (reads the control tree; fast and precise for normal apps) and **vision-based** automation (screenshot + image match; works for games and custom-rendered UIs where the control tree is unavailable).

---

## Approaches at a glance

| Approach | Difficulty | Needs root | Analogy | Best for |
|----------|-----------|------------|---------|----------|
| adb `input` | low | no | hardcoded coordinates | simple scripts |
| **uiautomator2** | low | no | Playwright | recommended entry point |
| Appium | medium | no | Selenium | professional testing, cross-platform |
| AutoX.js | low | no | userscripts | on-device scripting |
| Airtest / OpenCV | low–med | no | vision automation | games, custom-rendered UIs |
| Frida | high | yes | debugger | RE / logic-level control |

Multi-device "control farm" stacks build on these: commercial agents, or open-source (Appium, STF/OpenSTF, scrcpy + scripts). The underlying mechanisms are adb commands, Android `AccessibilityService`, or root + injection.

---

## adb input (lowest level)

```bash
adb shell input tap 500 1000               # tap (x, y)
adb shell input swipe 500 1000 500 300     # swipe
adb shell input text "hello"               # type
adb shell input keyevent BACK              # key event
adb shell screencap /sdcard/screen.png     # screenshot
```

Coordinates are device-resolution specific.

---

## uiautomator2 (Python, recommended)

The most Playwright-like option; drives the device from the host over adb, no root.

```bash
pip install uiautomator2
```

```python
import uiautomator2 as u2

d = u2.connect()                 # connect to device
d.app_start("com.example.app")   # launch app

d(text="Login").click()
d(resourceId="com.example:id/username").set_text("admin")
d(className="android.widget.Button").click()

d.screenshot("screen.png")
```

---

## Appium (industry standard)

Cross-platform (Android + iOS), multi-language (Python/Java/JS).

```python
from appium import webdriver
driver = webdriver.Remote('http://localhost:4723', caps)
driver.find_element(By.ID, "com.example:id/btn").click()
```

---

## AutoX.js (on-device, no root)

Runs JavaScript directly on the phone via the accessibility service (open-source successor to Auto.js). Install the release APK, then enable: Settings → Accessibility → AutoX.js → On, and grant the floating-window permission.

---

## Vision-based automation

When the app renders its own UI (games, Canvas/OpenGL) the accessibility tree is empty, so use screenshot + image recognition + simulated input.

```
screenshot (adb screencap / scrcpy frames)
   -> image recognition (OpenCV template match / YOLO detection / OCR)
   -> decision logic (Python)
   -> simulated input (adb input tap/swipe)
```

| Tool | Use |
|------|-----|
| OpenCV | template matching (find a target image's position) |
| YOLO | object detection (complex scenes) |
| Tesseract / PaddleOCR | read on-screen numbers/text |
| Airtest | turnkey vision framework (below) |

### OpenCV + adb example

```python
import cv2, subprocess

subprocess.run(["adb", "shell", "screencap", "-p", "/sdcard/screen.png"])
subprocess.run(["adb", "pull", "/sdcard/screen.png", "screen.png"])

screen = cv2.imread("screen.png")
template = cv2.imread("target_button.png")
res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
_, max_val, _, max_loc = cv2.minMaxLoc(res)

if max_val > 0.8:
    h, w = template.shape[:2]
    cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
    subprocess.run(["adb", "shell", "input", "tap", str(cx), str(cy)])
```

### Airtest (recommended vision framework)

The most popular vision-automation framework (NetEase, OSS, Google-recommended), built for games; screenshot matching works out of the box.

```bash
pip install airtest      # or download AirtestIDE (bundles everything)
```

```python
from airtest.core.api import *

connect_device("Android:///")
touch(Template("attack_button.png"))                 # match + tap
swipe(Template("start.png"), Template("end.png"))
wait(Template("loading_done.png"), timeout=30)
if exists(Template("reward.png")):
    touch(Template("claim.png"))
snapshot("result.png")
```

**Poco** (Airtest's companion) reads the control tree of game engines (Unity/Cocos2dx), which is more precise than image matching when available:

```python
from poco.drivers.unity3d import UnityPoco
poco = UnityPoco()
poco("btn_attack").click()
poco("input_name").set_text("hello")
```

---

## Accessibility vs vision — trade-offs

| | Accessibility (uiautomator2 / AutoX.js) | Vision (Airtest / OpenCV) |
|---|----------------------------------------|---------------------------|
| Principle | reads control tree | screenshot + image match |
| Game support | no (can't see game canvas) | yes (only needs a screenshot) |
| Speed | fast | slower (capture + recognition latency) |
| Accuracy | precise (control IDs) | depends on image quality/threshold |
| Resolution handling | automatic | manual scaling needed |

### Notes

- **Resolution scaling** — coordinates differ per device; scale proportionally for vision approaches.
- **Anti-detection** — randomize action intervals; perfectly regular timing is detectable.
- **Performance** — `adb screencap` is ~1–2 s/frame; for high frequency use scrcpy frame capture.
- **Game anti-cheat** — some games detect simulated taps; account-ban risk exists.

---

## Installing self-built APKs (automation harness apps)

Any APK must be **signed** to install — a debug/self-signed signature is enough, no CA-issued cert required. Same-app updates must keep a consistent signature or you must uninstall the old version first. `adb install` is not subject to the "unknown sources" toggle.

```bash
adb install your_app.apk
adb install -r your_app.apk      # reinstall/overwrite

# manual signing without Android Studio:
keytool -genkey -v -keystore my-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias mykey
apksigner sign --ks my-key.jks your_app.apk
```

To allow installing from a file manager (not needed for `adb install`): Settings → Security → Install unknown apps → enable the chosen source.
