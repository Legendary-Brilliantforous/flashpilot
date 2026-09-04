"""Automated device health report — JSON + HTML + PDF.

Aggregates USB enumeration, PIT forensic health, FUS/modem info, battery
and network state into a single ``health_report.json``. HTML is rendered
via Jinja2-free string template so no new runtime dep; PDF is a
print-to-PDF via Qt QTextDocument when a QApplication exists, else falls
back to writing HTML alongside the JSON.

Uses the audited PIT engine: python/core/pit.py:509 pit_health — the same
verdict/summary the flash preflight blocks on (frp.py:752).
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List

from . import bridge, pit, pitstore


def _safe(call, default=""):
    try:
        return call()
    except Exception:
        return default


def _usb_snapshot() -> List[Dict[str, Any]]:
    try:
        devs = bridge.detect_all()
        return devs if isinstance(devs, list) else []
    except Exception:
        return []


def _pit_health_for(raw: bytes) -> Dict[str, Any]:
    try:
        return pit.pit_health(raw)
    except Exception as e:
        return {"verdict": "fail", "summary": f"PIT health error: {e}", "findings": [], "stats": {}}


def collect_health_report(
    pit_raw: bytes = b"",
    pit_path: str = "",
    device_filter: str = "",
    extra: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Build the unified health-report dict.

    pit_raw: raw PIT bytes if already dumped (e.g. from pit_contract)
    pit_path: path to PIT file to load if raw empty
    extra: caller-supplied map (model, battery, knox, qcn, etc.)
    """
    ts = time.time()
    usb = _usb_snapshot()

    # Resolve PIT: prefer explicit raw, else file, else latest cache
    pit_info: Dict[str, Any] = {}
    pit_from_cache = False
    raw = pit_raw
    if not raw and pit_path and os.path.isfile(pit_path):
        try:
            with open(pit_path, "rb") as f:
                raw = f.read()
        except Exception:
            raw = b""
    if not raw:
        # Fallback to latest cached PIT for any model — best-effort health preview
        try:
            for m in pitstore.stats().get("models", []):
                cached = pitstore.load_latest(m)
                if cached:
                    raw = cached
                    pit_from_cache = True
                    break
        except Exception:
            pass
    if raw:
        health = _pit_health_for(raw)
        sha = hashlib.sha256(raw).hexdigest()
        try:
            entries = pit.parse_pit(raw)
            part_count = len(entries)
        except Exception:
            entries = []
            part_count = 0
        pit_info = {
            "size": len(raw),
            "sha256": sha,
            "from_cache": pit_from_cache,
            "path": pit_path or ("cache" if pit_from_cache else ""),
            "health": health,
            "partition_count": part_count,
        }
        # Include first-lines of pit_report for human readers (Heimdall style)
        try:
            pit_info["report"] = pit.pit_report(raw).splitlines()[:80]
        except Exception:
            pit_info["report"] = []
        try:
            pit_info["map"] = pit.pit_map(raw).splitlines()[:60]
        except Exception:
            pit_info["map"] = []
    else:
        pit_info = {
            "size": 0,
            "sha256": "",
            "from_cache": False,
            "path": "",
            "health": {"verdict": "unknown", "summary": "No PIT available — connect device in Download Mode once", "findings": [], "stats": {}},
            "partition_count": 0,
            "report": [],
            "map": [],
        }

    # samsung / mtk / qcom / spd buckets (mirrors qt_app.py DeviceMonitor)
    samsung = [d for d in usb if d.get("is_samsung")]
    mtk = [d for d in usb if d.get("vid") == 0x0E8D]
    qcom = [d for d in usb if d.get("vid") == 0x05C6]
    spd = [d for d in usb if d.get("vid") == 0x1782]

    report: Dict[str, Any] = {
        "schema": "flashpilot.health_report/v1",
        "ts": ts,
        "ts_human": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
        "from": "FlashPilot 1.2.1-beta",
        "device_filter": device_filter,
        "usb": {
            "count": len(usb),
            "devices": usb,
            "buckets": {"samsung": len(samsung), "mtk": len(mtk), "qcom": len(qcom), "spd": len(spd)},
        },
        "pit": pit_info,
        "extra": extra or {},
    }
    return report


