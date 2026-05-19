#!/usr/bin/env python3
"""Build a self-contained single-page HTML reader for x-algorithm-wiki.

Reads the 34 wiki markdown pages + changelogs, embeds them, emits site/index.html.
Run:  python3 site/build.py
"""
import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "index.html")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def split_frontmatter(text):
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[1], parts[2].lstrip("\n")
    return "", text


def fm_get(fm, key):
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip() if m else ""


def fix_wiki_links(md):
    """[[name]] / [[name|alias]] / [[name\\|alias]]  ->  [alias](#name)"""
    def repl(m):
        name = m.group(1).strip()
        alias = (m.group(2) or name).strip()
        return f"[{alias}](#{name})"
    return re.sub(r"\[\[([^\]|\\]+)(?:\\?\|([^\]]+?))?\]\]", repl, md)


def find_file(name):
    for sub in ("concepts", "entities", "guide", "changelog"):
        p = os.path.join(ROOT, sub, name + ".md")
        if os.path.exists(p):
            return p
    return None


# --- parse index.md into sidebar groups (document order) ---
groups = []
for line in read(os.path.join(ROOT, "index.md")).splitlines():
    h = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
    if h:
        groups.append({"label": h.group(1), "pages": []})
        continue
    lk = re.match(r"^-\s*\[\[([^\]|]+)\]\]", line)
    if lk and groups:
        groups[-1]["pages"].append(lk.group(1).strip())
groups = [g for g in groups if g["pages"]]

# --- collect every page (in case index misses one) ---
seen = {p for g in groups for p in g["pages"]}
extra = []
for sub in ("concepts", "entities", "guide", "changelog"):
    for fn in sorted(os.listdir(os.path.join(ROOT, sub))):
        if fn.endswith(".md"):
            nm = fn[:-3]
            if nm not in seen:
                extra.append(nm)
if extra:
    groups.append({"label": "其它", "pages": extra})

# --- build page data ---
pages = {}
for g in groups:
    for name in g["pages"]:
        path = find_file(name)
        if not path:
            print("  ! missing:", name)
            continue
        fm, body = split_frontmatter(read(path))
        pages[name] = {
            "title": fm_get(fm, "title") or name,
            "type": fm_get(fm, "type") or "page",
            "group": g["label"],
            "md": fix_wiki_links(body),
        }

groups = [{"label": g["label"], "pages": [p for p in g["pages"] if p in pages]}
          for g in groups]
groups = [g for g in groups if g["pages"]]

total = len([p for p in pages if pages[p]["type"] != "changelog"])
data_json = json.dumps(pages, ensure_ascii=False).replace("</", "<\\/")
groups_json = json.dumps(groups, ensure_ascii=False).replace("</", "<\\/")
print(f"  pages={len(pages)}  groups={len(groups)}  content-pages={total}")

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>X 算法 Wiki · 源码级解读</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,500;0,600;1,500&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
:root{
  --bg:#0c0d10; --surface:#121318; --surface-2:#1a1b22; --inset:#16171d;
  --border:#272932; --border-soft:#1f2027;
  --text:#e7e7ea; --dim:#9a9ca6; --mute:#6b6d79;
  --accent:#e8b14a; --accent-2:#f0c873; --accent-soft:rgba(232,177,74,.10);
  --font-display:'Spectral','Songti SC',Georgia,serif;
  --font-body:'IBM Plex Sans','PingFang SC','Microsoft YaHei',sans-serif;
  --font-mono:'IBM Plex Mono','SF Mono',Menlo,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  background:var(--bg); color:var(--text); font-family:var(--font-body);
  font-size:15.5px; line-height:1.5; -webkit-font-smoothing:antialiased;
  display:flex; overflow:hidden;
}
::selection{background:var(--accent-soft);color:var(--accent-2)}
/* scrollbars */
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:#2c2e38;border-radius:6px;border:2px solid var(--bg)}
::-webkit-scrollbar-thumb:hover{background:#3a3d4a}

/* ===== SIDEBAR ===== */
#sidebar{
  width:312px; flex-shrink:0; height:100vh; background:var(--surface);
  border-right:1px solid var(--border); display:flex; flex-direction:column;
}
.brand{padding:26px 24px 18px;border-bottom:1px solid var(--border-soft)}
.brand .mark{
  font-family:var(--font-mono); font-size:11px; letter-spacing:.22em;
  color:var(--accent); text-transform:uppercase; margin-bottom:9px;
}
.brand h1{
  font-family:var(--font-display); font-weight:600; font-size:25px;
  line-height:1.2; letter-spacing:.01em;
}
.brand .sub{font-size:12px;color:var(--mute);margin-top:7px;font-family:var(--font-mono)}
.searchbox{padding:14px 18px 6px}
.searchbox input{
  width:100%; background:var(--inset); border:1px solid var(--border);
  color:var(--text); font-family:var(--font-mono); font-size:13px;
  padding:9px 12px; border-radius:7px; outline:none;
}
.searchbox input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.searchbox input::placeholder{color:var(--mute)}
#nav{flex:1;overflow-y:auto;padding:8px 12px 40px}
.grp{margin-top:14px}
.grp-label{
  font-family:var(--font-mono); font-size:10.5px; letter-spacing:.16em;
  color:var(--mute); text-transform:uppercase; padding:6px 12px 5px;
}
.nav-item{
  display:block; padding:6.5px 12px; border-radius:7px; color:var(--dim);
  text-decoration:none; font-size:13.5px; border-left:2px solid transparent;
  transition:background .13s,color .13s; cursor:pointer;
}
.nav-item:hover{background:var(--surface-2);color:var(--text)}
.nav-item.active{
  background:var(--accent-soft); color:var(--accent-2);
  border-left-color:var(--accent); font-weight:500;
}
.nav-empty{padding:10px 12px;color:var(--mute);font-size:12.5px}

