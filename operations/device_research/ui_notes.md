# Cihaz merkezi — düzen kararları

FlashPilot'in GUI'nin cihazları ve eylemleri nasıl sunduğuna dair notlar ve neden
böyle düzenlendiği. Bu, daha önceki UI çalışmasını geçersiz kılar; o çalışma başka
bir ürünün yönetilen katmanını anlatır ve yeniden kullanılabilir kod taşımaz; yalnızca
az sayıda düzen öğrenisini kayıt eder.

Kaynak gerçekliği: `python/gui/devices.py`, `python/gui/nav.py`,
`python/gui/qt_app.py`, `python/gui/widgets/action_row.py`, `python/gui/theme.py`.

---

## 1. Uygulamanın şekli

```
┌──────────────┬──────────────────────────────────────────────────────┐
│ nav rail     │  section content                                     │
│  Samsung     │                                                      │
│  General     │   ┌ brand grid ─┬─ model grid ─┬─ model board ──┐   │
│  FUS         │   │  Xiaomi     │  Redmi 13C   │  ▸ Flash       │   │
│  MTK         │   │  Oppo       │  Note 12     │  ▸ Info        │   │
│  Qualcomm    │   │  SPD        │  …           │  ▸ FRP         │   │
│  SPD         │   └─────────────┴──────────────┴────────────────┘   │
│  Settings    │                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
```

Rail ana eksendir: `supported_devices.json`'dan inşa edilmiş OEM başına bir giriş
ve motor bölümü başına bir giriş. Menü ağacı değil — akışta hiçbir yerde modal
“işlem seç” diyaloğu yoktur.

## 2. Üç seviyeli drill-down

1. **Marka** — rail girişi ya da marka grid'inde bir kart. Kartlar veritabanından
   oluşturulur; hardcoded değildir; bucket eklemek UI değişikliği gerektirmez.
2. **Model** — kaydırılabilir model kartları grid'i. Her kart model adını ve alt
   etiket olarak mod/motor çipi (`mtk`, `qcom`, `spd`, `odin`, `apple`) ile yonga
   dizesini gösterir.
3. **Model board** — her eylem için tam genişlikte `ActionRow` kartı, ardından geri
   dönüş bağlantısı. İşletim sadece buradan başlatılır.

Board, geri dönüş yığınıyla erişilir; böylece işlem başarısız olsa bile kullanıcı
üzerinde olduğu modeli kaybetmez.

## 3. Rol kısıtlaması değil yetenek kısıtlaması

Board'un zorladığı kurallar:

- **Yanıp sönen ama gizlenmeyen.** Motorun desteklediği eylem, cihaz bağlı olmasa
  bile render edilir; gerekli taşıma görünene kadar devre dışı kalır. Desteklenmeyen
  eylemleri gizlemek testçileri uygulama bir özelliği kaybetmiş zannetmeye götürürdü.
- **Taşıma farkında.** `apply_applicability()` görünür satırları gezip canlı cihaz
  tarafından karşılanmayan `required_transports()` kümesiyle eşleşmeyen satırları
  devre dışı bırakır (ör. FRP ADB yolu `ADB` gerektirir, Odin flash `ODIN` gerektirir).
- **Durum farkında.** `status: "planned"` modeller tüm eylemleri devre dışı gösterir
  ve kart görünür şekilde işaretlenir; model hâlâ görünür kalır, çünkü araştırma
  listesi dürüst kalmalıdır.
- **Dürüst tooltip'lar.** Her satır çalışacak köprü komutunu taşır, örn.
  `qcom-detect`, `mtk-frp-brom`. Komut adı olmayan satır hata sayılır.

## 4. Görsel dil

- **Risk kenarı.** Her `ActionRow`, 3 piksel sol kenar çizer: silme/bozucu eylemler
  için `err`, diğerleri için `accent_hi`. Bu, flow browser içinde `MethodCard.set_risk`
  ile aynı dildir; böylece “kırmızı kenar = bu bir şey siler” tek bir kez öğrenilir.
- **Tek satırlık açıklamalar.** Satır açıklamaları kırpılır, asla sarılmaz; uzun akış
  etiketi panelden daha geniş olmasına neden olabilirdi.
- **Çipler.** Motor/mod çipleri `chip_blue` / `chip_text` token'larını kullanır; aynı
  çip bağlı cihaz çubuğunda da görünür, böylece “bu model MTK” ile “bu ekli cihaz
  BROM’da” etiketleri tutarlı kalır.
- **Odak halkası.** Satırlar `StrongFocus` ve Enter/Return/Space ile etkinleşir; böylece
  fare olmadan da kullanılabilir.
- **Yalnızca token'lar.** Sayfa kodunda literal renk yok; her şey `theme.C`'den gelir,
  tema değiştirmeleri de burada yapılır (`Slate Professional`, vb.).

## 5. Bağlı cihaz çubuğu

`buckets_from_rows()`, canlı USB satırlarını `samsung`, `mtk`, `spd`, `qcom`,
`adb`, `fastboot` bucket'larına gruplar; çubuk her bucket için sayıları ve
`mode_hint`'tan alınan mevcut mod etiketini gösterir. Bucket seçimi cihaz listesini
filtreler; bu şekilde beş telefon takılı bir çalışma masası okunabilir kalır.

`connected_rows()` önbelleğe alınır ve USB olaylarında geçersiz kılınır; her yeniden
çizimde poll edilmez.

## 6. Hub sayfaları

Marka drill-down'un dışında üç taşıma-öncelikli hub vardır:

| Hub | Amaç |
|---|---|
| `build_adb_hub_page` | düz ADB üzerinden mevcut eylemler (FRP, bilgi, reboot, shell) |
| `build_fastboot_hub_page` | fastboot eylemleri (boot image, vbmeta, slot sorguları) |
| `build_easylogin_hub_page` | birkaç taşıma zincirleme bir-tık akışlar |

Bunlar mevcut çünkü bazı işlemler model-öncelikli değil taşıma-önceliklidir: ADB
üzerinde bilinmeyen bir cihazı kullanırken önce marka kartı bulmak gerekmez.

## 7. Kasıtlı olmayan özellikler

Ticari yazılımlarda yaygın olan düzen karşısında alınan kararlar:

| İnşa edilmedi | Neden |
|---|---|
| Lisans/aktivasyon diyaloğu | Aktivasyon yok; sahte biri dürüst olmayan UI olur |
| Sunucu tarafı loader indirme | Her flash yerel, kullanıcı tarafından sağlanan firmware kullanır |
| İç içe “işlem seç” modalları | Model board seçim yeridir; modal bağlam kaybeder |
| Alt süreç substring eşleşmesinden status metni | Yapılandırılmış köprü çıktısı durum bilgisi üretir |
| Gizli devre dışı eylemler | Yanan ama devre dışı + tooltip ile değiştirildi |

## 8. Bilinen boşluklar

1. **Belirsiz bus için cihaz seçici yok.** Köprü tahmin etmez (`find_mtk_dev("auto")`),
   ama UI ayrıştırma yolu sunmaz.
2. **İzin hataları yokluk gibi görünür.** Eksik udev kuralı “cihaz yok” yerine
   “0e8d:0003 erişimi yok” olarak gösterilmelidir.
3. **Model araması lineerdir.** 719 model veritabanı için filtre kutusu daha da
   büyümeden gelmelidir.

Bunlar `usb_detection_gap.md` §4 ve `feature_logic_matrix.md` §9 içinde izlenir.