def render_html_report(report: Dict[str, Any]) -> str:
    """Render health report dict as self-contained HTML."""
    pit_h = report.get("pit", {}).get("health", {})
    verdict = pit_h.get("verdict", "unknown")
    color = {"ok": "#2dd4bf", "warn": "#fbbf24", "fail": "#fb7185"}.get(verdict, "#94a3b8")
    usb = report.get("usb", {})
    pit = report.get("pit", {})
    extra = report.get("extra", {})
    findings = pit_h.get("findings", [])

    def _escape(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    find_rows = ""
    for f in findings[:30]:
        find_rows += f"<tr><td>{_escape(f.get('code',''))}</td><td>{_escape(f.get('severity',''))}</td><td>{_escape(f.get('message',''))}</td></tr>\n"
    if not find_rows:
        find_rows = "<tr><td colspan=3 style='color:#6b7d94'>No findings — PIT passed forensic checklist.</td></tr>"

    usb_rows = ""
    for d in usb.get("devices", [])[:30]:
        usb_rows += f"<tr><td>{d.get('vid',0):04x}:{d.get('pid',0):04x}</td><td>{_escape(str(d.get('product','')))}</td><td>{d.get('bus','')}:{d.get('address','')}</td><td>{'yes' if d.get('is_samsung') else ''}</td></tr>\n"
    if not usb_rows:
        usb_rows = "<tr><td colspan=4 style='color:#6b7d94'>No USB devices — check cable/udev (root/setup-usb.sh).</td></tr>"

    extra_rows = ""
    if extra:
        for k, v in extra.items():
            extra_rows += f"<tr><td>{_escape(k)}</td><td>{_escape(str(v)[:120])}</td></tr>\n"
    else:
        extra_rows = "<tr><td colspan=2 style='color:#6b7d94'>No extra diagnostics supplied (battery/knox/qcn when available).</td></tr>"

    html = f"""<!doctype html><meta charset="utf-8">
<title>FlashPilot Device Health Report</title>
<style>
body{{font-family:Inter,system-ui,sans-serif;background:#04070c;color:#e7eef8;margin:0;padding:28px}}
.card{{background:#0d1622;border:1px solid #16233a;border-radius:12px;padding:18px;margin:16px 0}}
.badge{{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:800;letter-spacing:0.6px;background:{color};color:#04121a}}
h1{{color:#f1f5f9;margin:0 0 6px 0}} h2{{color:#a8bdd6;font-size:14px;letter-spacing:1px;text-transform:uppercase;margin:18px 0 10px 0}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #16233a;font-size:12px}}
th{{color:#6b7d94;text-transform:uppercase;letter-spacing:0.6px;font-size:10px}}
code{{background:#070d15;border:1px solid #16233a;border-radius:6px;padding:1px 5px;color:#7dd3fc}}
.small{{color:#6b7d94;font-size:11px}}
</style>
<h1>FlashPilot — Device Health Report</h1>
<div class="small">{_escape(report.get('ts_human',''))} · schema {report.get('schema','')}</div>
<div class="card">
  <span class="badge">PIT {verdict.upper()}</span>
  <span style="margin-left:10px;color:#e2e8f0">{_escape(pit_h.get('summary',''))}</span>
  <div class="small" style="margin-top:8px">PIT {pit.get('size',0)} bytes · sha256 <code>{pit.get('sha256','')[:16]}...</code> · from_cache={pit.get('from_cache',False)} · partitions={pit.get('partition_count',0)}</div>
</div>
<div class="card">
  <h2>Findings (forensic checklist)</h2>
  <table><tr><th>code</th><th>severity</th><th>message</th></tr>
  {find_rows}</table>
</div>
<div class="card">
  <h2>USB snapshot — {usb.get('count',0)} device(s)</h2>
  <div class="small">Buckets samsung={usb.get('buckets',{}).get('samsung',0)} mtk={usb.get('buckets',{}).get('mtk',0)} qcom={usb.get('buckets',{}).get('qcom',0)} spd={usb.get('buckets',{}).get('spd',0)}</div>
  <table><tr><th>VID:PID</th><th>product</th><th>bus:addr</th><th>samsung</th></tr>
  {usb_rows}</table>
</div>
<div class="card">
  <h2>Extra diagnostics</h2>
  <table><tr><th>key</th><th>value</th></tr>
  {extra_rows}</table>
</div>
<div class="small">Generated by FlashPilot 1.2.1-beta. Verify PIT verdict == ok before flashing. Warnings are non-fatal; fails block flashing.</div>
"""
    return html


def write_report(report: Dict[str, Any], out_dir: str, basename: str = "health_report") -> Dict[str, str]:
    """Write JSON + HTML (+ best-effort PDF via Qt if available) to out_dir.

    Returns {{"json": path, "html": path, "pdf": path|"" }}.
    """
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, f"{basename}.json")
    hpath = os.path.join(out_dir, f"{basename}.html")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    html = render_html_report(report)
    with open(hpath, "w", encoding="utf-8") as f:
        f.write(html)
    ppath = ""
    # Best-effort PDF via Qt if a QApplication already exists (GUI path)
    try:
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrinter

        doc = QTextDocument()
        doc.setHtml(html)
        ppath = os.path.join(out_dir, f"{basename}.pdf")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(ppath)
        doc.print(printer)
    except Exception:
        ppath = ""
    return {"json": jpath, "html": hpath, "pdf": ppath}
