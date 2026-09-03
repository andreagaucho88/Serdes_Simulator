#!/usr/bin/env python3
"""Capture the polished, authentic Lab PRO GIFs embedded in the README.

Prerequisites: a running server, Playwright for Python, and ImageMagick
``magick``. Every application frame is captured from the real bench. Branded
chapter cards and explanatory overlays are injected only for the recording;
they never become part of the application itself.

The script saves and restores the bench configuration and RUN state. It uses
an isolated browser profile, so it does not touch the user's workspace,
language, or camera. It does not launch long procedures.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "media"
CAPTURE_SIZE = (1440, 810)
GIF_SIZE = "1000x563"


@dataclass(frozen=True)
class Step:
    panel: str
    title: str
    detail: str
    action: str = ""


@dataclass(frozen=True)
class Tour:
    eyebrow: str
    title: str
    summary: str
    steps: tuple[Step, ...]


TOURS = {
    "00-instruments-hero.gif": Tour(
        "LIVE INSTRUMENT STORY",
        "From eye opening to corrected codewords",
        "One running record. Four views. A complete measurement narrative.",
        (
            Step("scope", "01 · Reveal the PAM4 eye", "Color-grade persistence exposes level separation, crossings, and mask margin.", "scope_eye"),
            Step("scope", "02 · Inspect the waveform", "The same DCA channel unfolds into a synchronized oscilloscope record.", "scope_wave"),
            Step("berlive", "03 · Accumulate confidence", "Live BER combines instant errors, cumulative evidence, GMI, and a 95% interval."),
            Step("feclive", "04 · See FEC doing the work", "KP4/KR4 codewords separate clean, corrected, lost, and post-FEC outcomes.", "live_settle"),
        ),
    ),
    "01-workspace-overview.gif": Tour(
        "NAVIGABLE BENCH",
        "Follow one signal across the complete link",
        "The workspace connects physical blocks, learning material, and declared standards.",
        (
            Step("chain", "Signal chain", "Click any block to open its instrument; DCA markers identify acquired reference planes."),
            Step("education", "Academy", "Bilingual lessons connect controls and plots to the physics behind them."),
            Step("standards", "Standards map", "Profiles state what is implemented, approximated, or intentionally out of scope."),
        ),
    ),
    "02-source-and-tx.gif": Tour(
        "SOURCE → TRANSMITTER",
        "Build the stimulus before it enters the channel",
        "Generator, stress, checker, and analog transmitter remain tied to one datapath.",
        (
            Step("bert", "BERT · PPG source", "Choose PRBS, SSPRQ, or Ethernet stimulus and configure the transmitted pattern.", "bert_source"),
            Step("bert", "BERT · TX stress", "Inject RJ, PJ, DCD, SSC, noise, and controlled error events.", "bert_stress"),
            Step("bert", "BERT · Error checker", "Compare pre-FEC and post-FEC observations against the known transmitted bits.", "bert_checker"),
            Step("bert", "BERT · RX procedures", "Run sensitivity, overload, and stressed-receiver workflows from the same instrument.", "bert_procedures"),
            Step("tx", "TX · FIR, DAC, and driver", "Observe tap shaping, quantization, bandwidth, and differential output together."),
        ),
    ),
    "03-channel-and-optics.gif": Tour(
        "TRANSMISSION MEDIUM",
        "Move from insertion loss to optical power",
        "Analytical and measured channels feed the same electrical or electro-optical link.",
        (
            Step("channel", "Channel", "Inspect loss, group delay, reflections, and imported Touchstone behavior."),
            Step("com", "COM Annex 93A", "Evaluate channel operating margin with explicit KR1 assumptions and reference planes.", "kr1_preset"),
            Step("optical", "Optical path", "Compare modulator, fiber, extinction, chirp, dispersion, RIN, and MPI penalties.", "optical_preset"),
            Step("cmis", "CMIS-lite", "Relate module telemetry, alarms, and thresholds to the active simulated record."),
        ),
    ),
    "04-rx-and-dsp.gif": Tour(
        "RECEIVER → DECISIONS",
        "Watch margin move through the receive chain",
        "Every stage consumes the output of the previous stage—these are not disconnected plots.",
        (
            Step("rxfe", "RX front end", "Set receiver bandwidth, noise, sensitivity, overload, and optical/electrical mode."),
            Step("pd", "Photodiode", "Convert received optical power into signal current with declared responsivity and noise."),
            Step("tia", "TIA / AFE", "Apply transimpedance, bandwidth, and analog noise before gain control."),
            Step("agc", "Automatic gain control", "Track target swing, gain limits, settling, and clipping risk."),
            Step("adc", "Interleaved ADC", "Expose sampling, ENOB, quantization, interleave mismatch, and aperture jitter."),
            Step("timing", "CDR and timing recovery", "Inspect lock, phase, frequency offset, and timing-error behavior."),
            Step("eq", "FSE and DFE equalization", "See feed-forward and decision-feedback taps recover eye margin."),
            Step("decisions", "Slicer and decisions", "Close the path with thresholds, symbol decisions, GMI, BER, and FEC input."),
        ),
    ),
    "05-live-instruments.gif": Tour(
        "COHERENT LIVE ACQUISITION",
        "Different instruments, one versioned record",
        "Plots update together while counters preserve the evidence accumulated so far.",
        (
            Step("scope", "DCA · eye and mask", "Color-grade persistence and eye metrics share a declared measurement plane.", "scope_eye"),
            Step("scope", "DCA · waveform", "Switch modes without changing the underlying acquired record.", "scope_wave"),
            Step("jitter", "Jitter · TIE", "Separate measured TIE, dual-Dirac tails, J2/J9, bathtub, and spectral content."),
            Step("spectrum", "Spectrum analyzer", "Compare the measured spectrum with the configured reference bandwidth."),
            Step("berlive", "Live BER", "Watch cumulative BER and confidence evolve record by record."),
            Step("feclive", "Live FEC", "Watch the symbol-error histogram approach the decoder correction boundary.", "live_settle"),
        ),
    ),
    "06-procedures-and-audit.gif": Tour(
        "PROCEDURES → EVIDENCE",
        "Turn measurements into an inspectable workflow",
        "Training, qualification, and audits retain both the result and how it was produced.",
        (
            Step("l2", "Traffic PHY · L1 · L2", "Close accounting identities across frames, PCS blocks, the serial PHY, and FEC."),
            Step("sweep", "Parameter sweep", "Map sensitivity to a chosen control without losing the baseline configuration."),
            Step("jtol", "JTOL-lite", "Search the injected-jitter boundary with an explicit model-level verdict."),
            Step("train", "Link training", "Follow coefficient requests, tap updates, convergence, and receiver quality."),
            Step("anlt", "Auto-negotiation and training", "Inspect advertised abilities, selected technology, and training state."),
            Step("dr4proc", "DR4 stress procedure", "Evaluate the eight-case stress space and golden-waveform correlation."),
            Step("instruments", "Instrument alignment", "Audit DCA, BERT, and traffic capabilities against declared references."),
            Step("checks", "Signal ledger", "Trace units, reference planes, and checkpoints throughout the datapath."),
            Step("physics", "Physics audit", "Verify paired invariants and expose any broken conservation relationship."),
        ),
    ),
}


def _launch_chromium(playwright):
    """Use Playwright's browser or a compatible binary from its cache."""
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
    unique_panels = list(dict.fromkeys(panels))
    page.goto(f"{base}/?panels={','.join(unique_panels)}",
              wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_function(
        "n => typeof S !== 'undefined' && !_buildingLayout && S.panels.length === n",
        arg=len(unique_panels), timeout=30_000)
    page.wait_for_timeout(850)
    _install_recording_skin(page)


def _install_recording_skin(page):
    page.evaluate("""() => {
      if (document.querySelector('#readme-tour-style')) return;
      const style=document.createElement('style');
      style.id='readme-tour-style';
      style.textContent=`
        #topbar,#statusbar{display:none!important}
        body{background:#050a0f!important}
        #workspace-tabs{margin-top:92px!important;border-top:0!important}
        #workbench{scrollbar-width:none;padding:12px 16px 20px!important}
        #workbench::-webkit-scrollbar{display:none}
        #workbench>.panel.active{
          border-color:#34586b!important;
          box-shadow:0 0 0 1px rgba(58,207,239,.10),0 18px 46px rgba(0,0,0,.38)!important
        }
        #readme-tour-hud{
          position:fixed;inset:0 0 auto 0;height:92px;z-index:9998;
          box-sizing:border-box;display:grid;grid-template-columns:190px 1fr 170px;
          align-items:center;gap:22px;padding:13px 22px;
          color:#e9f4f8;border-bottom:1px solid rgba(70,190,221,.28);
          background:linear-gradient(100deg,rgba(5,14,20,.985),rgba(8,28,39,.985) 52%,rgba(8,17,25,.985));
          box-shadow:0 12px 36px rgba(0,0,0,.42);font-family:'IBM Plex Sans',system-ui,sans-serif
        }
        .rt-brand{display:flex;align-items:center;gap:10px;font:700 13px 'IBM Plex Mono',monospace;letter-spacing:.07em}
        .rt-mark{width:31px;height:31px;border:1px solid #3acfee;border-radius:8px;display:grid;place-items:center;
          color:#3acfee;background:rgba(58,207,239,.08);box-shadow:inset 0 0 18px rgba(58,207,239,.08)}
        .rt-copy{min-width:0;border-left:2px solid #3acfee;padding-left:17px}
        .rt-title{font:700 22px 'IBM Plex Sans',system-ui,sans-serif;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .rt-detail{margin-top:4px;color:#9fb5c1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .rt-progress{text-align:right}.rt-count{color:#8fa5b1;font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.12em}
        .rt-dots{display:flex;justify-content:flex-end;gap:6px;margin-top:9px}
        .rt-dot{width:18px;height:3px;border-radius:4px;background:#263945}.rt-dot.done{background:#3acfee}.rt-dot.now{background:#f2c94c;box-shadow:0 0 9px rgba(242,201,76,.55)}
        #readme-tour-card{
          position:fixed;inset:0;z-index:99999;display:grid;place-items:center;overflow:hidden;
          color:#eef8fb;background:
            radial-gradient(circle at 18% 18%,rgba(43,205,238,.17),transparent 34%),
            radial-gradient(circle at 82% 76%,rgba(101,87,255,.16),transparent 38%),
            linear-gradient(135deg,#05090e,#071722 58%,#08111a);
          font-family:'IBM Plex Sans',system-ui,sans-serif
        }
        #readme-tour-card:before{content:'';position:absolute;inset:-40%;opacity:.22;transform:rotate(-8deg);
          background:repeating-linear-gradient(90deg,transparent 0 79px,rgba(71,194,222,.13) 80px 81px),
                     repeating-linear-gradient(0deg,transparent 0 79px,rgba(71,194,222,.10) 80px 81px)}
        .rt-card-inner{position:relative;width:min(940px,78vw);padding:58px 64px;border:1px solid rgba(74,197,226,.28);
          border-radius:18px;background:rgba(6,15,22,.78);box-shadow:0 28px 90px rgba(0,0,0,.5),inset 0 0 60px rgba(38,173,211,.04)}
        .rt-card-eyebrow{color:#4ad4f2;font:700 13px 'IBM Plex Mono',monospace;letter-spacing:.22em}
        .rt-card-title{margin-top:18px;font-size:46px;line-height:1.08;font-weight:720;letter-spacing:-.035em;max-width:900px}
        .rt-card-summary{margin-top:20px;color:#aac0ca;font-size:19px;line-height:1.5;max-width:800px}
        .rt-card-rule{width:88px;height:4px;margin-top:34px;border-radius:4px;background:linear-gradient(90deg,#3acfee,#7d6cff)}
        .rt-card-footer{display:flex;justify-content:space-between;margin-top:45px;color:#718a97;font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.12em}
      `;
      document.head.appendChild(style);
      const hud=document.createElement('div');hud.id='readme-tour-hud';hud.innerHTML=`
        <div class="rt-brand"><span class="rt-mark">S</span><span>LAB PRO</span></div>
        <div class="rt-copy"><div class="rt-title"></div><div class="rt-detail"></div></div>
        <div class="rt-progress"><div class="rt-count"></div><div class="rt-dots"></div></div>`;
      document.body.appendChild(hud);
    }""")


def _show_intro(page, tour: Tour, chapter: int, total: int):
    page.evaluate("""d => {
      document.querySelector('#readme-tour-card')?.remove();
      const card=document.createElement('div');card.id='readme-tour-card';
      const inner=document.createElement('div');inner.className='rt-card-inner';
      for(const [cls,text] of [
        ['rt-card-eyebrow',d.eyebrow],['rt-card-title',d.title],
        ['rt-card-summary',d.summary]]){
          const el=document.createElement('div');el.className=cls;el.textContent=text;inner.appendChild(el);
      }
      const rule=document.createElement('div');rule.className='rt-card-rule';inner.appendChild(rule);
      const footer=document.createElement('div');footer.className='rt-card-footer';
      const left=document.createElement('span');left.textContent='SERDES OPTICAL LAB PRO';
      const right=document.createElement('span');right.textContent=`CHAPTER ${String(d.chapter).padStart(2,'0')} / ${String(d.total).padStart(2,'0')}`;
      footer.append(left,right);inner.appendChild(footer);card.appendChild(inner);document.body.appendChild(card);
    }""", {
        "eyebrow": tour.eyebrow,
        "title": tour.title,
        "summary": tour.summary,
        "chapter": chapter,
        "total": total,
    })


def _hide_intro(page):
    page.evaluate("document.querySelector('#readme-tour-card')?.remove()")


def _activate(page, panel):
    page.evaluate(
        "type => activatePanel(S.panels.find(p => p.type === type))", panel)
    page.wait_for_function(
        "type => S.panels.find(p => !p.el.hidden)?.type === type",
        arg=panel, timeout=10_000)
    page.evaluate("document.querySelector('#workbench').scrollTop=0")
    page.wait_for_timeout(550)


def _select(page, key: str, value: str):
    locator = page.locator(f"section.panel:not([hidden]) [data-k='{key}']")
    locator.select_option(value)
    locator.dispatch_event("change")


def _check(page, key: str, checked: bool):
    locator = page.locator(f"section.panel:not([hidden]) [data-k='{key}']")
    locator.set_checked(checked)
    locator.dispatch_event("change")


def _prepare_step(page, base: str, step: Step):
    if step.action == "kr1_preset":
        page.request.post(f"{base}/api/preset", data={
            "name": "IEEE 802.3ck — 100GBASE-KR1 · backplane elettrico"})
        page.wait_for_timeout(900)
    elif step.action == "optical_preset":
        page.request.post(f"{base}/api/preset", data={
            "name": "Link con margine — FEC al lavoro"})
        page.wait_for_timeout(900)

    _activate(page, step.panel)

    if step.action.startswith("bert_"):
        key = step.action.removeprefix("bert_")
        page.evaluate("""key => {
          const p=S.panels.find(x=>x.type==='bert');PANEL_DEFS.bert.showTab(p,key)
        }""", key)
        page.wait_for_timeout(500)
    elif step.action == "scope_eye":
        _select(page, "view", "eye")
        _check(page, "mask", True)
        page.wait_for_timeout(1_100)
    elif step.action == "scope_wave":
        _select(page, "view", "wave")
        page.wait_for_timeout(1_100)
    elif step.action == "live_settle":
        page.wait_for_timeout(1_600)


def _update_hud(page, step: Step, index: int, total: int):
    page.evaluate("""d => {
      const hud=document.querySelector('#readme-tour-hud');
      hud.querySelector('.rt-title').textContent=d.title;
      hud.querySelector('.rt-detail').textContent=d.detail;
      hud.querySelector('.rt-count').textContent=`LIVE VIEW ${String(d.index).padStart(2,'0')} / ${String(d.total).padStart(2,'0')}`;
      const dots=hud.querySelector('.rt-dots');dots.innerHTML='';
      for(let i=1;i<=d.total;i++){
        const dot=document.createElement('span');dot.className='rt-dot'+(i<d.index?' done':i===d.index?' now':'');dots.appendChild(dot);
      }
    }""", {
        "title": step.title,
        "detail": step.detail,
        "index": index,
        "total": total,
    })


def _frame(page, directory: Path, index: int, *, delay: int):
    path = directory / f"{index:02d}.png"
    page.screenshot(path=str(path), animations="disabled")
    return path, delay


def _build_gif(frames, destination, magick):
    command = [magick]
    for path, delay in frames:
        command.extend(("-delay", str(delay), str(path)))
    # Repeat the last view briefly before the loop returns to the chapter card.
    command.extend((
        "-delay", "80", str(frames[-1][0]),
        "-loop", "0", "-resize", GIF_SIZE, "-colors", "160",
        "-dither", "FloydSteinberg", "-layers", "Optimize", str(destination),
    ))
    subprocess.run(command, check=True)


def capture(base: str, out_dir: Path):
    magick = shutil.which("magick")
    if not magick:
        raise SystemExit("ImageMagick 'magick' was not found")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        context = browser.new_context(
            viewport={"width": CAPTURE_SIZE[0], "height": CAPTURE_SIZE[1]},
            device_scale_factor=1,
            color_scheme="dark",
        )
        page = context.new_page()
        saved = page.request.get(f"{base}/api/config/export").json()
        state = page.request.get(f"{base}/api/state").json()
        was_running = bool(state["running"])

        try:
            page.goto(base, wait_until="domcontentloaded")
            page.evaluate("localStorage.setItem('labpro_lang','en')")
            page.request.post(
                f"{base}/api/preset",
                data={"name": "Link con margine — FEC al lavoro"})
            page.request.post(f"{base}/api/run", data={"running": True})
            page.wait_for_timeout(1_800)

            with tempfile.TemporaryDirectory(prefix="labpro-readme-") as tmp:
                temp_root = Path(tmp)
                total_tours = len(TOURS)
                for chapter, (gif_name, tour) in enumerate(TOURS.items(), 1):
                    tour_dir = temp_root / gif_name.removesuffix(".gif")
                    tour_dir.mkdir()
                    _open_panels(page, base, [step.panel for step in tour.steps])
                    frames = []

                    _show_intro(page, tour, chapter, total_tours)
                    frames.append(_frame(page, tour_dir, 0, delay=180))
                    _hide_intro(page)

                    for index, step in enumerate(tour.steps, 1):
                        _prepare_step(page, base, step)
                        _update_hud(page, step, index, len(tour.steps))
                        frames.append(_frame(
                            page, tour_dir, index,
                            delay=210 if gif_name == "00-instruments-hero.gif" else 170,
                        ))

                    destination = out_dir / gif_name
                    _build_gif(frames, destination, magick)
                    try:
                        label = destination.relative_to(ROOT)
                    except ValueError:
                        label = destination
                    print(
                        f"{label} · {len(frames)} frames · "
                        f"{destination.stat().st_size / 1024:.0f} KiB")
        finally:
            page.request.post(f"{base}/api/config/import", data=saved)
            page.request.post(f"{base}/api/run", data={"running": was_running})
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Capture polished, annotated README GIFs from a live Lab PRO bench.")
    parser.add_argument("--base", default="http://127.0.0.1:8640")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    capture(args.base.rstrip("/"), args.out.resolve())


if __name__ == "__main__":
    main()
