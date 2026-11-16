# Qualcomm firehose programmers (bundled)

This directory holds **30 Qualcomm EDL / firehose programmer images** (`*.mbn`),
11,533,223 bytes (11.0 MiB) in total, so that Qualcomm EDL operations work
without the user having to locate and supply a programmer file.

## Origin and purpose

* **Origin:** the user's own existing TFT installation
  (`.../TFT/Data/bin/Loader/*.mbn` and `.../TFT/Data/bin/Loader/bin/*/*.mbn`).
  Files were copied byte-for-byte and renamed to the stable scheme
  `prog_<original-stem>.mbn` (e.g. `Loader6.mbn` → `prog_Loader6.mbn`).
* These are vendor Qualcomm programmer blobs. They are redistributed here for
  interoperability with devices the user owns or is authorized to service, in
  the same way the MediaTek BROM payloads in `../mtk/` are bundled.
* No activation, licensing, entitlement, or secret/credential logic is included.
  The images are unmodified vendor binaries; the only changes are the file
  names and the index metadata described below.

## Index (`index.json`)

`index.json` is an array with one object per programmer:

| field      | meaning |
|------------|---------|
| `file`     | file name in this directory |
| `socs`     | SoC tokens found in the image, sorted and unique |
| `firehose` | `true` when the image embeds the literal `firehose` string |
| `sha256`   | SHA-256 of the copied file |
| `size`     | size of the copied file in bytes |
| `origin`   | `generic` — a generic vendor programmer set, not tied to one firmware package |

* `socs` is derived mechanically from `strings -a`, matching
  `(MSM|SDM|SM|APQ)[0-9]{3,5}`. 24 of the 30 images contain at least one SoC
  token; the remaining 6 have an empty list (`[]`).
* `firehose` reflects only the presence of that literal string: 2 of the 30
  images contain it. Older 32-bit programmers frequently omit the string while
  still speaking the Saharan/firehose protocol, so a `false` value is **not** a
  claim that the image is unusable — it is an observation, not a guess.

## Selection

1. Put the device into EDL mode (Qualcomm 9008).
2. Read the SoC identifier from the device (Sahara serial-number / HWID
   response, or the user's explicit choice).
3. Look up `index.json` for programmers whose `socs` list contains that SoC.
4. Offer the matches in order and send the programmer over Sahara; if the
   device rejects it, fall through to the next candidate until Sahara accepts
   one.
5. If no indexed programmer matches, the caller may still try the remaining
   bundled images, and finally fall back to a user-supplied programmer file.

The index is advisory data. Nothing in this directory is executed at build
time; the images are only read when an EDL operation is requested.
