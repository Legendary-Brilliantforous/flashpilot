# operations/frp/samsung_frp/
#
# Samsung FRP (Odin dışı) — gerçek uygulama şurada yaşar:
#   src/flows.rs kaydı  (frp_emergency, frp_browser, frp_qr_provision,
#                       frp_alliance — cihaz üzerinde yöntemler, yalnızca
#                       ADB gerektirir; `flow-run <key>` ile çalıştırılır)
#   mtk_brom_info / mtk_brom_backup satırları (Samsung MTK BROM FRP için
#                       A05/A06 Helio G85: BROM çip kimliği oku, frp / nvdata için
#                       BROM DA silme)
#   (kaldırılmış) python/core/flows/{frp,brom,oem_odin}.py (asla piyasaya sürülmedi;
#             Odin indirme modu yalnızca flaşlama içindir, FRP silme yolu yok)
#
# Cihaz bazlı notlar, gerçek tarif bulunduğunda operations/frp/devices/samsung/ içinde yer alır
# (örnek: A145F varyantı için ../devices/samsung/galaxy_a14_*.md dosyalarına bakın).
