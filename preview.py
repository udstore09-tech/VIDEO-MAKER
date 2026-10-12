"""Serve the cartoon on port 8080 for review in a browser.

    python preview.py [--port 8080]

Serving ./output, writing output/index.html first. Byte ranges are implemented
because Python's stock http.server has none, and a <video> tag cannot seek - or
sometimes even start - without them.
"""
from __future__ import annotations

import argparse
import os
import posixpath
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "output")

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pencil cartoon — review</title>
<style>
  :root{--ink:#181818;--paper:#efece6;--line:#c9c4ba}
  *{box-sizing:border-box}
  body{margin:0;background:#141414;color:#e8e6e2;font:14px/1.5 ui-sans-serif,system-ui,sans-serif;
       display:flex;gap:26px;justify-content:center;align-items:flex-start;padding:22px 18px;flex-wrap:wrap}
  video{display:block;background:#000;border:1px solid #2e2e2e;border-radius:6px;
        height:min(84vh,900px);aspect-ratio:9/16;max-width:100%}
  .side{width:min(360px,94vw);display:flex;flex-direction:column;gap:14px}
  h1{font-size:17px;margin:0;letter-spacing:.02em}
  .sub{color:#9a968f;font-size:12px;margin-top:-8px}
  .chaps{display:grid;grid-template-columns:1fr 1fr;gap:7px}
  .chaps button{all:unset;cursor:pointer;padding:8px 10px;border:1px solid #333;border-radius:5px;
                background:#1b1b1b;font-size:12.5px;color:#dcdad6}
  .chaps button:hover{border-color:#6d6a64;background:#232323}
  .chaps b{color:#8f8b84;font-variant-numeric:tabular-nums;margin-right:6px}
  .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .row a,.row button{all:unset;cursor:pointer;padding:6px 10px;border:1px solid #333;border-radius:5px;
                     background:#1b1b1b;font-size:12px;color:#c9c6c1}
  .row a:hover,.row button:hover{border-color:#6d6a64}
  #tc{font-variant-numeric:tabular-nums;color:#8f8b84;font-size:12px}
  ul{margin:0;padding-left:17px;color:#8f8b84;font-size:12px}
  ul b{color:#c9c6c1;font-weight:500}
  kbd{border:1px solid #3a3a3a;border-bottom-width:2px;border-radius:3px;padding:0 4px;
      font:11px ui-monospace,monospace;color:#c9c6c1;background:#1d1d1d}
  figure{margin:0;width:min(84vw,900px)}
  figure img{width:100%;border:1px solid #2e2e2e;border-radius:6px;background:var(--paper)}
  figcaption{color:#8f8b84;font-size:12px;margin-top:6px}
</style>
<figure>
  <video id="v" src="/pencil_cartoon.mp4" controls playsinline loop preload="metadata"></video>
</figure>
<div class="side">
  <h1>Pencil cartoon — 30&nbsp;s review</h1>
  <div class="sub">1080×1920 · 60&nbsp;fps · drawings on 20s · H.264 + AAC</div>
  <div class="chaps" id="ch"></div>
  <div class="row">
    <button data-k="f-">◀ frame</button><button data-k="f+">frame ▶</button>
    <button data-k="half-">−0.1s</button><button data-k="half+">+0.1s</button>
    <span id="tc">0.000s · f0</span>
  </div>
  <div class="row">
    <a href="/pencil_cartoon_silent.mp4">silent mp4</a><a href="/score.wav">score.wav</a>
    <a href="/model_sheet.png">model sheet</a><a href="/frame_07.00.png">a frame @1×</a>
  </div>
  <ul>
    <li><b>space</b> play/pause · <b>←/→</b> 0.5&nbsp;s · <b>,</b> / <b>.</b> one frame</li>
    <li>Every one of the 1800 frames is drawn live by <b>pencilcartoon/</b>; no video model, no stills.</li>
    <li>Re-render: <b>python make.py video</b> (~7 min) then <b>audio</b>, <b>mux</b>. Retime a gag in <b>story.py</b>.</li>
    <li>X-sheet of any window: <b>python make.py strip --t0 10 --t1 13 --n 12</b></li>
  </ul>
</div>
<script>
const v=document.getElementById('v'), tc=document.getElementById('tc');
const CH=[[0,'they sit, one cookie'],[2.6,'the sneak'],[4.1,'the grab'],[5.4,'innocent whistle'],
          [6.4,'crumbs — fury'],[7.0,'the chase'],[10.45,'leap the pencil'],[11.12,'B eats it'],
          [12.1,'eraser pile'],[12.9,'A howls'],[15.2,'fake tears'],[17.6,'the point'],
          [18.2,'cookie snatched back'],[18.6,'the shock'],[20.0,'chase #2'],[21.6,'the slide'],
          [22.62,'head-on'],[23.2,'spinning tops'],[25.2,'out of breath'],[26.5,'peace offering'],
          [27.5,'the handshake'],[28.0,'...stolen again'],[28.4,'to camera'],[28.9,'both laugh'],
          [29.62,'freeze frame']];
const box=document.getElementById('ch');
for(const [t,name] of CH){
  const b=document.createElement('button');
  b.innerHTML='<b>'+t.toFixed(2)+'</b>'+name;
  b.onclick=()=>{v.currentTime=t+.001;v.play();};
  box.appendChild(b);
}
const FPS=60;
const upd=()=>{const n=v.currentTime*FPS;
  tc.textContent=v.currentTime.toFixed(3)+'s · f'+Math.round(n);};
v.addEventListener('timeupdate',upd); v.addEventListener('seeked',upd);
addEventListener('keydown',e=>{
  const k=e.key;
  if(k===' '){e.preventDefault();v.paused?v.play():v.pause();}
  else if(k==='ArrowLeft')v.currentTime=Math.max(0,v.currentTime-.5);
  else if(k==='ArrowRight')v.currentTime=Math.min(30,v.currentTime+.5);
  else if(k===',')v.currentTime=Math.max(0,Math.round(v.currentTime*FPS-1)/FPS);
  else if(k==='.')v.currentTime=Math.min(30,Math.round(v.currentTime*FPS+1)/FPS);
});
document.querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{
  const k=b.dataset.k;
  if(k==='f-')v.currentTime=Math.max(0,Math.round(v.currentTime*FPS-1)/FPS);
  if(k==='f+')v.currentTime=Math.min(30,Math.round(v.currentTime*FPS+1)/FPS);
  if(k==='half-')v.currentTime=Math.max(0,v.currentTime-.1);
  if(k==='half+')v.currentTime=Math.min(30,v.currentTime+.1);
});
</script>
"""


class Handler(SimpleHTTPRequestHandler):
    """Static files with HTTP range requests (needed for seeking mp4)."""

    def translate_path(self, path):
        """Root everything in output/, and never serve dotfiles."""
        clean = posixpath.normpath(self.path.split("?", 1)[0].split("#", 1)[0])
        if any(part.startswith(".") for part in clean.split("/") if part):
            return ""                      # make translate_path 404 on it
        return super().translate_path(path)

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if rng and path and os.path.isfile(path):
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            size = os.path.getsize(path)
            if m:
                a, b = m.groups()
                start = int(a) if a else max(0, size - int(b or 1))
                end = min(int(b) if (a and b) else size - 1, size - 1)
                if start >= size or start > end:
                    self.send_error(416, f"Requested Range Not Satisfiable ({size})")
                    return None
                f = open(path, "rb")
                f.seek(start)
                self.send_response(206)
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return f
        return super().send_head()

    def list_directory(self, path):
        return self.send_error(404, "No listing")

    def log_message(self, fmt, *a):
        if a and " 206" not in str(a[1]):
            super().log_message(fmt, *a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "index.html"), "w") as fh:
        fh.write(PAGE)
    handler = partial(Handler, directory=ROOT)
    print(f"serving {ROOT} on http://{a.host}:{a.port}/", flush=True)
    ThreadingHTTPServer((a.host, a.port), handler).serve_forever()


if __name__ == "__main__":
    main()
