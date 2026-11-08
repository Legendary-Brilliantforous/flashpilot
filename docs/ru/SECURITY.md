# Политика безопасности

Language switcher: [English](../../SECURITY.md) · [Français](../fr/SECURITY.md) · [Español](../es/SECURITY.md) · [Deutsch](../de/SECURITY.md) · [简体中文](../zh/SECURITY.md) · **Русский** · [Português](../pt/SECURITY.md) · [日本語](../ja/SECURITY.md) · [العربية](../ar/SECURITY.md) · [हिन्दी](../hi/SECURITY.md) · [Türkçe](../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Поддерживаемые версии

Проект в статусе pre-1.0. Исправления безопасности land'ят на ветку `main` и, если есть, на последний tagged release.

## Сообщение об уязвимости

Пожалуйста, **не открывайте публичный issue** по security-проблемам. Репортите приватно:

- Email: **flashpilot@proton.me** (создаётся на proton.me → free account), или
- Приватная форма отчётности об уязвимостях GitHub на этом репозитории.

Пожалуйста, включите:
- Затронутую команду / поток и версию,
- Шаги для воспроизведения,
- Impact (напр. arbitrary code execution, brick risk, data loss, credential exposure).

Мы aim to acknowledge reports в течение 72 часов и будем координировать disclosure.

## Scope & expectations

Этот инструмент намеренно выполняет низкоуровневые USB / bootloader операции. По своей природе он может стереть данные или превратить устройство в кирпич. Это documented behaviour, не уязвимость. Нам важны:

- Эксплойты, запускающие untrusted code сверх intended operation,
- Обход safety-confirmation'ов / device checks способом, вредящим пользователям,
- Поставка проприетарных blob'ов или секретов в репозитории,
- Всё, что leaks данные устройства или credential'ы пользователя.

Пожалуйста, работайте только с устройствами, которыми вы владеете или авторизованы обслуживать.