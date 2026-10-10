# operations/frp/generic_frp/
#
# Generic FRP fallbacks (ADB-authorized, any device) — actual implementation
# lives in the Rust flow registry (src/flows.rs, `flow-run <key>`). These
# flows are engine-agnostic and work on every Android phone once USB
# debugging is authorized.
#
# Flow keys registered (verify with `flow-list`):
#   adb_frp                   — settings put + pm disable + pm clear (universal)
#   frp_browser               — on-device: open browser, chrome://settings/, remove account
#   frp_emergency             — on-device: Emergency-call dialer path to Settings
#   frp_settings              — on-device: open Settings via notification shade
#   frp_fake_login (+testdpc/+adp) — QR provisioning with a device-owner DPC,
#                               then FRP clear over the enabled ADB
#   factory_reset / recovery  — recovery-side wipe paths
#   (retired) python/core/flows/{frp,info}.py (never shipped)
#
# For a specific device, prefer the engine-specific path
# (mtk_* / edl_frp / qcom_* / samsung + frp_* / spd_*) over the generic
# one — the generic path requires the Google account to be removable
# via ADB, which is gated by the OEM's policy.
