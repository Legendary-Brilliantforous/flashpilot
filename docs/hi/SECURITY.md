Language switcher: [English](../../SECURITY.md) · [Français](../fr/SECURITY.md) · [Español](../es/SECURITY.md) · [Deutsch](../de/SECURITY.md) · [简体中文](../zh/SECURITY.md) · [Русский](../ru/SECURITY.md) · [Português](../pt/SECURITY.md) · [日本語](../ja/SECURITY.md) · [العربية](../ar/SECURITY.md) · **हिन्दी** · [Türkçe](../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# सुरक्षा नीति (Security Policy)

## समर्थित versions

Project pre-1.0 hai. Security fixes `main` branch par land karte hain aur, jab
ek ho, latest tagged release par bhi.

## Vulnerability report karna

Security problems ke liye please public issue mat kholo. Privately report karo:

- Email: **flashpilot@proton.me** (proton.me par ye address create karo → free account), ya
- Is repository par GitHub ka private vulnerability reporting form.

Please include karo:
- Affected command / flow aur version,
- Reproduce karne ke steps,
- Impact (e.g. arbitrary code execution, brick risk, data loss, credential exposure).

Hum reports ko 72 hours ke andar acknowledge karne ki koshish karte hain aur
disclosure coordinate karenge.

## Scope & expectations

Yeh tool intentionally low-level USB / bootloader operations perform karta hai.
Apni nature se yeh device wipe ya brick kar sakta hai. Yeh documented behaviour
hai, vulnerability nahi. Hum care karte hain:

- Exploits jo intended operation ke beyond untrusted code run karte hain,
- Safety confirmations / device checks bypass karna user harm ke liye,
- Repository mein proprietary blobs ya secrets ship karna,
- Kuch bhi jo user ka device data ya credentials leak kare.

Please sirf un devices par operate karo jo aapke hain ya jinhe service karne
ke liye aap authorized hain.
