# Spark 10C — MDM
Chip: Unisoc UMS9230 (T606)
Engine: spd
MDM actions: mdm_unlock, mdm_diagnostics, kg_state_check
Notes: Spark 10C = KI5k codename, Unisoc UMS9230, Android 12 (API 31), TECNO/TECNO-KI5k. ADB researched live (serial 10545373A6137053). Per-model reverse-engineered flows: FRP/MDM/Screen-Lock (ADB + BROM) plus enable_adb and device_check. Flash routes to the SPD tab for FDL1/FDL2.
