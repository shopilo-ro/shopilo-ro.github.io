#!/usr/bin/env python3
"""
Shopilo GitHub Repos Creator — Multi-country support

Usage:
  python3 create_repos.py --token TOKEN --username shopilo-ro --country ro
  python3 create_repos.py --token TOKEN --username shopilo-de --country de
  python3 create_repos.py --token TOKEN --username shopilo-fr --country fr

Fiecare tara are un folder shopilo.{tld}/ cu:
  stores.py  — COUNTRY_CONFIG + STORES lista de magazine

Obtine tokenul din: GitHub -> Settings -> Developer settings -> Personal access tokens
Permisiuni necesare: repo (full control)
"""

import argparse
import base64
import importlib.util
import json
import os
import sys
import time
import calendar
import requests
from datetime import datetime

NOW      = datetime.now()
YEAR_STR = str(NOW.year)

# Expiry dinamic: intotdeauna NOW + 6 luni (regenerat lunar de GitHub Action)
def _six_months_from_now():
    month = NOW.month + 6
    year  = NOW.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day   = min(NOW.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)

EXPIRY_DATE = _six_months_from_now().strftime("%Y-%m-%d")

# Setate dinamic in main() pe baza COUNTRY_CONFIG
SHOPILO_DOMAIN = "shopilo.ro"
MONTH_STR      = ""


# ─── GITHUB API ───────────────────────────────────────────────────────────────

class GitHubAPI:
    def __init__(self, token, username):
        self.token = token
        self.username = username
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        })

    def create_repo(self, name, description):
        r = self.session.post("https://api.github.com/user/repos", json={
            "name": name,
            "description": description,
            "private": False,
            "auto_init": False,
            "has_issues": False,
            "has_projects": False,
            "has_wiki": False
        })
        if r.status_code == 201:
            return True, "creat"
        elif r.status_code == 422:
            return True, "exista deja"
        else:
            return False, r.json().get("message", str(r.status_code))

    def create_file(self, repo, path, content, message):
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        r = self.session.put(
            f"https://api.github.com/repos/{self.username}/{repo}/contents/{path}",
            json={"message": message, "content": encoded}
        )
        return r.status_code in (200, 201)

    def enable_pages(self, repo):
        r = self.session.post(
            f"https://api.github.com/repos/{self.username}/{repo}/pages",
            json={"source": {"branch": "main", "path": "/"}}
        )
        return r.status_code in (200, 201)

    def update_file(self, repo, path, content, message):
        """Actualizeaza un fisier existent (necesita SHA-ul curent)."""
        r = self.session.get(
            f"https://api.github.com/repos/{self.username}/{repo}/contents/{path}"
        )
        if r.status_code != 200:
            return False
        sha = r.json().get("sha")
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        r = self.session.put(
            f"https://api.github.com/repos/{self.username}/{repo}/contents/{path}",
            json={"message": message, "content": encoded, "sha": sha}
        )
        return r.status_code in (200, 201)


# ─── GENERARE CONTINUT ────────────────────────────────────────────────────────

def make_readme(store_name, repo_slug, shopilo_slug, example_code,
                example_discount, example_desc, example_date, username):
    shopilo_url = f"https://{SHOPILO_DOMAIN}/magazin/{shopilo_slug}"
    pages_url   = f"https://{username}.github.io"
    store_lower = store_name.lower().replace(" ", "-").replace(".", "")
    return f"""# Cod reducere {store_name} — fetch automat de pe {SHOPILO_DOMAIN}

Modul Python pentru fetch automat de **coduri de reducere {store_name}** de pe [{SHOPILO_DOMAIN}]({shopilo_url}). Returneaza **cupoane {store_name}** active in format JSON, gata de integrat intr-un bot Telegram, extensie de browser sau orice alt tool.

**Pagina live:** [{username}.github.io/{repo_slug}]({pages_url}/{repo_slug}/)

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue) ![License MIT](https://img.shields.io/badge/license-MIT-green)

## Instalare

```bash
pip install requests beautifulsoup4
git clone https://github.com/{username}/{repo_slug}
cd {repo_slug}
python fetch.py
```

## Output exemplu

```json
[
  {{
    "store": "{store_name}",
    "code": "{example_code}",
    "discount": "{example_discount}",
    "description": "{example_desc}",
    "expires": "{EXPIRY_DATE}",
    "source": "{shopilo_url}"
  }}
]
```

## Cupoane {store_name} disponibile

| Reducere | Descriere | Sursa |
|----------|-----------|-------|
| {example_discount} | {example_desc} | [{SHOPILO_DOMAIN}]({shopilo_url}) |

Codurile active: **[{SHOPILO_DOMAIN}/magazin/{shopilo_slug}]({shopilo_url})**

## Intrebari frecvente

### Cum folosesc un cod de reducere {store_name}?
Copiaza codul din tabelul de mai sus sau de pe [{SHOPILO_DOMAIN}]({shopilo_url}), adauga produsele in cos pe {store_name}, si introdu codul la checkout in campul dedicat.

### Cat timp sunt valabile cupoanele {store_name}?
Fiecare cupon are data de expirare afisata in coloana "Expira". Scriptul fetch.py returneaza doar cupoanele active la momentul rularii.

### Unde gasesc cele mai noi voucher-uri {store_name}?
Pagina [{SHOPILO_DOMAIN}/magazin/{shopilo_slug}]({shopilo_url}) este actualizata zilnic cu cele mai noi cod reducere {store_name}, voucher {store_name} si cupon promotional {store_name}.

### Codul nu functioneaza. Ce fac?
Verifica data de expirare si conditiile (valoare minima cos, produse eligibile). Unele coduri sunt valabile doar in aplicatia mobila sau pentru prima comanda.

## Despre {store_name}

{store_name} este unul dintre magazinele online populare. Gasesti pe [{SHOPILO_DOMAIN}]({shopilo_url}) cele mai bune cod reducere {store_name}, cupoane {store_name} verificate si voucher {store_name} active, actualizate zilnic.

## Instalare npm

```bash
npm install {repo_slug}
```

```javascript
const {{ fetchCoupons }} = require('{repo_slug}');
fetchCoupons().then(data => console.log(data));
```

## Licenta

MIT — date sursa de pe [{SHOPILO_DOMAIN}](https://{SHOPILO_DOMAIN})
"""


