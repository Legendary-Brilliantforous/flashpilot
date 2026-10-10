# operations/frp/devices/

Per-device FRP research notes. **One file per model** — the filename
matches the model name from `python/gui/supported_devices.json`
(sluggified: lowercase, `/` and spaces → `_`).

These notes hold **research that's not in `supported_devices.json`** —
real recipes discovered on a live device. Don't duplicate the JSON
content (model, chip, engine, status) here; link to the JSON entry
for that, and put only the new knowledge (dump paths, partition
offsets, secret codes, BROM-BROM-erased-partition name, etc.).

## When to add a file here

You just dumped firmware (or successfully removed FRP) on a real device
and learned something that the next person with the same device needs
to know. Example: a specific `mmcblk0p4 = frp` partition name, a
custom BROM pinout, an OEM-specific gadget to disable, a build-fingerprint
quirk that breaks the generic flow.

## File format

```markdown
# <Marketing Model Name> — <Family or Codename> — FRP
Chip: <chip>             (matches supported_devices.json chip field)
Engine: <engine>         (mtk | spd | qcom | odin | apple-excluded)
VID: 0x<vid>             (USB vendor id)
Status: <status>         (researched | planned — copy from the JSON)
Actions: <list>          (the actions the JSON advertises for this model)

# Field-discovered recipe (the part NOT in supported_devices.json)
FRP: <partition>         e.g. "mmcblk0p4 = frp, instant BROM DA erase, no combo"
Dump: <path>             e.g. "build/cache/dumps/<Model>_<Coden>/ (system 1.5G, product 1.6G, vendor 175M)"
Build: <fingerprint>     e.g. "<vendor>/<model>:<android>:<build>/<incremental>"
Notes: <free-form>        caveats, OEM-specific behaviors, links to the working dump
```

## Real examples in this directory

- `nokia/nokia_g20.md` — full Nokia G20 reverse-engineering note: chip,
  dump paths, build fingerprint, the exact BROM recipe that works.
- `itel/a14_a18.md` — Itel A14/A18 *#*#49#*#* secret code (field-tested).
- `samsung/galaxy_a14_sm_a145f_m_p_sm_a146b_p.md` — Helio G80 vs Exynos
  variant caveat (the chip / engine depends on which variant you have;
  check the variant code in `*#1234#`).
