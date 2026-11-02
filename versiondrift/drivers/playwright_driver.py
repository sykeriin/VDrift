"""Playwright driver: pixel-level actions + an accessibility-style snapshot of interactive elements."""
from __future__ import annotations
import re
from playwright.sync_api import sync_playwright, Page

SNAPSHOT_JS = r"""
() => {
  const IMPLICIT = {A:'link', BUTTON:'button', INPUT:'textbox', SELECT:'combobox', TEXTAREA:'textbox', SUMMARY:'button', LABEL:'label'};
  const SEL = 'a,button,input,select,textarea,summary,label,[role],.item,.button,[onclick]';
  const CTX = /(menu|dropdown|modal|dialog|header|navbar|tabular|form|sidebar|toolbar|popup|nav)/i;
  const out = [];
  const txt = e => (e.innerText || e.textContent || '').replace(/\s+/g,' ').trim();
  for (const e of document.querySelectorAll(SEL)) {
    const r = e.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    const cs = getComputedStyle(e);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    if (r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.right > innerWidth + 50) continue;
    let role = e.getAttribute('role') || IMPLICIT[e.tagName] || (e.matches('.item') ? 'menuitem' : 'generic');
    if (e.tagName === 'INPUT') { const t = (e.type||'text'); role = t==='checkbox'?'checkbox':t==='radio'?'radio':(['submit','button'].includes(t)?'button':'textbox'); }
    let name = e.getAttribute('aria-label') || '';
    if (!name && e.id) { const l = document.querySelector('label[for="'+CSS.escape(e.id)+'"]'); if (l) name = txt(l); }
    if (!name && ['INPUT','TEXTAREA','SELECT'].includes(e.tagName)) name = e.getAttribute('placeholder') || e.getAttribute('name') || '';
    if (!name && e.tagName==='INPUT' && ['submit','button'].includes(e.type)) name = e.value || '';
    if (!name) name = txt(e);
    if (!name) name = e.getAttribute('title') || e.getAttribute('data-tooltip-content') || (e.querySelector('img') && e.querySelector('img').alt) || '';
    name = name.slice(0, 80);
    const anc = []; let p = e.parentElement;
    while (p && p !== document.body && anc.length < 6) {
      const cls = (typeof p.className === 'string' ? p.className : '');
      const m = cls.match(CTX);
      const tag = p.tagName.toLowerCase();
      const tok = (p.getAttribute('role') || '') + '|' + (p.getAttribute('aria-label')||'') + '|' + (['nav','header','main','form','aside','dialog'].includes(tag)?tag:'') + '|' + (m?m[1].toLowerCase():'');
      if (tok !== '|||') anc.push(tok);
      p = p.parentElement;
    }
    const attrs = {};
    for (const a of ['id','name','type','href','placeholder','class','for','value']) { const v = e.getAttribute(a); if (v) attrs[a] = v.slice(0,120); }
    out.push({ tag: e.tagName.toLowerCase(), role, name, text: txt(e).slice(0,120), attrs,
               bbox: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)], anc });
  }
  return out;
}
"""

class Driver:
    def __init__(self, headless=True, viewport=(1280, 1200)):
        self.viewport = {"width": viewport[0], "height": viewport[1]}
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(executable_path="/opt/pw-browsers/chromium",
                                                args=["--no-sandbox"], headless=headless)
        self.ctx = None; self.page: Page | None = None

    def new_session(self, viewport=None):
        if self.ctx: self.ctx.close()
        vp = {"width": viewport[0], "height": viewport[1]} if viewport else self.viewport
        self.ctx = self.browser.new_context(viewport=vp)
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(8000)
        return self.page

    def login(self, env):
        p = self.page
        p.goto(env.url + "/user/login")
        p.fill("#user_name", env.auth[0]); p.fill("#password", env.auth[1])
        p.locator("form.ui.form button.ui.button, form button[type=submit]").last.click()
        p.wait_for_url(lambda u: "/user/login" not in u, timeout=10000)
        self.settle()

    def goto(self, url): self.page.goto(url); self.settle()

    def settle(self, ms=350):
        try: self.page.wait_for_load_state("networkidle", timeout=3000)
        except Exception: pass
        self.page.wait_for_timeout(ms)

    # --- observation ---
    def snapshot(self) -> list[dict]:
        els = self.page.evaluate(SNAPSHOT_JS)
        for i, e in enumerate(els):
            e["i"] = i
            cx, cy = e["bbox"][0] + e["bbox"][2] / 2, e["bbox"][1] + e["bbox"][3] / 2
            e["center"] = (cx, cy)
        add_neighbours(els)
        return els

    def screenshot(self, path): self.page.screenshot(path=path)
    @property
    def url(self): return self.page.url

    # --- actions ---
    def click(self, x, y):
        self.page.mouse.click(x, y); self.settle()

    def type_at(self, x, y, text):
        self.page.mouse.click(x, y)
        self.page.keyboard.press("Control+A"); self.page.keyboard.type(text); self.settle(150)

    def press(self, key): self.page.keyboard.press(key); self.settle()

    def close(self):
        try: self.browser.close(); self._pw.stop()
        except Exception: pass


def add_neighbours(els, k=4):
    cents = [(i, e) for i, e in enumerate(els) if e["name"]]
    for e in els:
        ds = sorted(((e["center"][0]-o["center"][0])**2 + (e["center"][1]-o["center"][1])**2, j) for j, o in cents if o is not e and o["name"] != e["name"])
        e["neighbours"] = [els[j]["name"] for _, j in ds[:k]]


def element_at(els, x, y):
    """Smallest interactive element whose bbox contains (x, y)."""
    best = None
    for e in els:
        bx, by, bw, bh = e["bbox"]
        if bx <= x <= bx + bw and by <= y <= by + bh:
            if best is None or bw * bh < best["bbox"][2] * best["bbox"][3]: best = e
    return best
