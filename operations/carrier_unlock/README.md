# carrier_unlock/
Carrier / SIM lock (SIM-lock / NVDATA patch).

Sources: Rust flows (`src/flows.rs` registry, `flow-run` CLI): `carrier_lock_status`, `carrier_lock_mtk`, `qcn_imei_repair`, `imei_repair_mtk/spd`
Rust: mtkDA nvdata paths, qualcomm qcn imei repair (src/qualcomm/*)
(The old `python/core/qcn.py` engine module and `python/core/flows/brom.py` were retired/never shipped; the logic lives in the Rust flows.)

```
carrier_unlock/
  apple/  — Apple carrier / SIM (device recipes, VID 05ac) — lock removes are under apple/ now
  mtk/    — MTK NVDATA patch (Android, future)
  qcom/   — QCOM QCN patch (Android, future)
```

Apple lock removes (enterprise_remote_lock, lost_mode_remove, passcode_lock_remove) moved to `apple/` as requested.
