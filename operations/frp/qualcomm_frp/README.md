# operations/frp/qualcomm_frp/
#
# Qualcomm FRP motoru — gerçek uygulama şurada yaşar:
#   src/flows.rs kaydı  (edl_frp, edl_enable_adb, edl_detect,
#                       qcom_detect_info, qcom_verify — `flow-run <key>` ile
#                       çalıştırılır)
#   src/qualcomm/       (Sahara + Firehose protokolü, GPT, çip bazlı
#                       hamprogram XML ayrıştırma)
#   (kaldırılmış) python/core/flows/frp.py (asla piyasaya sürülmedi)
#
# Çip bazlı RAWPROGRAM XML yamalamaları src/qualcomm/ içinde yaşar. EDL akışları
# 05c6:9008 için izleme yapar (ve 9006/900E tanı ailesi de dahil); ana bilgisayar tarafı akış
# cihazı Rust'a `flashpilot-bridge` aracılığıyla teslim eder.
