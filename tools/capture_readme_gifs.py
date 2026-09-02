#!/usr/bin/env python3
"""Cattura le GIF autentiche usate dal README di Lab PRO.

Prerequisiti: server già attivo, Playwright Python e ImageMagick ``magick``.
Lo script salva e ripristina configurazione e stato RUN del banco. Usa un
profilo browser isolato, quindi non tocca workspace, lingua o camera utente.
Non esegue procedure lunghe: mostra i pannelli e le loro viste operative.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "media"

TOURS = {
    "01-workspace-overview.gif": ["chain", "education", "standards"],
    "02-source-and-tx.gif": ["bert", "tx"],
    "03-channel-and-optics.gif": ["channel", "com", "optical", "cmis"],
    "04-rx-and-dsp.gif": [
        "rxfe", "pd", "tia", "agc", "ctle", "adc", "timing", "eq",
        "decisions",
    ],
    "05-live-instruments.gif": [
        "scope", "jitter", "spectrum", "berlive", "feclive",
    ],
    "06-procedures-and-audit.gif": [
        "l2", "sweep", "jtol", "train", "anlt", "dr4proc",
        "instruments", "checks", "physics",
    ],
}


def _launch_chromium(playwright):
    """Usa il browser Playwright standard o un cache binary compatibile."""
    try:
        return playwright.chromium.launch(headless=True)
    except PlaywrightError:
        cache = Path.home() / "Library" / "Caches" / "ms-playwright"
        patterns = (
            "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
            "chromium-*/chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        )
        candidates = [p for pattern in patterns for p in cache.glob(pattern)]
        if not candidates:
            raise
        return playwright.chromium.launch(
            headless=True, executable_path=str(sorted(candidates)[-1]))


def _open_panels(page, base, panels):
    page.goto(f"{base}/?panels={','.join(panels)}",
              wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_function(
        "n => typeof S !== 'undefined' && !_buildingLayout && S.panels.length === n",
        arg=len(panels), timeout=30_000)
    page.wait_for_timeout(750)


def _activate(page, panel):
    page.evaluate(
        "type => activatePanel(S.panels.find(p => p.type === type))", panel)
    page.wait_for_function(
        "type => S.panels.find(p => !p.el.hidden)?.type === type",
        arg=panel, timeout=10_000)
    page.wait_for_timeout(700)


def _frame(page, directory, index, label):
    # Badge discreto: chiarisce il blocco anche quando il titolo della card è
    # fuori dal crop verticale dopo un cambio di layout.
    page.evaluate("""label => {
      let b=document.querySelector('#readme-tour-badge');
      if(!b){b=document.createElement('div');b.id='readme-tour-badge';
        b.style.cssText='position:fixed;right:14px;bottom:26px;z-index:9999;'+
        'padding:7px 11px;border:1px solid #4b6778;border-radius:6px;'+
        'background:rgba(4,10,14,.9);color:#d7e1e8;font:600 12px IBM Plex Sans';
        document.body.appendChild(b);} b.textContent=label;
    }""", label)
    path = directory / f"{index:02d}.png"
    page.screenshot(path=str(path), animations="disabled")
    return path


def _build_gif(frames, destination, magick):
    # Primo/ultimo frame duplicati: una breve pausa rende leggibile il tour.
    ordered = [frames[0], *frames, frames[-1]]
    subprocess.run([
        magick, "-delay", "135", "-loop", "0", *map(str, ordered),
        "-resize", "1000x625", "-colors", "112", "-fuzz", "1%",
        "-layers", "Optimize", str(destination),
    ], check=True)


def capture(base: str, out_dir: Path):
    magick = shutil.which("magick")
    if not magick:
        raise SystemExit("ImageMagick 'magick' non trovato")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )
        page = context.new_page()
        saved = page.request.get(f"{base}/api/config/export").json()
        state = page.request.get(f"{base}/api/state").json()
        was_running = bool(state["running"])

        try:
            page.goto(base, wait_until="domcontentloaded")
            page.evaluate("localStorage.setItem('labpro_lang','it')")
            page.request.post(
                f"{base}/api/preset",
                data={"name": "Link con margine — FEC al lavoro"})
            page.request.post(f"{base}/api/run", data={"running": True})
            page.wait_for_timeout(1_800)

            with tempfile.TemporaryDirectory(prefix="labpro-readme-") as tmp:
                temp_root = Path(tmp)
                for gif_name, panels in TOURS.items():
                    tour_dir = temp_root / gif_name.removesuffix(".gif")
                    tour_dir.mkdir()
                    _open_panels(page, base, panels)
                    frames = []
                    index = 0

                    for panel in panels:
                        # COM Annex 93A è applicabile al profilo KR1; le card
                        # ottiche tornano invece al preset FEC ottico.
                        if panel == "com":
                            page.request.post(f"{base}/api/preset", data={
                                "name": "IEEE 802.3ck — 100GBASE-KR1 · backplane elettrico"})
                            page.wait_for_timeout(1_000)
                        elif panel == "optical":
                            page.request.post(f"{base}/api/preset", data={
                                "name": "Link con margine — FEC al lavoro"})
                            page.wait_for_timeout(1_000)

                        _activate(page, panel)

                        if panel == "bert":
                            bert = (("source", "BERT · 1/4 · sorgente TX"),
                                    ("stress", "BERT · 2/4 · stress TX"),
                                    ("checker", "BERT · 3/4 · checker RX/FEC"),
                                    ("procedures", "BERT · 4/4 · procedure RX"))
                            for key, label in bert:
                                page.evaluate("""key => {const p=S.panels.find(x=>x.type==='bert');
                                  PANEL_DEFS.bert.showTab(p,key)}""", key)
                                page.wait_for_timeout(250)
                                frames.append(_frame(page, tour_dir, index, label))
                                index += 1
                            continue

                        if panel == "scope":
                            frames.append(_frame(
                                page, tour_dir, index, "Scope · DCA · EYE/MASK"))
                            index += 1
                            page.locator(
                                "section.panel:not([hidden]) [data-k='view']"
                            ).select_option("wave")
                            page.wait_for_timeout(850)
                            frames.append(_frame(
                                page, tour_dir, index, "Scope · DCA · WAVE"))
                            index += 1
                            continue

                        title = page.locator(
                            "section.panel:not([hidden]) .panel-head .t"
                        ).inner_text()
                        frames.append(_frame(page, tour_dir, index, title))
                        index += 1

                    destination = out_dir / gif_name
                    _build_gif(frames, destination, magick)
                    print(f"{destination.relative_to(ROOT)} · {len(frames)} frame")
        finally:
            page.request.post(f"{base}/api/config/import", data=saved)
            page.request.post(f"{base}/api/run", data={"running": was_running})
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8640")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    capture(args.base.rstrip("/"), args.out.resolve())


if __name__ == "__main__":
    main()
