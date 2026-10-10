# operations/frp/qualcomm_frp/
#
# Qualcomm FRP engine — actual implementation lives in:
#   python/core/flows/frp.py         (EDL / QFIL FRP erase flows)
#   src/qualcomm/                    (Sahara + Firehose protocol)
#   src/qualcomm/qcom_*              (per-chip rawprogram XML parsing, GPT)
#
# Flow keys registered:
#   flow_qualcomm_edl_frp   (05c6:9008 EDL — Sahara + Firehose erase)
#   flow_qualcomm_qfil_frp  (Qualcomm emergency-download + QFIL XML)
#   flow_qualcomm_qfil_frp  (alternate path for some Snapdragon QCOM devices)
#
# Per-chip RAWPROGRAM XML patching lives in src/qualcomm/. The host-side
# Python flow hands the device to Rust via flashpilot-bridge.
