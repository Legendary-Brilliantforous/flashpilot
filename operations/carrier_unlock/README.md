# carrier_unlock/
Taşıyıcı / SIM kilidi (SIM-kilit / NVDATA yaması).

Kaynaklar: Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI): `carrier_lock_status`, `carrier_lock_mtk`, `qcn_imei_repair`, `imei_repair_mtk/spd`
Rust: mtkDA nvdata yolları, qualcomm qcn imei onarımı (src/qualcomm/*)
(Eski `python/core/qcn.py` motor modülü ve `python/core/flows/brom.py` emekliye ayrıldı/asla teslim edilmedi; mantık Rust akışlarında yaşıyor.)

```
carrier_unlock/
  apple/  — Apple taşıyıcı / SIM (cihaz tarifleri, VID 05ac) — kilit kaldırmalar artık apple/ altında
  mtk/    — MTK NVDATA yaması (Android, gelecek)
  qcom/   — QCOM QCN yaması (Android, gelecek)
```

Apple kilit kaldırmalar (enterprise_remote_lock, lost_mode_remove, passcode_lock_remove) istenen şekilde `apple/` içine taşındı.