/* ===== MAIN ===== */
#main{flex:1;height:100vh;overflow-y:auto;position:relative}
.glow{
  position:absolute;top:-220px;left:50%;transform:translateX(-50%);
  width:780px;height:440px;pointer-events:none;
  background:radial-gradient(ellipse,rgba(232,177,74,.07),transparent 70%);
}
.article{max-width:880px;margin:0 auto;padding:54px 56px 140px;position:relative}
.crumb{
  font-family:var(--font-mono);font-size:11px;letter-spacing:.13em;
  color:var(--mute);text-transform:uppercase;margin-bottom:20px;
}
.crumb .t{color:var(--accent)}

/* markdown */
.md{animation:fade .4s ease both}
@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.md h1{
  font-family:var(--font-display);font-weight:600;font-size:33px;
  line-height:1.22;letter-spacing:.005em;margin:2px 0 22px;
}
.md h2{
  font-family:var(--font-display);font-weight:600;font-size:22.5px;
  margin:38px 0 13px;padding-bottom:8px;border-bottom:1px solid var(--border);
}
.md h3{font-weight:600;font-size:17px;margin:26px 0 9px;color:var(--accent-2)}
.md h4{font-weight:600;font-size:15px;margin:20px 0 7px;color:var(--dim)}
.md p{margin:11px 0;color:#dcdce0}
.md ul,.md ol{margin:11px 0;padding-left:24px}
.md li{margin:5px 0;color:#dcdce0}
.md li::marker{color:var(--mute)}
.md strong{color:#fff;font-weight:600}
.md em{color:var(--accent-2)}
.md a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(232,177,74,.3)}
.md a:hover{border-bottom-color:var(--accent);background:var(--accent-soft)}
.md blockquote{
  border-left:2px solid var(--accent);background:var(--accent-soft);
  margin:14px 0;padding:9px 18px;border-radius:0 7px 7px 0;color:var(--dim);
}
.md blockquote p{color:var(--dim);margin:5px 0}
.md hr{border:0;border-top:1px solid var(--border);margin:28px 0}
.md code{
  font-family:var(--font-mono);font-size:.86em;background:var(--inset);
  border:1px solid var(--border-soft);padding:1.5px 5px;border-radius:4px;color:#c8cad0;
}
/* signature detail: source-code anchors as gold evidence tags */
.md code.anchor{
  color:var(--accent-2);background:var(--accent-soft);
  border-color:rgba(232,177,74,.28);font-weight:500;
}
.md pre{
  background:var(--inset);border:1px solid var(--border);border-radius:9px;
  padding:15px 17px;overflow-x:auto;margin:14px 0;
}
.md pre code{background:none;border:0;padding:0;font-size:12.8px;color:#cfd2da;line-height:1.62}
.table-wrap{overflow-x:auto;margin:15px 0;border:1px solid var(--border);border-radius:9px}
.md table{border-collapse:collapse;width:100%;font-size:13.5px}
.md th{
  background:var(--surface-2);text-align:left;padding:9px 13px;
  font-weight:600;color:var(--accent-2);border-bottom:1px solid var(--border);
  white-space:nowrap;
}
.md td{padding:8px 13px;border-bottom:1px solid var(--border-soft);color:#d2d3d9;vertical-align:top}
.md tr:last-child td{border-bottom:0}
.md tbody tr:hover{background:rgba(255,255,255,.018)}
.mermaid{
  background:var(--inset);border:1px solid var(--border);border-radius:9px;
  padding:18px;margin:16px 0;text-align:center;overflow-x:auto;
}
.mermaid svg{max-width:100%;height:auto}

/* mobile */
#menu-btn{
  display:none;position:fixed;top:14px;left:14px;z-index:30;
  background:var(--surface);border:1px solid var(--border);color:var(--accent);
  width:40px;height:40px;border-radius:9px;font-size:18px;cursor:pointer;
}
#scrim{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:18}
@media(max-width:880px){
  #sidebar{position:fixed;z-index:20;transform:translateX(-100%);transition:transform .22s}
  #sidebar.open{transform:none}
  #scrim.show{display:block}
  #menu-btn{display:block}
  .article{padding:64px 22px 110px}
  .md h1{font-size:27px}
}
</style>
</head>
<body>
<button id="menu-btn">☰</button>
<div id="scrim"></div>
<aside id="sidebar">
  <div class="brand">
    <div class="mark">xai-org/x-algorithm · 0bfc279</div>
    <h1>X 算法 Wiki</h1>
    <div class="sub" id="brand-sub"></div>
  </div>
  <div class="searchbox"><input id="q" type="text" placeholder="搜索页面 / 内容…  (/)"></div>
  <nav id="nav"></nav>
</aside>
<main id="main">
  <div class="glow"></div>
  <div class="article">
    <div class="crumb" id="crumb"></div>
    <div class="md" id="content"></div>
  </div>
</main>
<script>
const PAGES=__WIKI_DATA__;
const GROUPS=__WIKI_GROUPS__;
const CONTENT_PAGES=__TOTAL__;

marked.setOptions({gfm:true,breaks:false});
mermaid.initialize({startOnLoad:false,theme:'dark',securityLevel:'loose',
  themeVariables:{fontFamily:"'IBM Plex Mono',monospace",fontSize:'13px',
    primaryColor:'#1a1b22',primaryBorderColor:'#3a3d4a',primaryTextColor:'#e7e7ea',
    lineColor:'#6b6d79',background:'#16171d'}});

const nav=document.getElementById('nav'), content=document.getElementById('content'),
      crumb=document.getElementById('crumb'), sidebar=document.getElementById('sidebar'),
      scrim=document.getElementById('scrim');
document.getElementById('brand-sub').textContent=CONTENT_PAGES+' 页 · 源码级解读';

function buildNav(filter){
  filter=(filter||'').trim().toLowerCase();
  nav.innerHTML=''; let hits=0;
  GROUPS.forEach(g=>{
    const items=g.pages.filter(n=>{
      if(!filter) return true;
      const p=PAGES[n];
      return p.title.toLowerCase().includes(filter)
          || n.toLowerCase().includes(filter)
          || p.md.toLowerCase().includes(filter);
    });
    if(!items.length) return;
    const box=document.createElement('div'); box.className='grp';
    const lab=document.createElement('div'); lab.className='grp-label';
    lab.textContent=g.label; box.appendChild(lab);
    items.forEach(n=>{
      hits++;
      const a=document.createElement('a');
      a.className='nav-item'; a.href='#'+n; a.dataset.page=n;
      a.textContent=PAGES[n].title;
      box.appendChild(a);
    });
    nav.appendChild(box);
  });
  if(!hits){nav.innerHTML='<div class="nav-empty">无匹配页面</div>';}
}

function decorate(){
  // wrap wide tables for horizontal scroll
  content.querySelectorAll('table').forEach(t=>{
    if(t.parentElement.classList.contains('table-wrap'))return;
    const w=document.createElement('div'); w.className='table-wrap';
    t.replaceWith(w); w.appendChild(t);
  });
  // gold "evidence tag" for source anchors  file.rs:NN / path/x.py:NN-NN
  content.querySelectorAll('code').forEach(c=>{
    if(/[\w/.\-]+\.(rs|py|md):\d/.test(c.textContent)) c.classList.add('anchor');
  });
  // render mermaid
  const blocks=[...content.querySelectorAll('code.language-mermaid')];
  blocks.forEach((c,i)=>{
    const d=document.createElement('div'); d.className='mermaid';
    d.id='mmd-'+Date.now()+'-'+i; d.textContent=c.textContent;
    c.closest('pre').replaceWith(d);
  });
  if(blocks.length){
    mermaid.run({nodes:content.querySelectorAll('.mermaid')}).catch(()=>{});
  }
}

function render(name){
  const p=PAGES[name];
  if(!p){content.innerHTML='<h1>页面未找到</h1><p>'+name+'</p>';return;}
  crumb.innerHTML='<span class="t">'+p.group+'</span> &nbsp;/&nbsp; '+p.type;
  content.className='md'; void content.offsetWidth; content.classList.add('md');
  content.innerHTML=marked.parse(p.md);
  decorate();
  document.title=p.title+' · X 算法 Wiki';
  document.querySelectorAll('.nav-item').forEach(a=>
    a.classList.toggle('active',a.dataset.page===name));
  document.getElementById('main').scrollTop=0;
  sidebar.classList.remove('open'); scrim.classList.remove('show');
}

function route(){
  const n=decodeURIComponent(location.hash.slice(1));
  render(PAGES[n]?n:GROUPS[0].pages[0]);
}
window.addEventListener('hashchange',route);

const q=document.getElementById('q');
q.addEventListener('input',()=>buildNav(q.value));
document.addEventListener('keydown',e=>{
  if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();}
});
document.getElementById('menu-btn').onclick=()=>{
  sidebar.classList.toggle('open');scrim.classList.toggle('show');};
scrim.onclick=()=>{sidebar.classList.remove('open');scrim.classList.remove('show');};

buildNav();
route();
</script>
</body>
</html>"""

html = (HTML
        .replace("__WIKI_DATA__", data_json)
        .replace("__WIKI_GROUPS__", groups_json)
        .replace("__TOTAL__", str(total)))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"  -> {OUT}  ({len(html)//1024} KB)")
