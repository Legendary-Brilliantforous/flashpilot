# operations/frp/devices/

Cihaz bazlı FRP araştırma notları. **Model başına bir dosya** — dosya adı
`python/gui/supported_devices.json` içindeki model adıyla eşleşir
(sluggified: küçük harf, `/` ve boşluk → `_`).

Bu notlar, `supported_devices.json` içinde bulunmayan **araştırmaları** tutar —
canlı cihazda bulunan gerçek tarifler. JSON içeriğini (model, çip, motor, durum) burada tekrarlamayın; o girişe bağlantı verin ve yalnızca yeni bilgiyi koyun (döküm yolları, bölüm ofsetleri, gizli kodlar, BROM-BROM tarafından silinen bölüm adı vb.).

## Buraya hangi durumda dosya eklenir

Gerçek bir cihazdan yazılım döktünüz (veya FRP'yi başarıyla kaldırdınız) ve aynı cihazla çalışan bir sonraki kişiye lazım olacak bir şey öğrendiniz. Örnek: belirli bir `mmcblk0p4 = frp` bölüm adı, özel bir BROM pinout, devre dışı bırakılacak OEM-özel cihaz, genel akışı bozan derleme-parmak izi tuhaflığı.

## Dosya formatı

```markdown
# <Pazarlama Model Adı> — <Aile veya Kod Adı> — FRP
Çip: <çip>             (supported_devices.json çip alanıyla eşleşir)
Motor: <motor>         (mtk | spd | qcom | odin | apple-excluded)
VID: 0x<vid>           (USB satıcı kimliği)
Durum: <durum>         (researched | planned — JSON'dan kopyalanır)
Eylemler: <liste>      (JSON tarafından bu model için ilan edilen eylemler)

# Alan tarafından keşfedilen tarif (supported_devices.json içinde olmayan kısım)
FRP: <bölüm>          örn. "mmcblk0p4 = frp, anında BROM DA silme, combo gerekmez"
Döküm: <yol>          örn. "build/cache/dumps/<Model>_<Kod>/ (system 1.5G, product 1.6G, vendor 175M)"
Derleme: <parmak izi>  örn. "<vendor>/<model>:<android>:<build>/<incremental>"
Notlar: <serbest metin>  uyarılar, OEM-özel davranışlar, çalışan döküm bağlantıları
```

## Bu dizindeki gerçek örnekler

- `nokia/nokia_g20.md` — tam Nokia G20 tersine mühendislik notu: çip,
  döküm yolları, derleme parmak izi, çalışan kesin BROM tarifi.
- `itel/a14_a18.md` — Itel A14/A18 *#*#49#*#* gizli kodu (alanda test edilmiş).
- `samsung/galaxy_a14_sm_a145f_m_p_sm_a146b_p.md` — Helio G80 vs Exynos
  varyant uyarısı (çip / motor hangi varyantınıza göre değişir;
  varyant kodunu `*#1234#` üzerinden kontrol edin).
