"""Guard rails for the public website in `website/`.

The site is a static Vite/React build. These checks are cheap file-level
assertions — they never invoke npm, so they run inside the existing pytest
job on any machine with the repository checked out.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"
SRC = WEBSITE / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.skipif(not WEBSITE.exists(), reason="website/ is not present")
class TestWebsiteLayout:
    def test_required_files_exist(self) -> None:
        expected = [
            WEBSITE / "package.json",
            WEBSITE / "package-lock.json",
            WEBSITE / "vite.config.ts",
            WEBSITE / "tsconfig.json",
            WEBSITE / "index.html",
            WEBSITE / "README.md",
            SRC / "main.tsx",
            SRC / "App.tsx",
            SRC / "styles" / "tokens.css",
            SRC / "styles" / "global.css",
            SRC / "data" / "site.ts",
            SRC / "data" / "protocols.ts",
        ]
        missing = [str(path.relative_to(ROOT)) for path in expected if not path.exists()]
        assert not missing, f"website is missing: {missing}"

    def test_build_scripts_are_wired(self) -> None:
        package = json.loads(_read(WEBSITE / "package.json"))
        scripts = package.get("scripts", {})
        assert "build" in scripts, "npm run build must exist for CI"
        assert "dev" in scripts
        for dep in ("react", "react-dom", "vite", "typescript", "@vitejs/plugin-react"):
            assert dep in package.get("dependencies", {}) or dep in package.get("devDependencies", {})

    def test_vite_output_is_relative(self) -> None:
        """`base: './'` keeps the build portable across Pages paths and domains."""
        config = _read(WEBSITE / "vite.config.ts")
        assert "base: './'" in config, "vite base must stay relative"

    def test_build_output_is_ignored(self) -> None:
        ignored = _read(ROOT / ".gitignore")
        assert "/website/node_modules/" in ignored
        assert "/website/dist/" in ignored


@pytest.mark.skipif(not WEBSITE.exists(), reason="website/ is not present")
class TestWebsiteContent:
    def test_every_referenced_image_exists(self) -> None:
        data = _read(SRC / "data" / "site.ts")
        referenced = set(re.findall(r"'(img/[^']+)'", data))
        assert referenced, "the site should reference its screenshots"
        for relative in referenced:
            assert (WEBSITE / "public" / relative).exists(), f"missing image {relative}"

    def test_screenshots_match_the_repo_copies(self) -> None:
        """The site must show the same screenshots the repository documents."""
        data = _read(SRC / "data" / "site.ts")
        for name in ("samsung", "mtk", "spd", "battery"):
            source = ROOT / "docs" / f"{name}.png"
            copy = WEBSITE / "public" / "img" / f"{name}.png"
            assert source.exists(), f"docs/{name}.png is missing"
            assert copy.exists(), f"website copy of {name}.png is missing"
            assert source.read_bytes() == copy.read_bytes(), f"{name}.png is stale"

    def test_site_does_not_claim_a_version(self) -> None:
        """The application version is not settled; the site must not advertise one."""
        data = _read(SRC / "data" / "site.ts")
        assert not re.search(r"\b\d+\.\d+\.\d+\b", data), "the site must not pin an app version"

    def test_protocol_codes_are_grounded_in_the_rust_core(self) -> None:
        """Every quoted packet code must exist in the Rust source it points at."""
        protocols = _read(SRC / "data" / "protocols.ts")
        for code in ("0x64 / 0x00", "0x65 / 0x01", "0x66 / 0x00", "0x67"):
            assert code in protocols, f"Odin code {code} disappeared from the panel"
        for code in ("a0 0a 50 05", "0xfc", "0xd0 and 0xd1", "0xd5"):
            assert code in protocols, f"MTK code {code} disappeared from the panel"
        for code in ("0x01 / 0x02", "0x0b", "0x11"):
            assert code in protocols, f"Sahara code {code} disappeared from the panel"
        for code in ("0x00 then 0x80 / 0x81", "0x07", "0x1a", "0x17"):
            assert code in protocols, f"BSL code {code} disappeared from the panel"

        # The codes must still be present in the Rust core they were taken from.
        rust = ROOT / "src"
        assert "CTRL_SESSION" in _read(rust / "sam_download.rs")
        assert "SYNC_BYTES" in _read(rust / "mtk.rs")
        assert "Hello = 0x1" in _read(rust / "qualcomm" / "sahara.rs")
        assert "BSL_CMD_CONNECT" in _read(rust / "spd.rs")

    def test_theme_tokens_match_the_app(self) -> None:
        """The site palette is the app palette — keep them in step."""
        theme = _read(ROOT / "python" / "gui" / "theme.py")
        tokens = _read(SRC / "styles" / "tokens.css")
        for token in ("bg", "panel", "card", "inset", "border", "text", "dim", "mute", "accent"):
            match = re.search(rf'"{token}":\s*"(#[0-9a-fA-F]+)"', theme)
            assert match, f"theme.py has no {token} token"
            assert match.group(1) in tokens, f"{token} {match.group(1)} is missing from the site"

    def test_crawler_files_are_shipped(self) -> None:
        robots = WEBSITE / "public" / "robots.txt"
        sitemap = WEBSITE / "public" / "sitemap.xml"
        assert robots.exists(), "robots.txt must ship with the site"
        assert sitemap.exists(), "sitemap.xml must ship with the site"
        text = _read(robots)
        assert "User-agent: *" in text
        assert "Allow: /" in text
        assert "Sitemap:" in text

    def test_page_carries_search_metadata(self) -> None:
        html = _read(WEBSITE / "index.html")
        assert '<meta charset="UTF-8" />' in html
        assert 'name="viewport"' in html
        assert 'name="description"' in html
        assert 'property="og:title"' in html
        assert 'property="og:image"' in html
        assert "<title>" in html


@pytest.mark.skipif(not WEBSITE.exists(), reason="website/ is not present")
class TestPagesWorkflow:
    def test_workflow_exists_and_publishes_the_build(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "pages.yml"
        assert workflow.exists(), "the Pages workflow is missing"
        text = _read(workflow)
        assert "actions/upload-pages-artifact" in text
        assert "actions/deploy-pages" in text
        assert "website/dist" in text
        assert "permissions:" in text and "pages: write" in text