def make_fetch_py(store_name, repo_slug, shopilo_slug, username):
    shopilo_url = f"https://{SHOPILO_DOMAIN}/magazin/{shopilo_slug}"
    return f"""#!/usr/bin/env python3
\"\"\"
Fetch coduri de reducere {store_name} de pe {SHOPILO_DOMAIN}
Sursa: {shopilo_url}
\"\"\"

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

SHOPILO_URL = "{shopilo_url}"
STORE_NAME = "{store_name}"


def fetch_coupons(url=SHOPILO_URL):
    \"\"\"Returneaza lista de cupoane active pentru {store_name} de pe {SHOPILO_DOMAIN}\"\"\"
    headers = {{
        "User-Agent": "Mozilla/5.0 (compatible; coupon-fetcher/1.0; +https://github.com/{username}/{repo_slug})"
    }}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Eroare la fetch: {{e}}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    coupons = []

    for item in soup.select(".coupon-item, [data-coupon], .offer-card"):
        code_el     = item.select_one("[data-code], .coupon-code, .code")
        discount_el = item.select_one(".discount, .percent, .amount")
        desc_el     = item.select_one(".title, .description, h3")
        expires_el  = item.select_one(".expires, .expiry, [data-expires]")

        coupon = {{
            "store":      STORE_NAME,
            "code":       code_el.get_text(strip=True)     if code_el     else None,
            "discount":   discount_el.get_text(strip=True) if discount_el else None,
            "description":desc_el.get_text(strip=True)     if desc_el     else None,
            "expires":    expires_el.get_text(strip=True)  if expires_el  else None,
            "source":     SHOPILO_URL,
            "fetched_at": datetime.now().isoformat()
        }}

        if coupon["description"]:
            coupons.append(coupon)

    return coupons


if __name__ == "__main__":
    print(f"Fetching coduri reducere {{STORE_NAME}} de pe {SHOPILO_DOMAIN}...\\n")
    coupons = fetch_coupons()

    if coupons:
        print(json.dumps(coupons, ensure_ascii=False, indent=2))
        print(f"\\nTotal: {{len(coupons)}} cupoane gasite")
    else:
        print(f"Nu s-au gasit cupoane. Vezi lista completa la: {{SHOPILO_URL}}")
"""


def make_workflow_yml(username, country):
    return f"""name: Update Store Pages

on:
  schedule:
    - cron: '0 6 1 * *'   # Prima zi a fiecarei luni la 06:00 UTC
  workflow_dispatch:       # Permite rulare manuala din GitHub UI

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Update all store pages with current month
        run: python3 create_repos.py --token "$GH_PAT" --username "{username}" --country "{country}" --update-html
        env:
          GH_PAT: ${{{{ secrets.GH_PAT }}}}
"""


def make_package_json(store_name, repo_slug, shopilo_slug, username):
    store_lower = store_name.lower().replace(" ", "-").replace(".", "")
    return json.dumps({
        "name": repo_slug,
        "version": "1.0.0",
        "description": f"Fetch automat de coduri de reducere {store_name} de pe {SHOPILO_DOMAIN}",
        "main": "index.js",
        "keywords": [
            "cod-reducere",
            f"cod-reducere-{store_lower}",
            f"voucher-{store_lower}",
            f"cupon-{store_lower}",
            "reduceri",
            "shopilo",
            "cupoane"
        ],
        "author": username,
        "license": "MIT",
        "homepage": f"https://{SHOPILO_DOMAIN}/magazin/{shopilo_slug}",
        "repository": {
            "type": "git",
            "url": f"https://github.com/{username}/{repo_slug}.git"
        }
    }, indent=2, ensure_ascii=False)


def make_requirements():
    return "requests>=2.28.0\nbeautifulsoup4>=4.11.0\n"


def make_index_js(store_name, repo_slug, shopilo_slug, username):
    shopilo_url = f"https://{SHOPILO_DOMAIN}/magazin/{shopilo_slug}"
    return f"""#!/usr/bin/env node
/**
 * Fetch coduri reducere {store_name} de pe {SHOPILO_DOMAIN}
 * Homepage: {shopilo_url}
 */

const SHOPILO_URL = "{shopilo_url}";
const STORE_NAME  = "{store_name}";

async function fetchCoupons(url = SHOPILO_URL) {{
  const res = await fetch(url, {{
    headers: {{ "User-Agent": "coupon-fetcher/1.0 (+https://github.com/{username}/{repo_slug})" }}
  }});
  if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
  const html = await res.text();
  const codes = [...html.matchAll(/data-code=["']([^"']+)["']/gi)].map(m => m[1]);
  return codes.map(code => ({{ store: STORE_NAME, code, source: SHOPILO_URL }}));
}}

module.exports = {{ fetchCoupons, SHOPILO_URL, STORE_NAME }};

if (require.main === module) {{
  fetchCoupons()
    .then(data => {{
      if (data.length) {{
        console.log(JSON.stringify(data, null, 2));
        console.log(`\\nTotal: ${{data.length}} coduri gasite`);
      }} else {{
        console.log(`Nu s-au gasit coduri. Lista completa: ${{SHOPILO_URL}}`);
      }}
    }})
    .catch(err => console.error("Eroare:", err.message));
}}
"""


