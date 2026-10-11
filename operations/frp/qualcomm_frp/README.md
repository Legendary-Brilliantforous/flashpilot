# operations/frp/qualcomm_frp/
#
# Qualcomm FRP engine — actual implementation lives in:
#   src/flows.rs registry  (edl_frp, edl_enable_adb, edl_detect,
#                           qcom_detect_info, qcom_verify — run via
#                           `flow-run <key>`)
#   src/qualcomm/          (Sahara + Firehose protocol, GPT, per-chip
#                           rawprogram XML parsing)
#   (retired) python/core/flows/frp.py (never shipped)
#
# Per-chip RAWPROGRAM XML patching lives in src/qualcomm/. EDL flows
# watch for 05c6:9008 (plus the 9006/900E diag family); the host-side
# flow hands the device to Rust via flashpilot-bridge.
