# operations/frp/generic_frp/
#
# Generic FRP fallbacks (ADB-authorized, any device) — actual implementation
# lives in python/core/flows/frp.py. These flows are engine-agnostic and
# work on every Android phone once USB debugging is authorized.
#
# Flow keys registered in python/core/flows/frp.py:
#   flow_frp_clear_adb            — settings put + pm disable + pm clear (universal)
#   flow_adb_frp                  — mark setup complete / user_setup_complete / provisioned
#   flow_frp_browser              — on-device: open browser, chrome://settings/, remove account
#   flow_frp_emergency            — on-device: Emergency-call dialer path to Settings
#   flow_frp_settings             — on-device: open Settings via notification shade
#   flow_universal_frp_bypass     — combined method ladder
#
# Plus the recovery-side path:
#   flow_recovery                 — from python/core/flows/info.py
#   flow_factory_reset            — from python/core/flows/info.py
#
# For a specific device, prefer the engine-specific path
# (mtk_frp / qualcomm_frp / samsung_frp / unisoc_frp) over the generic
# one — the generic path requires the Google account to be removable
# via ADB, which is gated by the OEM's policy.