def make_index_html(store_name, repo_slug, shopilo_slug, example_code,
                    example_discount, example_desc, example_date, username):
    shopilo_url = f"https://{SHOPILO_DOMAIN}/magazin/{shopilo_slug}"
    pages_url   = f"https://{username}.github.io"
    faq_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"Ce este un cod de reducere {store_name}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Un cod de reducere {store_name} (numit si voucher {store_name} sau cupon {store_name}) este un sir de caractere pe care il introduci la checkout pentru a obtine o reducere la comanda ta."
                }
            },
            {
                "@type": "Question",
                "name": f"Unde gasesc cele mai noi cupoane {store_name}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Pe {SHOPILO_DOMAIN} gasesti lista completa de cod reducere {store_name} actualizata zilnic, cu date de expirare si conditii clare: {shopilo_url}"
                }
            },
            {
                "@type": "Question",
                "name": f"Pot combina mai multe coduri de reducere {store_name}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"De obicei se poate folosi un singur cod per comanda. Verifica termenii fiecarui cupon {store_name} pe pagina {SHOPILO_DOMAIN}."
                }
            },
            {
                "@type": "Question",
                "name": f"Cat timp sunt valabile cupoanele {store_name}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Fiecare cod reducere {store_name} are o data de expirare proprie afisata in tabel. {SHOPILO_DOMAIN} verifica si actualizeaza zilnic lista de cupoane {store_name} active."
                }
            },
            {
                "@type": "Question",
                "name": f"Functioneaza codul de reducere {store_name} pe aplicatia mobila?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Unele cupoane {store_name} sunt valabile exclusiv in aplicatia mobila, altele doar pe site. Conditiile sunt afisate pe fiecare cupon in parte pe {SHOPILO_DOMAIN}."
                }
            }
        ]
    }, ensure_ascii=False, indent=2)
    breadcrumb_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Shopilo Dev", "item": pages_url},
            {"@type": "ListItem", "position": 2, "name": f"Cod reducere {store_name}", "item": f"{pages_url}/{repo_slug}/"}
        ]
    }, ensure_ascii=False)
    webpage_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": f"Cod reducere {store_name} | {SHOPILO_DOMAIN}",
        "description": f"Cele mai bune coduri de reducere {store_name}. Cupoane {store_name} active, voucher {store_name} si oferte exclusive pe {SHOPILO_DOMAIN}.",
        "url": f"{pages_url}/{repo_slug}/",
        "dateModified": f"{YEAR_STR}-{NOW.month:02d}-01",
        "isPartOf": {"@type": "WebSite", "name": "Shopilo Dev", "url": pages_url},
        "about": {"@type": "Thing", "name": store_name}
    }, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cod reducere {store_name} — {MONTH_STR} {YEAR_STR} | {SHOPILO_DOMAIN}</title>
  <meta name="description" content="Script Python open-source pentru fetch automat de coduri de reducere {store_name}. Returneaza cupoane {store_name} active in format JSON de pe {SHOPILO_DOMAIN}.">
  <meta name="robots" content="index, follow">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Cod reducere {store_name} — {MONTH_STR} {YEAR_STR} | {SHOPILO_DOMAIN}">
  <meta property="og:description" content="Script Python open-source pentru fetch automat de coduri de reducere {store_name} de pe {SHOPILO_DOMAIN}.">
  <meta property="og:url" content="{pages_url}/{repo_slug}/">
  <script type="application/ld+json">{faq_schema}</script>
  <script type="application/ld+json">{breadcrumb_schema}</script>
  <script type="application/ld+json">{webpage_schema}</script>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8fa;color:#212529;line-height:1.6}}
    a{{color:#0969da;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    .wrap{{max-width:860px;margin:0 auto;padding:0 24px}}
    header{{background:#24292f;padding:14px 0}}
    .header-inner{{display:flex;justify-content:space-between;align-items:center}}
    .logo{{font-weight:600;color:#fff;font-size:15px}}
    nav a{{font-size:13px;color:#8b949e;margin-left:20px}}
    nav a:hover{{color:#fff;text-decoration:none}}
    .hero{{background:#fff;border-bottom:1px solid #e1e4e8;padding:40px 0 32px}}
    .breadcrumb{{font-size:13px;color:#57606a;margin-bottom:16px}}
    .breadcrumb a{{color:#57606a}}
    .repo-title{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
    .repo-icon{{color:#57606a;font-size:18px}}
    .hero h1{{font-size:22px;font-weight:600;color:#24292f;margin:0}}
    .hero h1 a{{color:#0969da}}
    .hero-desc{{color:#57606a;font-size:15px;margin:10px 0 20px;max-width:600px}}
    .badges{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}}
    .badge{{display:inline-flex;align-items:center;gap:4px;background:#f6f8fa;border:1px solid #e1e4e8;border-radius:4px;padding:3px 10px;font-size:12px;color:#57606a}}
    .badge-blue{{background:#ddf4ff;border-color:#54aeff;color:#0550ae}}
    .badge-green{{background:#dafbe1;border-color:#56d364;color:#1a7f37}}
    .cta{{display:inline-flex;align-items:center;gap:6px;background:#2da44e;color:#fff;padding:8px 18px;border-radius:6px;font-size:14px;font-weight:600;transition:.15s}}
    .cta:hover{{background:#2c974b;text-decoration:none}}
    main{{padding:32px 0 60px;display:grid;grid-template-columns:1fr 300px;gap:24px;align-items:start}}
    @media(max-width:700px){{main{{grid-template-columns:1fr}}}}
    .main-col{{display:flex;flex-direction:column;gap:20px}}
    .sidebar{{display:flex;flex-direction:column;gap:16px}}
    .card{{background:#fff;border:1px solid #e1e4e8;border-radius:10px;padding:20px}}
    .card h2{{font-size:15px;font-weight:600;margin-bottom:14px;color:#24292f;padding-bottom:10px;border-bottom:1px solid #e1e4e8}}
    .card h3{{font-size:14px;font-weight:600;color:#24292f;margin:0 0 4px}}
    pre{{background:#f6f8fa;border:1px solid #e1e4e8;border-radius:6px;padding:14px;font-size:13px;overflow-x:auto;line-height:1.5}}
    code{{font-family:'SFMono-Regular',Consolas,monospace;font-size:13px}}
    .inline-code{{background:#f6f8fa;border:1px solid #e1e4e8;border-radius:4px;padding:1px 6px;font-family:monospace;font-size:12px;color:#24292f}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{text-align:left;padding:8px 12px;background:#f6f8fa;border:1px solid #e1e4e8;font-weight:600;color:#57606a;font-size:12px}}
    td{{padding:8px 12px;border:1px solid #e1e4e8;color:#24292f}}
    td.mono{{font-family:monospace;font-weight:700;color:#0969da}}
    .tag-green{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:#dafbe1;color:#1a7f37}}
    .faq-item{{margin-bottom:16px}}
    .faq-item:last-child{{margin-bottom:0}}
    .faq-item h3{{font-size:14px;font-weight:600;color:#24292f;margin-bottom:4px}}
    .faq-item p{{font-size:13px;color:#57606a;line-height:1.6}}
    .kw-list{{display:flex;flex-wrap:wrap;gap:6px}}
    .kw{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;color:#0969da;border:1px solid #c8e1ff;background:#f1f8ff}}
    .kw:hover{{background:#ddf4ff;text-decoration:none}}
    .about-text{{font-size:13px;color:#57606a;line-height:1.7}}
    .steps{{display:flex;flex-direction:column;gap:10px;counter-reset:steps}}
    .step{{display:flex;gap:12px;align-items:flex-start;font-size:13px;color:#57606a}}
    .step-num{{background:#0969da;color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;margin-top:1px}}
    footer{{background:#f6f8fa;border-top:1px solid #e1e4e8;padding:20px 0;font-size:12px;color:#57606a;text-align:center}}
  </style>
</head>
<body>

<header>
  <div class="wrap">
    <div class="header-inner">
      <a href="{pages_url}" class="logo">&#9679; {username}</a>
      <nav>
        <a href="{pages_url}">Toate magazinele</a>
        <a href="https://github.com/{username}/{repo_slug}">GitHub</a>
        <a href="https://{SHOPILO_DOMAIN}">{SHOPILO_DOMAIN}</a>
      </nav>
    </div>
  </div>
</header>

<div class="hero">
  <div class="wrap">
    <div class="breadcrumb">
      <a href="https://github.com/{username}">{username}</a> /
      <a href="https://github.com/{username}/{repo_slug}">{repo_slug}</a>
    </div>
    <div class="repo-title">
      <span class="repo-icon">&#128196;</span>
      <h1><a href="{pages_url}">{username}</a> / {repo_slug}</h1>
    </div>
    <p class="hero-desc">Script Python open-source pentru fetch automat de <strong>coduri de reducere {store_name}</strong> de pe <a href="{shopilo_url}">{SHOPILO_DOMAIN}</a>. Returneaza cupoane active in format JSON.</p>
    <div class="badges">
      <span class="badge badge-blue">Python 3.8+</span>
      <span class="badge badge-green">MIT License</span>
      <span class="badge">requests + beautifulsoup4</span>
      <span class="badge">{SHOPILO_DOMAIN}</span>
    </div>
    <a href="{shopilo_url}" class="cta">
      &#128279; Date live {store_name} pe {SHOPILO_DOMAIN}
    </a>
  </div>
</div>

<div class="wrap">
<main>
  <div class="main-col">

    <div class="card">
      <h2>Instalare si utilizare rapida</h2>
      <pre><code># Instaleaza dependentele
pip install requests beautifulsoup4

# Cloneaza repo-ul
git clone https://github.com/{username}/{repo_slug}
cd {repo_slug}

# Ruleaza scriptul
python fetch.py</code></pre>
      <p style="font-size:13px;color:#57606a;margin-top:12px">Sau instaleaza ca modul npm:</p>
      <pre><code>npm install {repo_slug}

# Foloseste in Node.js
const {{ fetchCoupons }} = require('{repo_slug}');
fetchCoupons().then(data => console.log(data));</code></pre>
    </div>

    <div class="card">
      <h2>Output fetch.py — {MONTH_STR} {YEAR_STR}</h2>
      <pre><code>[
  {{
    "store": "{store_name}",
    "code": "{example_code}",
    "discount": "{example_discount}",
    "description": "{example_desc}",
    "expires": "{EXPIRY_DATE}",
    "source": "{shopilo_url}",
    "fetched_at": "{YEAR_STR}-{NOW.month:02d}-01T09:12:33"
  }}
]</code></pre>
      <table style="margin-top:14px">
        <thead>
          <tr>
            <th>Reducere</th><th>Descriere</th><th>Sursa</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{example_discount}</td>
            <td>{example_desc}</td>
            <td><a href="{shopilo_url}">{SHOPILO_DOMAIN}</a></td>
          </tr>
        </tbody>
      </table>
      <p style="font-size:12px;color:#57606a;margin-top:12px">
        Codurile active si verificate sunt disponibile pe
        <a href="{shopilo_url}" style="font-weight:600">{SHOPILO_DOMAIN}/magazin/{shopilo_slug}</a>
      </p>
    </div>

    <div class="card">
      <h2>Cum functioneaza scriptul</h2>
      <div class="steps">
        <div class="step"><span class="step-num">1</span><span>Face un GET request catre pagina publica <span class="inline-code">{shopilo_url}</span> cu un User-Agent standard</span></div>
        <div class="step"><span class="step-num">2</span><span>Parseaza HTML-ul cu <span class="inline-code">BeautifulSoup</span> si selecteaza elementele cu selectori CSS (<span class="inline-code">.coupon-item</span>, <span class="inline-code">[data-coupon]</span>)</span></div>
        <div class="step"><span class="step-num">3</span><span>Extrage per cupon: codul (<span class="inline-code">data-code</span>), reducerea, descrierea si data de expirare</span></div>
        <div class="step"><span class="step-num">4</span><span>Returneaza lista ca JSON in stdout — gata de integrat in orice pipeline, bot sau extensie</span></div>
      </div>
    </div>

    <div class="card">
      <h2>Intrebari frecvente — cod reducere {store_name}</h2>
      <div class="faq-item">
        <h3>Ce returneaza scriptul fetch.py?</h3>
        <p>Un array JSON cu obiectele cupoanelor active: codul de reducere {store_name}, procentul de discount, descrierea, data de expirare si URL-ul sursa de pe {SHOPILO_DOMAIN}.</p>
      </div>
      <div class="faq-item">
        <h3>Cat de des pot rula scriptul?</h3>
        <p>Recomandam maxim o rulare la 6 ore. Datele de pe <a href="{shopilo_url}">{SHOPILO_DOMAIN}</a> se actualizeaza zilnic, deci un cron la cateva ore este suficient.</p>
      </div>
      <div class="faq-item">
        <h3>Functioneaza si ca modul npm?</h3>
        <p>Da. <span class="inline-code">npm install {repo_slug}</span> instaleaza versiunea JavaScript care foloseste <span class="inline-code">fetch()</span> nativ din Node 18+ si exporta aceeasi structura JSON.</p>
      </div>
      <div class="faq-item">
        <h3>Unde gasesc toate cupoanele {store_name} active?</h3>
        <p>Lista completa si actualizata zilnic pe <a href="{shopilo_url}">{SHOPILO_DOMAIN}/magazin/{shopilo_slug}</a> — sursa de date a acestui script.</p>
      </div>
      <div class="faq-item">
        <h3>Pot combina mai multe coduri de reducere {store_name}?</h3>
        <p>De obicei un singur voucher {store_name} per comanda. Conditiile complete sunt afisate pe fiecare cupon pe {SHOPILO_DOMAIN}.</p>
      </div>
    </div>

  </div>

  <div class="sidebar">

    <div class="card">
      <h2>Despre {store_name}</h2>
      <p class="about-text">{store_name} este unul dintre magazinele online populare. Scriptul extrage automat codurile de reducere {store_name} disponibile pe <a href="{shopilo_url}">{SHOPILO_DOMAIN}</a>.</p>
    </div>

    <div class="card">
      <h2>Cum folosesti un cod {store_name}</h2>
      <div class="steps">
        <div class="step"><span class="step-num">1</span><span>Copiaza codul din output-ul scriptului</span></div>
        <div class="step"><span class="step-num">2</span><span>Adauga produsele dorite in cosul {store_name}</span></div>
        <div class="step"><span class="step-num">3</span><span>La checkout, introdu codul in campul "Voucher" sau "Cod promotional"</span></div>
        <div class="step"><span class="step-num">4</span><span>Apasa "Aplica" — reducerea se aplica automat</span></div>
      </div>
    </div>

    <div class="card">
      <h2>Cuvinte cheie</h2>
      <div class="kw-list">
        <a href="{shopilo_url}" class="kw">cod reducere {store_name}</a>
        <a href="{shopilo_url}" class="kw">voucher {store_name}</a>
        <a href="{shopilo_url}" class="kw">cupon {store_name}</a>
        <a href="{shopilo_url}" class="kw">cod promotional {store_name}</a>
        <a href="{shopilo_url}" class="kw">reduceri {store_name}</a>
        <a href="{shopilo_url}" class="kw">{store_name} discount</a>
      </div>
    </div>

  </div>
</main>
</div>

<footer>
  Script open-source. Date de pe <a href="{shopilo_url}">{SHOPILO_DOMAIN}</a> &mdash;
  <a href="{pages_url}">Toate magazinele</a>
</footer>

</body>
</html>
"""


def make_org_profile_readme(stores, username, config):
    """Genereaza profile/README.md pentru repo-ul .github (apare pe github.com/username)."""
    domain    = config["domain"]
    pages_url = f"https://{username}.github.io"
    n         = len(stores)

    rows = ""
    for i, (name, slug, shopilo_slug, code, disc, desc, date) in enumerate(stores, 1):
        shopilo_url = f"https://{domain}/magazin/{shopilo_slug}"
        rows += f"| {i} | [{name}](https://github.com/{username}/{slug}) | [{slug}](https://github.com/{username}/{slug}) | [{domain}/magazin/{shopilo_slug}]({shopilo_url}) |\n"

    return f"""# {username}

Colectie de **{n} scripturi Python** open-source pentru fetch automat de coduri de reducere de pe [{domain}](https://{domain}).

**Pagina principala:** [{pages_url}]({pages_url})

Fiecare repo contine:
- `fetch.py` — script Python care returneaza cupoane active in format JSON
- `index.js` — modul Node.js echivalent
- `package.json` — instalabil via `npm i {username.split("-")[0]}-reducere-[magazin]`
- `index.html` — pagina GitHub Pages cu detalii si instructiuni

---

## Magazine disponibile ({n})

| # | Magazin | Repo | Date live |
|---|---------|------|-----------|
{rows}
---

Date sursa: [{domain}](https://{domain}) | Licenta: MIT | Actualizat: {MONTH_STR} {YEAR_STR}
"""


def make_org_index_html(stores, username, config):
    """Genereaza pagina dark-theme pentru username.github.io din datele stores."""
    domain     = config["domain"]
    hero_h1    = config.get("hero_h1",    f"Coduri de reducere - {domain}")
    hero_desc  = config.get("hero_desc",  f"Scripturi Python open-source pentru coduri de reducere de pe {domain}.")
    btn_prefix = config.get("btn_shop_prefix", "Cod reducere")
    n_stores   = len(stores)
    lang       = config.get("lang", "ro")

    OCTOCAT = '<svg height="13" width="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
    GH_LOGO   = '<svg height="24" viewBox="0 0 16 16" width="24" fill="#e6edf3"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'

    cards_html = ""
    for name, slug, shopilo_slug, code, disc, desc, date in stores:
        shopilo_url = f"https://{domain}/magazin/{shopilo_slug}"
        cards_html += f"""
    <div class="card">
      <div class="card-head">
        <div class="card-name">{name}</div>
        <div class="card-slug">{slug}</div>
      </div>
      <div class="npm-box"><span class="npm-prompt">$</span>npm i {slug}</div>
      <div class="card-btns">
        <a href="https://github.com/{username}/{slug}" class="btn btn-gh" target="_blank" rel="noopener">
          {OCTOCAT}GitHub
        </a>
        <a href="{shopilo_url}" class="btn btn-shop" target="_blank" rel="noopener">{btn_prefix} {name}</a>
      </div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{username} — {hero_h1}</title>
  <meta name="description" content="{hero_desc}">
  <meta name="robots" content="index, follow">
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#0d1117;color:#e6edf3;line-height:1.5}}
    a{{color:#58a6ff;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    .wrap{{max-width:1200px;margin:0 auto;padding:0 24px}}
    header{{background:#161b22;border-bottom:1px solid #30363d;padding:14px 0}}
    .hdr{{display:flex;justify-content:space-between;align-items:center}}
    .logo{{display:flex;align-items:center;gap:10px;font-weight:600;font-size:15px;color:#e6edf3;text-decoration:none}}
    nav a{{font-size:13px;color:#8b949e;margin-left:20px}}
    nav a:hover{{color:#e6edf3;text-decoration:none}}
    .hero{{padding:56px 0 40px}}
    .hero-eyebrow{{font-size:12px;color:#8b949e;font-family:'SFMono-Regular',Consolas,monospace;margin-bottom:12px}}
    .hero h1{{font-size:36px;font-weight:700;margin-bottom:16px;line-height:1.2}}
    .hero-desc{{font-size:16px;color:#8b949e;max-width:620px;margin-bottom:24px}}
    .badges{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:28px}}
    .badge{{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500;border:1px solid}}
    .badge-blue{{background:rgba(31,111,235,.1);border-color:#1f6feb;color:#79c0ff}}
    .badge-green{{background:rgba(35,134,54,.1);border-color:#238636;color:#56d364}}
    .badge-gray{{background:#21262d;border-color:#30363d;color:#8b949e}}
    .code-block{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px 24px;font-family:'SFMono-Regular',Consolas,monospace;font-size:13px;line-height:1.8;max-width:560px}}
    .c-comment{{color:#8b949e}}
    .c-cmd{{color:#e6edf3}}
    .stats{{background:#161b22;border-top:1px solid #30363d;border-bottom:1px solid #30363d;padding:14px 0;font-size:13px;color:#8b949e}}
    .stats-inner{{display:flex;flex-wrap:wrap;gap:24px}}
    .stat{{display:flex;align-items:center;gap:6px}}
    .stat-val{{color:#e6edf3;font-weight:600}}
    section{{padding:40px 0 60px}}
    .sec-hdr{{display:flex;align-items:center;gap:12px;margin-bottom:24px}}
    .sec-title{{font-size:18px;font-weight:600}}
    .sec-count{{background:#21262d;border:1px solid #30363d;border-radius:20px;padding:2px 10px;font-size:12px;color:#8b949e}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px}}
    .card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;transition:.15s}}
    .card:hover{{border-color:#388bfd;box-shadow:0 0 0 3px rgba(56,139,253,.1)}}
    .card-head{{margin-bottom:12px}}
    .card-name{{font-size:15px;font-weight:600;color:#e6edf3;margin-bottom:2px}}
    .card-slug{{font-size:11px;color:#8b949e;font-family:'SFMono-Regular',Consolas,monospace}}
    .npm-box{{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:7px 11px;font-family:'SFMono-Regular',Consolas,monospace;font-size:12px;color:#e6edf3;margin-bottom:12px}}
    .npm-prompt{{color:#3fb950;margin-right:6px;user-select:none}}
    .card-btns{{display:flex;gap:8px}}
    .btn{{display:inline-flex;align-items:center;gap:5px;padding:6px 14px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;transition:.15s;white-space:nowrap}}
    .btn-gh{{background:#238636;color:#fff;border:1px solid rgba(240,246,252,.1)}}
    .btn-gh:hover{{background:#2ea043;text-decoration:none}}
    .btn-shop{{background:transparent;color:#e6edf3;border:1px solid #30363d}}
    .btn-shop:hover{{background:#21262d;text-decoration:none;border-color:#8b949e}}
    footer{{background:#161b22;border-top:1px solid #30363d;padding:20px 0;font-size:12px;color:#8b949e;text-align:center}}
    @media(max-width:600px){{.hero h1{{font-size:26px}}.stats-inner{{gap:14px}}}}
  </style>
</head>
<body>

<header>
  <div class="wrap">
    <div class="hdr">
      <a href="/" class="logo">{GH_LOGO}{username}</a>
      <nav>
        <a href="https://github.com/{username}" target="_blank" rel="noopener">GitHub</a>
        <a href="https://{domain}" target="_blank" rel="noopener">{domain}</a>
      </nav>
    </div>
  </div>
</header>

<div class="wrap">
  <div class="hero">
    <div class="hero-eyebrow">github.com / {username}</div>
    <h1>{hero_h1}</h1>
    <p class="hero-desc">{hero_desc}</p>
    <div class="badges">
      <span class="badge badge-blue">Python 3.8+</span>
      <span class="badge badge-green">MIT License</span>
      <span class="badge badge-gray">npm disponibil</span>
      <span class="badge badge-gray">Date live {domain}</span>
    </div>
    <div class="code-block">
      <span class="c-comment"># Instaleaza dependentele</span><br>
      <span class="c-cmd">pip install requests beautifulsoup4</span><br><br>
      <span class="c-comment"># Fetch automat coduri de reducere</span><br>
      <span class="c-cmd">git clone https://github.com/{username}/cod-reducere-[magazin]</span><br>
      <span class="c-cmd">python fetch.py</span>
    </div>
  </div>
</div>

<div class="stats">
  <div class="wrap">
    <div class="stats-inner">
      <span class="stat"><span class="stat-val">{n_stores}</span> magazine</span>
      <span class="stat">Python <span class="stat-val">3.8+</span></span>
      <span class="stat">Sursa date: <span class="stat-val">{domain}</span></span>
      <span class="stat">npm i <span class="stat-val">cod-reducere-[magazin]</span></span>
      <span class="stat">Licenta: <span class="stat-val">MIT</span></span>
    </div>
  </div>
</div>

<div class="wrap">
  <section>
    <div class="sec-hdr">
      <span class="sec-title">Magazine</span>
      <span class="sec-count">{n_stores}</span>
    </div>
    <div class="grid">
{cards_html}
    </div>
  </section>
</div>

<footer>
  Script open-source &mdash; Date de pe <a href="https://{domain}">{domain}</a> &mdash;
  <a href="https://github.com/{username}">GitHub</a>
</footer>

</body>
</html>"""


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Creeaza repo-urile GitHub pentru Shopilo (multi-country)"
    )
    parser.add_argument("--token",       required=True, help="GitHub Personal Access Token")
    parser.add_argument("--username",    required=True, help="GitHub username/org (ex: shopilo-ro)")
    parser.add_argument("--country",     default="ro",  help="Codul tarii: ro, de, fr, es, it (default: ro)")
    parser.add_argument("--dry-run",     action="store_true", help="Simuleaza fara sa creeze nimic")
    parser.add_argument("--only",        help="Creeaza doar repo-ul specificat (slug)")
    parser.add_argument("--update-html", action="store_true", help="Actualizeaza doar index.html cu luna curenta")
    args = parser.parse_args()

    # ── Incarca config tara ──────────────────────────────────────────────────
    country_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"shopilo.{args.country}")
    if not os.path.isdir(country_dir):
        print(f"EROARE: Directorul '{country_dir}' nu exista.")
        print(f"Creeaza shopilo.{args.country}/stores.py cu COUNTRY_CONFIG si STORES.")
        sys.exit(1)

    stores_path = os.path.join(country_dir, "stores.py")
    spec = importlib.util.spec_from_file_location("country_stores", stores_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    config = mod.COUNTRY_CONFIG
    global SHOPILO_DOMAIN, MONTH_STR
    SHOPILO_DOMAIN = config["domain"]
    MONTH_STR      = config["months"][NOW.month]
    stores_all     = mod.STORES

    # ── Autentificare ────────────────────────────────────────────────────────
    api = GitHubAPI(args.token, args.username)
    r = api.session.get("https://api.github.com/user")
    if r.status_code != 200:
        print(f"Token invalid: {r.json().get('message')}")
        sys.exit(1)
    print(f"Autentificat ca: {r.json()['login']} | Tara: {args.country} | Domain: {SHOPILO_DOMAIN}\n")

    stores = stores_all
    if args.only:
        stores = [s for s in stores_all if s[1] == args.only]
        if not stores:
            print(f"Nu am gasit repo-ul: {args.only}")
            sys.exit(1)

    # ── 0. Mod update-html (folosit de GitHub Action lunar) ──────────────────
    if args.update_html:
        print(f"Update index.html pentru {len(stores)} magazine ({MONTH_STR} {YEAR_STR})...\n")
        for i, (name, slug, shopilo_slug, ex_code, ex_disc, ex_desc, ex_date) in enumerate(stores, 1):
            print(f"[{i:02d}/{len(stores)}] {slug}...", end=" ", flush=True)
            html = make_index_html(name, slug, shopilo_slug, ex_code, ex_disc, ex_desc, ex_date, args.username)
            ok = api.update_file(slug, "index.html", html, f"Update {MONTH_STR} {YEAR_STR}")
            print("OK" if ok else "EROARE")
            time.sleep(0.5)
        print("\nGata! Toate paginile au fost actualizate.")
        sys.exit(0)

    # ── 1. Repo-uri individuale ──────────────────────────────────────────────
    print(f"Creez {len(stores)} repo-uri individuale...\n")

    for i, (name, slug, shopilo_slug, ex_code, ex_disc, ex_desc, ex_date) in enumerate(stores, 1):
        print(f"[{i:02d}/{len(stores)}] {slug}...", end=" ", flush=True)

        if args.dry_run:
            print("DRY RUN - skip")
            continue

        ok, msg = api.create_repo(slug, f"Fetch automat de coduri de reducere {name} de pe {SHOPILO_DOMAIN}")
        if not ok:
            print(f"EROARE: {msg}")
            continue
        print(f"repo {msg}", end=" | ", flush=True)

        time.sleep(0.5)

        readme     = make_readme(name, slug, shopilo_slug, ex_code, ex_disc, ex_desc, ex_date, args.username)
        fetch      = make_fetch_py(name, slug, shopilo_slug, args.username)
        index_js   = make_index_js(name, slug, shopilo_slug, args.username)
        pkg        = make_package_json(name, slug, shopilo_slug, args.username)
        req        = make_requirements()
        index_html = make_index_html(name, slug, shopilo_slug, ex_code, ex_disc, ex_desc, ex_date, args.username)

        files = [
            ("README.md",        readme,      "Add README"),
            ("index.html",       index_html,  "Add GitHub Pages store page"),
            ("fetch.py",         fetch,       "Add Python fetch script"),
            ("index.js",         index_js,    "Add npm module"),
            ("package.json",     pkg,         "Add package.json"),
            ("requirements.txt", req,         "Add requirements"),
        ]

        all_ok = True
        for fname, content, commit_msg in files:
            if not api.create_file(slug, fname, content, commit_msg):
                print(f"EROARE la {fname}", end=" ")
                all_ok = False
            time.sleep(0.3)

        time.sleep(0.5)
        api.enable_pages(slug)

        print("OK" if all_ok else "PARTIAL")
        time.sleep(1.2)

    # ── 2. Repo GitHub Pages principal (username.github.io) ──────────────────
    pages_repo = f"{args.username}.github.io"
    print(f"\nCreez pagina GitHub Pages: {pages_repo}...", end=" ", flush=True)

    if not args.dry_run:
        ok, msg = api.create_repo(pages_repo, f"Shopilo Dev — Scripturi Python pentru coduri de reducere ({SHOPILO_DOMAIN})")
        print(f"repo {msg}", end=" | ", flush=True)

        time.sleep(0.5)

        # Genereaza org page din date (nu citeste din disk)
        org_html = make_org_index_html(stores_all, args.username, config)
        if api.create_file(pages_repo, "index.html", org_html, "Add GitHub Pages index"):
            print("index.html OK", end=" | ")

        # Uploadeaza scriptul de update si GitHub Action
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "create_repos.py")
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
        if api.create_file(pages_repo, "create_repos.py", script_content, "Add update script"):
            print("create_repos.py OK", end=" | ")

        workflow_yml = make_workflow_yml(args.username, args.country)
        if api.create_file(pages_repo, ".github/workflows/monthly-update.yml", workflow_yml, "Add monthly update action"):
            print("GitHub Action OK", end=" | ")

        time.sleep(1)
        api.enable_pages(pages_repo)
        print("Pages activat")
    else:
        print("DRY RUN - skip")

    # ── 3. Org profile README (.github repo → github.com/username) ───────────
    profile_repo = ".github"
    print(f"\nCreez org profile: {profile_repo}...", end=" ", flush=True)

    if not args.dry_run:
        ok, msg = api.create_repo(profile_repo, f"Profil organizatie {args.username}")
        print(f"repo {msg}", end=" | ", flush=True)
        time.sleep(0.5)

        profile_readme = make_org_profile_readme(stores_all, args.username, config)
        if api.create_file(profile_repo, "profile/README.md", profile_readme, "Add org profile README"):
            print("profile/README.md OK")
        else:
            print("EROARE profile/README.md")
    else:
        print("DRY RUN - skip")

    print(f"""
Gata!
  Org profile:  https://github.com/{args.username}
  GitHub Pages: https://{args.username}.github.io
  Magazine:     {len(stores_all)} ({SHOPILO_DOMAIN})

GitHub Pages poate dura 1-2 minute sa fie live dupa activare.
""")


if __name__ == "__main__":
    main()
