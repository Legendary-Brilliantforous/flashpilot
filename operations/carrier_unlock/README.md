# carrier_unlock/
Carrier / SIM lock (SIM-lock / NVDATA patch).

Sources: `python/core/flows/brom.py` flow_carrier_lock_*, `_mtk_simlock_patch`, `_mtk_analyze_nvdata`
Rust: mtkDA nvdata paths, qualcomm qcn imei repair (src/qualcomm/* + python/core/qcn.py)

```
carrier_unlock/
  apple/  — Apple carrier / SIM (device recipes, VID 05ac) — lock removes are under apple/ now
  mtk/    — MTK NVDATA patch (Android, future)
  qcom/   — QCOM QCN patch (Android, future)
```

Apple lock removes (enterprise_remote_lock, lost_mode_remove, passcode_lock_remove) moved to `apple/` as requested.
