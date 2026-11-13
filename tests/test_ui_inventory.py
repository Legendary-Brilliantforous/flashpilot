"""Page/button inventory parity guard.

Captured from the real window headless BEFORE the `pages/` + `widgets/`
architecture split, so the mechanical refactor cannot silently drop a page,
a section, a gated button or a page's action set.

This is an exact-equality golden test: when a later UI slice *intentionally*
changes the inventory (console dock, flow browser, icons…), regenerate
`tests/ui_inventory_golden.json` with `REGEN_INVENTORY=1` and review the diff
instead of loosening the assertions.

    REGEN_INVENTORY=1 QT_QPA_PLATFORM=offscreen \
        .venv/bin/python -m pytest tests/test_ui_inventory.py -q
"""
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

GOLDEN = Path(__file__).with_name("ui_inventory_golden.json")

# The real window is built through the shared harness in tests/conftest.py
# (`test_window`): it keeps a strong reference, joins the monitor poll thread,
# stops the periodic timers and tears the window down at module end.


def _walk(root):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget

    seen, out, stack = set(), [], [root]
    while stack:
        x = stack.pop()
        if id(x) in seen:
            continue
        seen.add(id(x))
        out.append(x)
        stack.extend(x.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly))
    return out


def _fingerprint(page):
    from PyQt6.QtWidgets import QPushButton

    widgets = _walk(page)
    acts = sorted(str(x.property("flow_act")) for x in widgets
                  if x.property("flow_act") is not None)
    btns = sorted(b.text() for b in widgets if isinstance(b, QPushButton))
    return {
        "widgets": len(widgets),
        "buttons": len(btns),
        "acts": acts,
        "btn_sha": hashlib.sha256(json.dumps(btns).encode()).hexdigest()[:16],
    }


def capture_inventory(w):
    """Fingerprint every registered page of the (already quiesced) window."""
    from python.core import core as _core
    from python.gui import devices as _dev

    rev = {idx: key for key, idx in w._section_index.items()}
    triples = sorted((j or "", m or "", c or "")
                     for _ref, j, m, c, _b in w._gated_buttons)
    return {
        "section_keys": sorted(w._section_index.keys()),
        "stack_count": w._stack.count(),
        "gated_count": len(w._gated_buttons),
        "gated_triples_sha256": hashlib.sha256(
            json.dumps(triples).encode()).hexdigest(),
        "gated_unique_triples": len(set(triples)),
        "core_flows": len(_core.FLOWS),
        "action_meta": len(_dev._ACTION_META),
        "pages": {rev[i]: _fingerprint(w._stack.widget(i))
                  for i in sorted(rev)},
    }


@pytest.fixture(scope="module")
def win(test_window):
    # Shared harness build + quiesce + module-teardown.
    return test_window()


def test_ui_inventory_parity(win):
    got = capture_inventory(win)
    if os.environ.get("REGEN_INVENTORY"):
        GOLDEN.write_text(json.dumps(got, indent=1) + "\n")
        pytest.skip(f"regenerated {GOLDEN.name}")

    assert GOLDEN.exists(), (
        f"missing {GOLDEN.name}; regenerate with --regen-inventory")
    want = json.loads(GOLDEN.read_text())

    assert got["section_keys"] == want["section_keys"], "section keys changed"
    assert got["stack_count"] == want["stack_count"], "page count changed"
    assert got["gated_count"] == want["gated_count"], "gated button count changed"
    assert got["gated_triples_sha256"] == want["gated_triples_sha256"], (
        "gated (job, mode, command) registry changed")
    assert got["gated_unique_triples"] == want["gated_unique_triples"]
    assert got["core_flows"] == want["core_flows"], "flow registry changed"
    assert got["action_meta"] == want["action_meta"], "_ACTION_META changed"

    for key in sorted(set(want["pages"]) | set(got["pages"])):
        assert key in got["pages"], f"page {key!r} disappeared"
        assert key in want["pages"], f"unexpected new page {key!r}"
        g, w_ = got["pages"][key], want["pages"][key]
        assert g["acts"] == w_["acts"], f"page {key!r} flow_act set changed"
        assert g["btn_sha"] == w_["btn_sha"], f"page {key!r} buttons changed"
        assert g["widgets"] == w_["widgets"], f"page {key!r} widget count changed"
