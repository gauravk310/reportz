"""Webpage analyser and interactive multi-section HTML report generator.

Collects passive web intelligence across security, SEO, performance,
accessibility, technologies, and DNS, producing an advanced SPA-style report.
"""

from __future__ import annotations

import base64
import datetime
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import socket
import ssl
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse
import webbrowser

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Optional BeautifulSoup parser fallback
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    BeautifulSoup = None  # type: ignore
    HAS_BS4 = False

# Optional DNS resolver
try:
    import dns.resolver as dns_resolver
    HAS_DNS = True
except ImportError:
    HAS_DNS = False

from reportz.core import BaseReport
from reportz.exceptions import ReportSaveError
from reportz.utils import open_in_browser, resolve_report_path

log = logging.getLogger("reportz.web")


# ══════════════════════════════════════════════════════════════════════════════
#  CSS THEMES & ASSETS
# ══════════════════════════════════════════════════════════════════════════════

def get_shared_css(dark_mode: bool = True) -> str:
    """Return CSS definitions tailored for the specified color mode."""
    if dark_mode:
        vars_css = """
  --bg:#080b10;
  --surface:#0e1319;
  --surface2:#141b24;
  --border:#1e2a38;
  --border2:#263040;
  --text:#d4dfe8;
  --muted:#4e6070;
  --accent:#00d4ff;
  --accent2:#7c5cfc;
  --good:#00e676;
  --warn:#ffab00;
  --danger:#ff3d57;
  --chart-grid:#1e2a38;
  --chart-text:#4e6070;
"""
    else:
        vars_css = """
  --bg:#f8fafc;
  --surface:#ffffff;
  --surface2:#f1f5f9;
  --border:#e2e8f0;
  --border2:#cbd5e1;
  --text:#0f172a;
  --muted:#64748b;
  --accent:#0284c7;
  --accent2:#6366f1;
  --good:#16a34a;
  --warn:#d97706;
  --danger:#dc2626;
  --chart-grid:#e2e8f0;
  --chart-text:#64748b;
"""

    return f"""@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{{vars_css}
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif;
}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;padding:32px 36px;animation:fadeIn .25s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
.page-header{{margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:14px}}
.page-header-icon{{width:44px;height:44px;background:linear-gradient(135deg,rgba(0,212,255,.15),rgba(124,92,252,.15));border:1px solid var(--border2);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}}
.page-header h1{{font-size:20px;font-weight:800;color:var(--text)}}
.page-header .sub{{font-size:12px;color:var(--muted);margin-top:2px;font-family:var(--mono)}}
.score-badge{{margin-left:auto;display:flex;flex-direction:column;align-items:flex-end}}
.score-num{{font-size:32px;font-weight:800;line-height:1;font-family:var(--mono)}}
.score-lbl{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono)}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:20px}}
.card-header{{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}}
.card-title{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-family:var(--mono)}}
.card-body{{padding:20px}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.stat-card{{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:18px;position:relative;overflow:hidden}}
.stat-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent-color,var(--accent))}}
.stat-val{{font-size:28px;font-weight:800;font-family:var(--mono);color:var(--accent-color,var(--accent));line-height:1}}
.stat-label{{font-size:11px;color:var(--muted);margin-top:6px;text-transform:uppercase;letter-spacing:.08em;font-family:var(--mono)}}
.table-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead th{{padding:10px 14px;background:var(--surface2);font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-family:var(--mono);border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}}
tbody td{{padding:11px 14px;border-bottom:1px solid var(--border);vertical-align:middle;line-height:1.5}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:var(--surface2)}}
.badge{{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;font-family:var(--mono);white-space:nowrap}}
.badge-good{{background:rgba(0,230,118,.12);color:#00e676;border:1px solid rgba(0,230,118,.25)}}
.badge-bad{{background:rgba(255,61,87,.12);color:#ff6b82;border:1px solid rgba(255,61,87,.25)}}
.badge-warn{{background:rgba(255,171,0,.12);color:#ffab00;border:1px solid rgba(255,171,0,.25)}}
.badge-critical{{background:rgba(255,61,87,.2);color:#ff3d57;border:1px solid rgba(255,61,87,.5)}}
.badge-high{{background:rgba(255,100,50,.12);color:#ff7043;border:1px solid rgba(255,100,50,.3)}}
.badge-medium{{background:rgba(255,171,0,.12);color:#ffab00;border:1px solid rgba(255,171,0,.3)}}
.badge-low{{background:rgba(0,212,255,.1);color:#00d4ff;border:1px solid rgba(0,212,255,.2)}}
.badge-info{{background:rgba(124,92,252,.12);color:#a78bfa;border:1px solid rgba(124,92,252,.25)}}
.tech-tag{{display:inline-block;background:var(--surface2);border:1px solid var(--border2);color:var(--accent2);border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600;margin:3px;font-family:var(--mono)}}
.info-row{{display:flex;gap:16px;align-items:flex-start;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px}}
.info-row:last-child{{border-bottom:none}}
.info-key{{color:var(--muted);min-width:160px;flex-shrink:0;font-size:11px;font-family:var(--mono);padding-top:2px}}
.info-val{{color:var(--text);word-break:break-all}}
code{{background:var(--surface2);border:1px solid var(--border2);padding:1px 6px;border-radius:4px;font-size:12px;font-family:var(--mono);color:var(--accent)}}
.issue-list{{list-style:none}}
.issue-list li{{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px;line-height:1.5}}
.issue-list li:last-child{{border-bottom:none}}
.issue-list li .icon{{flex-shrink:0;font-size:14px}}
.progress-wrap{{background:var(--surface2);border-radius:99px;height:5px;overflow:hidden;margin-top:8px}}
.progress-bar{{height:100%;border-radius:99px;background:var(--accent-color,var(--accent));transition:width 1s cubic-bezier(.4,0,.2,1)}}
.alert{{border-radius:10px;padding:14px 18px;margin-bottom:20px;display:flex;align-items:flex-start;gap:14px;border:1px solid}}
.alert-icon{{font-size:20px;flex-shrink:0}}
.alert-title{{font-size:13px;font-weight:700}}
.alert-sub{{font-size:12px;color:var(--muted);margin-top:2px;font-family:var(--mono)}}
.alert-critical{{background:rgba(255,61,87,.08);border-color:rgba(255,61,87,.3)}}
.alert-high{{background:rgba(255,112,67,.08);border-color:rgba(255,112,67,.3)}}
.alert-medium{{background:rgba(255,171,0,.08);border-color:rgba(255,171,0,.3)}}
.alert-good{{background:rgba(0,230,118,.08);border-color:rgba(0,230,118,.3)}}
.section-label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);font-family:var(--mono);margin:22px 0 10px}}
.section-label:first-child{{margin-top:0}}
.footer{{padding-top:24px;margin-top:36px;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--muted);font-family:var(--mono)}}
.footer a{{color:var(--accent);text-decoration:none;display:inline-flex;align-items:center;gap:4px}}
.footer a:hover{{text-decoration:underline}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:var(--bg)}}
::-webkit-scrollbar-thumb{{background:var(--border2);border-radius:99px}}
"""

CHARTJS = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>'


# ══════════════════════════════════════════════════════════════════════════════
#  FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _score_color(score: int) -> str:
    if score >= 80:
        return "#00e676"
    if score >= 60:
        return "#ffab00"
    if score >= 40:
        return "#ff7043"
    return "#ff3d57"


def _score_label(score: int) -> str:
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Needs Work"
    if score >= 40:
        return "Poor"
    return "Critical"


def _bool_badge(val: bool, t: str = "✓ Yes", f: str = "✗ No") -> str:
    cls = "badge-good" if val else "badge-bad"
    return f'<span class="badge {cls}">{t if val else f}</span>'


def _sev_badge(sev: str) -> str:
    m = {
        "critical": "badge-critical",
        "high": "badge-high",
        "medium": "badge-medium",
        "low": "badge-low",
    }
    return f'<span class="badge {m.get(sev.lower(), "badge-low")}">{sev.capitalize()}</span>'


def _status_badge(code: int) -> str:
    cls = (
        "badge-good"
        if 200 <= code < 300
        else ("badge-warn" if 300 <= code < 400 else "badge-bad")
    )
    return f'<span class="badge {cls}">{code}</span>'


def _esc(s: Any) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _section_shell(
    title: str, dark_mode: bool = True, extra_css: str = "", extra_head: str = ""
) -> Tuple[str, str]:
    """Return (open_html, close_html) for a section page."""
    css = get_shared_css(dark_mode=dark_mode)
    open_html = f"""<!DOCTYPE html>
<html lang="en" data-theme="{"dark" if dark_mode else "light"}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{_esc(title)}</title>
{extra_head}
<style>{css}{extra_css}</style>
</head>
<body>
"""
    close_html = """
<footer class="footer">
  <div>WebAnalyzer &middot; Automated Passive Telemetry</div>
  <div>
    <span>Connect Author :</span>
    <a href="https://github.com/gauravk310" target="_blank" rel="noopener noreferrer">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="display:inline-block;vertical-align:-2px;margin-right:4px;"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>Gaurav Kadam
    </a>
  </div>
</footer>
</body>
</html>
"""
    return open_html, close_html


# ══════════════════════════════════════════════════════════════════════════════
#  SCAN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_web_scan(url: str, delay: int = 0) -> Dict[str, Any]:
    """Run all passive checks and return comprehensive telemetry data dictionary."""
    if not url:
        raise ValueError("URL cannot be empty.")

    target_url = url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (compatible; WebAnalyzer/2.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
    })

    def _get(target: str, timeout: int = 10, allow_redirects: bool = True) -> Optional[requests.Response]:
        try:
            return session.get(
                target, timeout=timeout, allow_redirects=allow_redirects, verify=False
            )
        except Exception as e:
            log.debug("GET %s failed: %s", target, e)
            return None

    # 1. Fetch
    log.info("Fetching %s ...", target_url)
    if delay > 0:
        log.info("Waiting %d seconds before fetching...", delay)
        time.sleep(delay)

    t0 = time.monotonic()
    resp = _get(target_url)
    if resp is None:
        # Retry with http:// if https failed
        if target_url.startswith("https://"):
            fallback_url = "http://" + target_url[8:]
            log.info("Retrying with %s ...", fallback_url)
            resp = _get(fallback_url)

    if resp is None:
        raise RuntimeError(f"Cannot reach {target_url}")

    ttfb = round((time.monotonic() - t0) * 1000, 1)
    html = resp.text
    if HAS_BS4:
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
    else:
        soup = None

    headers = dict(resp.headers)
    final_url = resp.url
    status_code = resp.status_code
    page_size_kb = round(len(resp.content) / 1024, 1)
    redirect_chain = [r.url for r in resp.history] + [final_url]
    parsed = urllib.parse.urlparse(final_url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    scheme = parsed.scheme or "http"
    html_lower = html.lower()

    def _resolve(host: str) -> str:
        try:
            return socket.gethostbyname(host.split(":")[0])
        except Exception:
            return "N/A"

    ip = _resolve(domain)
    robots = _get(f"{scheme}://{domain}/robots.txt")
    sitemap = _get(f"{scheme}://{domain}/sitemap.xml")
    has_robots = bool(robots and robots.status_code == 200)
    has_sitemap = bool(sitemap and sitemap.status_code == 200)
    fav_tag = (
        soup.find("link", rel=lambda r: r and "icon" in " ".join(r).lower())
        if soup else None
    )

    # 2. Security
    log.info("Security checks ...")
    sec_issues: List[Dict[str, str]] = []
    sec: Dict[str, Any] = {}
    is_https = scheme == "https"
    sec["https"] = is_https
    if not is_https:
        sec_issues.append({
            "severity": "critical",
            "issue": "HTTPS not enabled",
            "detail": "Site served over unencrypted HTTP.",
        })

    # SSL
    ssl_info: Dict[str, Any] = {}
    if is_https:
        try:
            ctx = ssl.create_default_context()
            host_clean = domain.split(":")[0]
            with ctx.wrap_socket(socket.socket(), server_hostname=host_clean) as s:
                s.settimeout(5)
                s.connect((host_clean, 443))
                cert = s.getpeercert()
                not_after = datetime.datetime.strptime(
                    cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
                )
                days_left = (not_after - datetime.datetime.utcnow()).days
                ssl_info = {
                    "issuer": dict(x[0] for x in cert.get("issuer", [])).get(
                        "organizationName", "?"
                    ),
                    "subject": dict(x[0] for x in cert.get("subject", [])).get(
                        "commonName", "?"
                    ),
                    "not_after": cert["notAfter"],
                    "not_before": cert.get("notBefore", "?"),
                    "tls_version": s.version(),
                    "days_left": days_left,
                    "valid": days_left > 0,
                }
                if days_left < 30:
                    sec_issues.append({
                        "severity": "high",
                        "issue": f"SSL cert expires soon ({days_left} days left)",
                        "detail": cert["notAfter"],
                    })
        except Exception as e:
            ssl_info = {"error": str(e)}
            sec_issues.append({
                "severity": "medium",
                "issue": "SSL validation notice",
                "detail": str(e),
            })
    sec["ssl"] = ssl_info

    # Security headers
    _hdrs = {
        "Strict-Transport-Security": ("hsts", "high", "HSTS header missing"),
        "Content-Security-Policy": ("csp", "high", "CSP header missing"),
        "X-Frame-Options": ("xframe", "medium", "X-Frame-Options missing"),
        "Referrer-Policy": ("ref", "low", "Referrer-Policy missing"),
        "Permissions-Policy": ("perms", "low", "Permissions-Policy missing"),
        "X-Content-Type-Options": ("xcto", "medium", "X-Content-Type-Options missing"),
        "X-XSS-Protection": ("xxss", "low", "X-XSS-Protection missing"),
    }
    for h, (key, sev, msg) in _hdrs.items():
        present = any(k.lower() == h.lower() for k in headers)
        sec[key] = present
        if not present:
            sec_issues.append({
                "severity": sev,
                "issue": msg,
                "detail": f"Consider configuring the '{h}' header.",
            })

    # Cookies
    cookies_info = []
    for c in resp.cookies:
        info = {
            "name": c.name,
            "secure": c.secure,
            "httponly": "httponly" in str(getattr(c, "_rest", {})).lower(),
            "samesite": getattr(c, "_rest", {}).get("SameSite", "Not Set"),
        }
        cookies_info.append(info)
        if not c.secure and is_https:
            sec_issues.append({
                "severity": "medium",
                "issue": f"Cookie '{c.name}' lacks Secure flag",
                "detail": "Set Secure attribute for HTTPS delivery.",
            })
    sec["cookies"] = cookies_info

    # Info disclosure
    disco = {
        h: headers[h]
        for h in ["X-Powered-By", "X-AspNet-Version", "X-Generator"]
        if h in headers
    }
    sec["disclosure"] = disco
    for h, v in disco.items():
        sec_issues.append({
            "severity": "low",
            "issue": f"Info disclosure: {h}: {v}",
            "detail": "Remove or obfuscate header to avoid fingerprinting.",
        })

    # CORS
    cors = headers.get("Access-Control-Allow-Origin", "Not Set")
    sec["cors"] = cors
    if cors == "*":
        sec_issues.append({
            "severity": "medium",
            "issue": "Wildcard CORS (Access-Control-Allow-Origin: *)",
            "detail": "Restrict allowed origins to trusted domains.",
        })

    # Sensitive paths
    _paths = [
        "/.env",
        "/.git/HEAD",
        "/admin",
        "/login",
        "/backup",
        "/phpinfo.php",
        "/wp-admin",
        "/config.php",
    ]
    exposed = []
    for p in _paths:
        r = _get(f"{scheme}://{domain}{p}", timeout=4)
        if r and r.status_code in (200, 403):
            exposed.append({"path": p, "status": r.status_code})
            if r.status_code == 200:
                sec_issues.append({
                    "severity": "high",
                    "issue": f"Sensitive path accessible: {p}",
                    "detail": f"HTTP {r.status_code}",
                })
    sec["exposed_paths"] = exposed

    weights = {"critical": 25, "high": 15, "medium": 8, "low": 3}
    penalty = sum(weights.get(i["severity"], 0) for i in sec_issues)
    security_score = max(0, 100 - penalty)
    risk_level = (
        "Critical" if security_score < 40
        else ("High" if security_score < 60
              else ("Medium" if security_score < 75
                    else ("Low" if security_score < 90 else "Minimal")))
    )

    # 3. SEO
    log.info("SEO checks ...")
    seo_issues: List[str] = []
    seo: Dict[str, Any] = {}

    title = ""
    if soup and soup.find("title"):
        title = soup.find("title").get_text(strip=True)
    elif "<title>" in html_lower:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()

    seo["title"] = title
    seo["title_len"] = len(title)
    if not title:
        seo_issues.append("Missing <title> tag")
    elif len(title) < 30:
        seo_issues.append("Title tag is short (< 30 chars)")
    elif len(title) > 60:
        seo_issues.append("Title tag is long (> 60 chars)")

    meta_desc = ""
    if soup:
        md = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        meta_desc = md.get("content", "") if md else ""
    seo["meta_desc"] = meta_desc
    seo["meta_desc_len"] = len(meta_desc)
    if not meta_desc:
        seo_issues.append("Missing meta description")
    elif len(meta_desc) > 160:
        seo_issues.append("Meta description exceeds 160 characters")

    headings: Dict[str, List[str]] = {t: [] for t in ["h1", "h2", "h3", "h4", "h5", "h6"]}
    if soup:
        for t in headings:
            headings[t] = [h.get_text(strip=True) for h in soup.find_all(t)]
    seo["headings"] = headings
    if not headings["h1"]:
        seo_issues.append("No H1 heading found")
    elif len(headings["h1"]) > 1:
        seo_issues.append(f"Multiple H1 headings detected ({len(headings['h1'])})")

    canonical = ""
    if soup:
        can_tag = soup.find("link", rel=lambda r: r and "canonical" in r)
        canonical = can_tag.get("href", "") if can_tag else ""
    seo["canonical"] = canonical
    if not canonical:
        seo_issues.append("No canonical URL specified")

    og: Dict[str, str] = {}
    tw: Dict[str, str] = {}
    schema_count = 0
    int_links, ext_links = [], []
    imgs = []
    missing_alts = []
    has_viewport = False

    if soup:
        for t in soup.find_all("meta", property=re.compile(r"^og:", re.I)):
            og[t.get("property", "")] = t.get("content", "")
        for t in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)}):
            tw[t.get("name", "")] = t.get("content", "")
        schema_count = len(soup.find_all("script", type="application/ld+json"))

        for a in soup.find_all("a", href=True):
            h = a["href"]
            if h.startswith("http"):
                (int_links if domain in h else ext_links).append(h)
            elif h.startswith("/") or not h.startswith(("#", "mailto:", "tel:")):
                int_links.append(h)

        imgs = soup.find_all("img")
        missing_alts = [i for i in imgs if not i.get("alt")]
        vp = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        has_viewport = bool(vp)
    else:
        has_viewport = 'name="viewport"' in html_lower

    seo["og"] = og
    seo["twitter"] = tw
    seo["structured_data"] = schema_count
    seo["internal_links"] = len(int_links)
    seo["external_links"] = len(ext_links)
    seo["images_total"] = len(imgs)
    seo["images_no_alt"] = len(missing_alts)
    seo["viewport"] = has_viewport
    seo["has_robots"] = has_robots
    seo["has_sitemap"] = has_sitemap

    if not og:
        seo_issues.append("No OpenGraph metadata tags")
    if not tw:
        seo_issues.append("No Twitter Card metadata tags")
    if missing_alts:
        seo_issues.append(f"{len(missing_alts)} image(s) missing alt attribute")
    if not has_viewport:
        seo_issues.append("Missing viewport meta tag for mobile responsiveness")
    if not has_robots:
        seo_issues.append("robots.txt was not reachable")
    if not has_sitemap:
        seo_issues.append("sitemap.xml was not reachable")

    seo_score = max(0, 100 - len(seo_issues) * 8)

    # 4. Performance
    log.info("Performance checks ...")
    perf_issues: List[str] = []
    enc_hdr = headers.get("Content-Encoding", "")
    compressed = enc_hdr.lower() in ("gzip", "br", "deflate")
    cache_ctrl = headers.get("Cache-Control", "")
    etag = headers.get("ETag", "")

    if not compressed:
        perf_issues.append("HTTP compression (gzip / br) not active")
    if not cache_ctrl and not etag:
        perf_issues.append("Missing caching directives (Cache-Control or ETag)")
    if page_size_kb > 3000:
        perf_issues.append(f"Heavy document payload ({page_size_kb} KB)")
    if ttfb > 800:
        perf_issues.append(f"High Time To First Byte ({ttfb} ms)")

    scripts_count = len(soup.find_all("script", src=True)) if soup else 0
    css_count = len(soup.find_all("link", rel="stylesheet")) if soup else 0

    perf = {
        "ttfb": ttfb,
        "page_size_kb": page_size_kb,
        "compressed": compressed,
        "cache_control": cache_ctrl,
        "etag": etag,
        "encoding": enc_hdr,
        "scripts": scripts_count,
        "css": css_count,
        "images": len(imgs),
        "last_modified": headers.get("Last-Modified", ""),
    }
    perf_score = max(
        0,
        min(
            100,
            100
            - len(perf_issues) * 12
            - max(0, int(ttfb - 200)) // 100
            - max(0, int(page_size_kb - 500)) // 200,
        ),
    )

    # 5. Accessibility
    log.info("Accessibility checks ...")
    a11y_issues: List[str] = []
    if missing_alts:
        a11y_issues.append(f"{len(missing_alts)} image(s) lacking descriptive alt text")

    unlabeled_inputs: List[Any] = []
    empty_btns: List[Any] = []
    has_lang = False
    aria_labels_cnt = 0
    roles_cnt = 0

    if soup:
        has_lang = bool(soup.find("html", lang=True))
        inputs = soup.find_all("input")
        unlabeled_inputs = [
            i for i in inputs
            if i.get("type", "text") not in ("hidden", "submit", "button", "image")
            and not i.get("aria-label")
            and not i.get("aria-labelledby")
            and not soup.find("label", attrs={"for": i.get("id", "__none__")})
        ]
        empty_btns = [
            b for b in soup.find_all("button")
            if not b.get_text(strip=True) and not b.get("aria-label")
        ]
        aria_labels_cnt = len(soup.find_all(attrs={"aria-label": True}))
        roles_cnt = len(soup.find_all(attrs={"role": True}))

        hlevels = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        if hlevels and any(hlevels[i + 1] - hlevels[i] > 1 for i in range(len(hlevels) - 1)):
            a11y_issues.append("Heading hierarchy skipped (e.g., jump from H1 directly to H3)")

    if not has_lang:
        a11y_issues.append("Missing lang attribute on <html> element")
    if unlabeled_inputs:
        a11y_issues.append(f"{len(unlabeled_inputs)} input field(s) without accessible label")
    if empty_btns:
        a11y_issues.append(f"{len(empty_btns)} button(s) lack visible text and aria-label")

    a11y = {
        "lang": has_lang,
        "aria_labels": aria_labels_cnt,
        "roles": roles_cnt,
        "unlabeled_inputs": len(unlabeled_inputs),
        "empty_buttons": len(empty_btns),
        "missing_alts": len(missing_alts),
    }
    a11y_score = max(0, 100 - len(a11y_issues) * 12)

    # 6. Technology Detection
    log.info("Technology fingerprinting ...")
    techs: List[Dict[str, str]] = []
    hdrs_l = {k.lower(): v.lower() for k, v in headers.items()}
    srv = headers.get("Server", "").lower()
    xpb = headers.get("X-Powered-By", "").lower()

    if "cloudflare" in srv or "cf-ray" in hdrs_l:
        techs.append({"name": "Cloudflare", "cat": "CDN", "via": "header"})
    if "nginx" in srv:
        techs.append({"name": "Nginx", "cat": "Web Server", "via": "header"})
    if "apache" in srv:
        techs.append({"name": "Apache", "cat": "Web Server", "via": "header"})
    if "php" in xpb or "php" in srv:
        techs.append({"name": "PHP", "cat": "Language", "via": "header"})
    if "express" in xpb:
        techs.append({"name": "Express", "cat": "Framework", "via": "header"})
    if "node" in xpb:
        techs.append({"name": "Node.js", "cat": "Runtime", "via": "header"})

    _patterns = [
        ("React", [r"__reactfiber", r"react\.production", r"react-dom"]),
        ("Next.js", [r"__next", r"/_next/"]),
        ("Vue.js", [r"vue\.js", r"__vue__", r"data-v-"]),
        ("Angular", [r"ng-version", r"angular\.min"]),
        ("jQuery", [r"jquery\.min\.js", r"jquery-\d"]),
        ("Bootstrap", [r"bootstrap\.min\.css", r"bootstrap\.min\.js"]),
        ("Tailwind CSS", [r"tailwindcss", r"tailwind\.css", r"data-tw"]),
        ("WordPress", [r"/wp-content/", r"/wp-includes/"]),
        ("Shopify", [r"cdn\.shopify\.com", r"shopify-buy"]),
        ("Gatsby", [r"___gatsby", r"gatsby"]),
        ("Nuxt.js", [r"__nuxt"]),
        ("Svelte", [r"__svelte", r"svelte-"]),
    ]
    existing = {t["name"] for t in techs}
    for name, pats in _patterns:
        if name not in existing:
            for p in pats:
                if re.search(p, html_lower):
                    techs.append({"name": name, "cat": "Frontend", "via": "html"})
                    break

    # 7. DNS & CDN
    log.info("DNS & CDN inspection ...")
    dns_records: Dict[str, Any] = {}
    if HAS_DNS:
        for rtype in ("A", "MX", "TXT", "NS", "CNAME"):
            try:
                dns_records[rtype] = [
                    str(r) for r in dns_resolver.resolve(domain.split(":")[0], rtype)
                ]
            except Exception:
                dns_records[rtype] = []
    else:
        dns_records["note"] = "dnspython not installed (run `pip install dnspython`)"

    cdn_map = {
        "Cloudflare": ["cf-ray", "cf-cache-status"],
        "AWS CloudFront": ["x-amz-cf-id", "x-cache"],
        "Fastly": ["x-served-by", "x-cache-hits"],
        "Akamai": ["x-check-cacheable"],
        "Azure CDN": ["x-msedge-ref"],
    }
    detected_cdn = "None"
    for cdn_name, sigs in cdn_map.items():
        if any(s in hdrs_l for s in sigs):
            detected_cdn = cdn_name
            break
    dns_records["cdn"] = detected_cdn

    # 8. Aggregate
    overall_score = round((security_score + seo_score + perf_score + a11y_score) / 4)
    scan_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return {
        "url": target_url,
        "final_url": final_url,
        "domain": domain,
        "ip": ip,
        "scheme": scheme,
        "status_code": status_code,
        "server": headers.get("Server", "Unknown"),
        "content_type": headers.get("Content-Type", "Unknown"),
        "encoding": resp.encoding or "Unknown",
        "page_size_kb": page_size_kb,
        "ttfb": ttfb,
        "redirect_chain": redirect_chain,
        "has_robots": has_robots,
        "has_sitemap": has_sitemap,
        "fav": fav_tag is not None,
        "headers": headers,
        # scores
        "security_score": security_score,
        "seo_score": seo_score,
        "perf_score": perf_score,
        "a11y_score": a11y_score,
        "overall_score": overall_score,
        "risk_level": risk_level,
        # categories
        "sec": sec,
        "sec_issues": sec_issues,
        "seo": seo,
        "seo_issues": seo_issues,
        "perf": perf,
        "perf_issues": perf_issues,
        "a11y": a11y,
        "a11y_issues": a11y_issues,
        "techs": techs,
        "dns": dns_records,
        "scan_time": scan_time,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION HTML BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def build_summary_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    sc = d["security_score"]
    seo = d["seo_score"]
    pc = d["perf_score"]
    ac = d["a11y_score"]
    ov = d["overall_score"]
    risk = d["risk_level"]
    all_issues = (
        len(d["sec_issues"])
        + len(d["seo_issues"])
        + len(d["perf_issues"])
        + len(d["a11y_issues"])
    )

    risk_alert_map = {
        "Critical": ("alert-critical", "🚨", "Critical Risk — Immediate Hardening Recommended"),
        "High": ("alert-high", "⚠️", "High Risk — Action Recommended"),
        "Medium": ("alert-medium", "⚡", "Medium Risk — Optimization Recommended"),
        "Low": ("alert-good", "✅", "Low Risk — Strong Overall Posture"),
        "Minimal": ("alert-good", "✅", "Minimal Risk — Excellent Standing"),
    }
    ac_cls, ac_icon, ac_title = risk_alert_map.get(
        risk, ("alert-medium", "⚡", "Review Recommended")
    )

    css = """
.ov-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:20px}
.ov-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center;position:relative;overflow:hidden;transition:transform .2s,border-color .2s}
.ov-card:hover{transform:translateY(-2px);border-color:var(--border2)}
.ov-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--cc,var(--accent))}
.ov-score{font-size:44px;font-weight:800;font-family:var(--mono);color:var(--cc,var(--accent));line-height:1}
.ov-name{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-top:4px;font-family:var(--mono)}
.ov-label{font-size:12px;font-weight:700;margin-bottom:6px;color:var(--text)}
.chart-area{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
.chart-box canvas{max-height:260px}
.score-line{display:flex;align-items:center;gap:14px;font-size:13px;margin-bottom:10px}
.score-line .sname{width:120px;flex-shrink:0;font-family:var(--mono);font-size:11px;color:var(--muted)}
.score-line .bwrap{flex:1;height:20px;background:var(--surface2);border-radius:6px;overflow:hidden}
.score-line .bfill{height:100%;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:700;color:#fff;font-family:var(--mono)}
.score-line .bnum{width:36px;text-align:right;font-family:var(--mono);font-weight:700;font-size:13px}
"""
    scores = [
        ("Security", sc, len(d["sec_issues"])),
        ("SEO", seo, len(d["seo_issues"])),
        ("Performance", pc, len(d["perf_issues"])),
        ("Accessibility", ac, len(d["a11y_issues"])),
    ]
    cards_html = ""
    for name, score, issues_cnt in scores:
        cc = _score_color(score)
        cards_html += f"""<div class="ov-card" style="--cc:{cc}">
  <div class="ov-label">{name}</div>
  <div class="ov-score">{score}</div>
  <div class="ov-name">{_score_label(score)}</div>
  <div class="progress-wrap"><div class="progress-bar" style="width:{score}%;background:{cc}"></div></div>
  <div style="font-size:10px;color:var(--muted);margin-top:6px;font-family:var(--mono)">{issues_cnt} issues</div>
</div>"""

    score_bars = ""
    for name, score in [
        ("Security", sc),
        ("SEO", seo),
        ("Performance", pc),
        ("Accessibility", ac),
        ("Overall", ov),
    ]:
        cc = _score_color(score)
        score_bars += f"""<div class="score-line">
  <div class="sname">{name}</div>
  <div class="bwrap"><div class="bfill" style="width:{score}%;background:{cc}">{score}</div></div>
  <div class="bnum" style="color:{cc}">{score}</div>
</div>"""

    chart_data = json.dumps({
        "labels": ["Security", "SEO", "Performance", "Accessibility"],
        "scores": [sc, seo, pc, ac],
        "isDark": dark_mode,
    })

    open_h, close_h = _section_shell("Summary", dark_mode, css, CHARTJS)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">📊</div>
  <div><h1>Executive Summary</h1><div class="sub">{_esc(d["domain"])} &mdash; {_esc(d["scan_time"])}</div></div>
  <div class="score-badge">
    <div class="score-num" style="color:{_score_color(ov)}">{ov}</div>
    <div class="score-lbl" style="color:{_score_color(ov)}">Overall Score</div>
  </div>
</div>

<div class="alert {ac_cls}">
  <div class="alert-icon">{ac_icon}</div>
  <div>
    <div class="alert-title">{ac_title}</div>
    <div class="alert-sub">Overall score: {ov}/100 &bull; {all_issues} total findings recorded</div>
  </div>
</div>

<div class="ov-grid">{cards_html}</div>

<div class="chart-area">
  <div class="chart-box">
    <div class="card-title" style="margin-bottom:14px">Radar Overview</div>
    <canvas id="radarChart"></canvas>
  </div>
  <div class="chart-box">
    <div class="card-title" style="margin-bottom:14px">Performance &amp; Compliance Bars</div>
    {score_bars}
  </div>
</div>

<div class="card">
  <div class="card-header"><div class="card-title">Analysis Metadata</div></div>
  <div class="card-body">
    <div class="grid-2">
      <div>
        <div class="info-row"><div class="info-key">Target URL</div><div class="info-val"><code>{_esc(d["url"])}</code></div></div>
        <div class="info-row"><div class="info-key">IP Address</div><div class="info-val"><code>{_esc(d["ip"])}</code></div></div>
        <div class="info-row"><div class="info-key">HTTP Status</div><div class="info-val">{_status_badge(d["status_code"])}</div></div>
        <div class="info-row"><div class="info-key">Scan Time</div><div class="info-val"><code>{_esc(d["scan_time"])}</code></div></div>
      </div>
      <div>
        <div class="info-row"><div class="info-key">Total Issues</div><div class="info-val"><span class="badge badge-warn">{all_issues} detected</span></div></div>
        <div class="info-row"><div class="info-key">Risk Level</div><div class="info-val"><span class="badge badge-{"good" if risk in ("Low", "Minimal") else "medium" if risk == "Medium" else "high"}">{risk}</span></div></div>
        <div class="info-row"><div class="info-key">CDN Provider</div><div class="info-val"><span class="tech-tag">{_esc(d["dns"].get("cdn", "None"))}</span></div></div>
        <div class="info-row"><div class="info-key">HTTPS / TLS</div><div class="info-val">{_bool_badge(d["sec"].get("https", False))}</div></div>
      </div>
    </div>
  </div>
</div>

<script>
const cd = {chart_data};
const F = {{family:'JetBrains Mono',size:11}};
const G = cd.isDark ? '#1e2a38' : '#e2e8f0';
const T = cd.isDark ? '#4e6070' : '#64748b';
const COLORS = cd.scores.map(s => s>=80?'#00e676':s>=60?'#ffab00':s>=40?'#ff7043':'#ff3d57');
new Chart(document.getElementById('radarChart'),{{
  type:'radar',
  data:{{
    labels:cd.labels,
    datasets:[{{
      label:'Score',
      data:cd.scores,
      backgroundColor:'rgba(0,212,255,0.12)',
      borderColor:'#00d4ff',
      pointBackgroundColor:COLORS,
      pointBorderColor:'#fff',
      pointRadius:5,
      borderWidth:2
    }}]
  }},
  options:{{
    responsive:true,
    scales:{{
      r:{{
        min:0,
        max:100,
        ticks:{{stepSize:25,color:T,backdropColor:'transparent',font:F}},
        grid:{{color:G}},
        angleLines:{{color:G}},
        pointLabels:{{color:cd.isDark ? '#d4dfe8' : '#0f172a',font:{{...F,size:12,weight:'700'}}}}
      }}
    }},
    plugins:{{legend:{{display:false}}}}
  }}
}});
</script>
""" + close_h


def build_siteinfo_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    css = """
.rchain{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 0;font-size:12px;font-family:var(--mono)}
.rstep{background:var(--surface2);border:1px solid var(--border2);border-radius:6px;padding:4px 10px;color:var(--accent)}
.rfinal{background:rgba(0,230,118,.1);border-color:rgba(0,230,118,.3);color:var(--good)}
.rarrow{color:var(--muted);font-size:14px}
"""
    chain = " ".join(
        f'<div class="rstep {"rfinal" if i == len(d["redirect_chain"]) - 1 else ""}">{_esc(u)}</div>'
        + ("" if i == len(d["redirect_chain"]) - 1 else '<div class="rarrow">→</div>')
        for i, u in enumerate(d["redirect_chain"])
    )
    hdr_rows = "".join(
        f"<tr><td><code>{_esc(k)}</code></td><td>{_esc(v)}</td></tr>"
        for k, v in sorted(d["headers"].items())
    )
    open_h, close_h = _section_shell("Site Information", dark_mode, css)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">🌐</div>
  <div><h1>Site Information</h1><div class="sub">Server headers &amp; network routing details</div></div>
</div>

<div class="grid-3" style="margin-bottom:20px">
  <div class="stat-card" style="--accent-color:#00d4ff"><div class="stat-val">{d["status_code"]}</div><div class="stat-label">HTTP Status</div></div>
  <div class="stat-card" style="--accent-color:#00e676"><div class="stat-val">{d["page_size_kb"]} KB</div><div class="stat-label">Page Payload</div></div>
  <div class="stat-card" style="--accent-color:{"#00e676" if d["ttfb"] < 400 else "#ffab00" if d["ttfb"] < 800 else "#ff3d57"}">
    <div class="stat-val">{d["ttfb"]} ms</div><div class="stat-label">TTFB Latency</div></div>
</div>

<div class="card">
  <div class="card-header"><div class="card-title">Server &amp; Configuration</div></div>
  <div class="card-body"><div class="grid-2">
    <div>
      <div class="info-row"><div class="info-key">Domain</div><div class="info-val"><code>{_esc(d["domain"])}</code></div></div>
      <div class="info-row"><div class="info-key">Resolved IP</div><div class="info-val"><code>{_esc(d["ip"])}</code></div></div>
      <div class="info-row"><div class="info-key">Web Server</div><div class="info-val"><span class="tech-tag">{_esc(d["server"])}</span></div></div>
      <div class="info-row"><div class="info-key">Content-Type</div><div class="info-val"><code>{_esc(d["content_type"])}</code></div></div>
      <div class="info-row"><div class="info-key">Charset Encoding</div><div class="info-val"><code>{_esc(d["encoding"])}</code></div></div>
    </div>
    <div>
      <div class="info-row"><div class="info-key">robots.txt</div><div class="info-val">{_bool_badge(d["has_robots"])}</div></div>
      <div class="info-row"><div class="info-key">sitemap.xml</div><div class="info-val">{_bool_badge(d["has_sitemap"])}</div></div>
      <div class="info-row"><div class="info-key">Favicon</div><div class="info-val">{_bool_badge(d["fav"])}</div></div>
      <div class="info-row"><div class="info-key">CDN Identified</div><div class="info-val"><span class="tech-tag">{_esc(d["dns"].get("cdn", "None"))}</span></div></div>
    </div>
  </div></div>
</div>

<div class="card">
  <div class="card-header"><div class="card-title">Redirect Path Chain</div></div>
  <div class="card-body"><div class="rchain">{chain}</div>
  <div style="font-size:12px;color:var(--muted);font-family:var(--mono);margin-top:8px">{len(d["redirect_chain"]) - 1} redirection step(s) recorded</div>
  </div>
</div>

<div class="card">
  <div class="card-header"><div class="card-title">HTTP Response Headers</div></div>
  <div class="card-body" style="padding:0"><div class="table-wrap">
    <table><thead><tr><th>Header Name</th><th>Value</th></tr></thead>
    <tbody>{hdr_rows}</tbody></table>
  </div></div>
</div>
""" + close_h


def build_security_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    sec = d["sec"]
    issues = d["sec_issues"]
    score = d["security_score"]
    ssl_info = sec.get("ssl", {})

    css = """
.hdr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin-bottom:20px}
.hdr-check{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:14px 12px;text-align:center;font-family:var(--mono)}
.hdr-check .icon{font-size:18px;margin-bottom:6px}
.hdr-check .name{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.hdr-check.ok{border-color:rgba(0,230,118,.3);background:rgba(0,230,118,.05)}
.hdr-check.fail{border-color:rgba(255,61,87,.3);background:rgba(255,61,87,.05)}
.ssl-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
.ssl-meter{text-align:center;padding:20px}
.ssl-days{font-size:52px;font-weight:800;font-family:var(--mono);line-height:1}
.ssl-days-lbl{font-size:11px;color:var(--muted);font-family:var(--mono);margin-top:4px;text-transform:uppercase}
"""
    hdr_checks = {
        "HTTPS": ("https", sec.get("https", False)),
        "HSTS": ("hsts", sec.get("hsts", False)),
        "CSP": ("csp", sec.get("csp", False)),
        "X-Frame": ("xframe", sec.get("xframe", False)),
        "Referrer": ("ref", sec.get("ref", False)),
        "X-CTO": ("xcto", sec.get("xcto", False)),
        "Perms-Policy": ("perms", sec.get("perms", False)),
        "XSS-Protect": ("xxss", sec.get("xxss", False)),
    }
    checks_html = ""
    for label, (_, val) in hdr_checks.items():
        cls = "ok" if val else "fail"
        icon = "✅" if val else "❌"
        checks_html += f'<div class="hdr-check {cls}"><div class="icon">{icon}</div><div class="name">{label}</div></div>'

    if "error" in ssl_info:
        ssl_html = f'<p class="badge badge-bad">SSL Check Error: {_esc(ssl_info["error"])}</p>'
    elif ssl_info:
        days = ssl_info.get("days_left", "?")
        dc = "#00e676" if isinstance(days, int) and days > 30 else "#ff3d57"
        ssl_html = f"""<div class="ssl-grid">
  <div>
    <div class="info-row"><div class="info-key">Authority / Issuer</div><div class="info-val">{_esc(ssl_info.get("issuer", "?"))}</div></div>
    <div class="info-row"><div class="info-key">Subject CN</div><div class="info-val"><code>{_esc(ssl_info.get("subject", "?"))}</code></div></div>
    <div class="info-row"><div class="info-key">TLS Protocol</div><div class="info-val"><span class="badge badge-good">{_esc(ssl_info.get("tls_version", "?"))}</span></div></div>
    <div class="info-row"><div class="info-key">Valid Not Before</div><div class="info-val"><code>{_esc(ssl_info.get("not_before", "?"))}</code></div></div>
    <div class="info-row"><div class="info-key">Valid Not After</div><div class="info-val"><code>{_esc(ssl_info.get("not_after", "?"))}</code></div></div>
  </div>
  <div class="ssl-meter">
    <div class="ssl-days" style="color:{dc}">{days}</div>
    <div class="ssl-days-lbl">Days Until Expiration</div>
  </div>
</div>"""
    else:
        ssl_html = '<p style="color:var(--muted);font-family:var(--mono);font-size:13px">N/A — Target is served over plain HTTP</p>'

    vuln_rows = (
        "".join(
            f"<tr><td>{_sev_badge(i['severity'])}</td><td>{_esc(i['issue'])}</td><td>{_esc(i.get('detail', ''))}</td></tr>"
            for i in issues
        )
        or "<tr><td colspan='3' style='text-align:center;color:#00e676'>No critical security issues found ✓</td></tr>"
    )

    exposed = sec.get("exposed_paths", [])
    exp_rows = (
        "".join(
            f"<tr><td><code>{_esc(e['path'])}</code></td><td>"
            f"<span class='badge {'badge-bad' if e['status'] == 200 else 'badge-warn'}'>{e['status']}</span></td></tr>"
            for e in exposed
        )
        or "<tr><td colspan='2' style='color:#00e676'>No common administrative paths exposed ✓</td></tr>"
    )

    cookies = sec.get("cookies", [])
    ck_rows = (
        "".join(
            f"<tr><td><code>{_esc(c['name'])}</code></td><td>{_bool_badge(c['secure'])}</td>"
            f"<td>{_bool_badge(c['httponly'])}</td><td>{_esc(c.get('samesite', '?'))}</td></tr>"
            for c in cookies
        )
        or "<tr><td colspan='4' style='color:var(--muted)'>No HTTP cookies detected</td></tr>"
    )

    risk_cls = {
        "Critical": "alert-critical",
        "High": "alert-high",
        "Medium": "alert-medium",
    }.get(d["risk_level"], "alert-good")

    open_h, close_h = _section_shell("Security", dark_mode, css)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">🔒</div>
  <div><h1>Security Analysis</h1><div class="sub">{len(issues)} finding(s) &bull; {d["risk_level"]} Risk Posture</div></div>
  <div class="score-badge">
    <div class="score-num" style="color:{_score_color(score)}">{score}</div>
    <div class="score-lbl" style="color:{_score_color(score)}">{_score_label(score)}</div>
  </div>
</div>

<div class="alert {risk_cls}">
  <div class="alert-icon">{"🚨" if d["risk_level"] == "Critical" else "⚠️" if d["risk_level"] in ("High", "Medium") else "✅"}</div>
  <div>
    <div class="alert-title">{d["risk_level"]} Risk Assessment &mdash; {len(issues)} security findings</div>
    <div class="alert-sub">Score: {score}/100 &bull; CORS Header: {_esc(sec.get("cors", "Not Set"))}</div>
  </div>
</div>

<div class="section-label">HTTP Security Headers</div>
<div class="hdr-grid">{checks_html}</div>

<div class="section-label">TLS / SSL Certificate</div>
<div class="card">
  <div class="card-header"><div class="card-title">Certificate Parameters</div>
    {('<span class="badge badge-good">Valid</span>' if ssl_info.get("valid") else '<span class="badge badge-bad">Untrusted / Invalid</span>') if ssl_info else ""}
  </div>
  <div class="card-body">{ssl_html}</div>
</div>

<div class="section-label">Vulnerability &amp; Hardening Table</div>
<div class="card"><div class="card-body" style="padding:0"><div class="table-wrap">
  <table><thead><tr><th>Severity</th><th>Issue Description</th><th>Recommendation</th></tr></thead>
  <tbody>{vuln_rows}</tbody></table>
</div></div></div>

<div class="section-label">Sensitive Path Probing</div>
<div class="card"><div class="card-body" style="padding:0"><div class="table-wrap">
  <table><thead><tr><th>Endpoint Path</th><th>HTTP Response</th></tr></thead>
  <tbody>{exp_rows}</tbody></table>
</div></div></div>

<div class="section-label">Cookie Configuration</div>
<div class="card"><div class="card-body" style="padding:0"><div class="table-wrap">
  <table><thead><tr><th>Cookie Name</th><th>Secure Flag</th><th>HttpOnly</th><th>SameSite Policy</th></tr></thead>
  <tbody>{ck_rows}</tbody></table>
</div></div></div>
""" + close_h


def build_seo_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    seo = d["seo"]
    issues = d["seo_issues"]
    score = d["seo_score"]
    tl = seo["title_len"]
    t_pct = min(100, int(tl / 60 * 100))
    t_color = "#00e676" if 30 <= tl <= 60 else "#ff3d57"
    ml = seo["meta_desc_len"]
    m_pct = min(100, int(ml / 160 * 100))
    m_color = "#00e676" if ml <= 160 else "#ff3d57"

    h1s = seo["headings"].get("h1", [])
    h_rows = ""
    for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        for txt in seo["headings"].get(tag, []):
            indent = (int(tag[1]) - 1) * 16
            h_rows += f'<div style="padding:6px 0 6px {indent}px;border-bottom:1px solid var(--border);font-size:12px;font-family:var(--mono)"><span style="font-size:9px;background:var(--surface2);border:1px solid var(--border2);border-radius:4px;padding:1px 5px;margin-right:8px">{tag.upper()}</span>{_esc(txt[:80])}</div>'

    og_items = (
        "".join(
            f'<div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;font-size:12px;font-family:var(--mono);margin:3px"><div style="color:var(--accent2);font-size:10px;margin-bottom:4px">{_esc(k)}</div><div>{_esc(v[:100])}</div></div>'
            for k, v in seo["og"].items()
        )
        or '<span class="badge badge-bad">No OpenGraph tags configured</span>'
    )

    issue_li = (
        "".join(f'<li><span class="icon">⚠️</span>{_esc(x)}</li>' for x in issues)
        or '<li><span class="icon">✅</span>All standard SEO audits passed</li>'
    )

    css = """
.cbar{flex:1;height:4px;background:var(--surface2);border-radius:99px;overflow:hidden}
.cfill{height:100%;border-radius:99px}
.cmeter{margin-top:8px;display:flex;align-items:center;gap:10px;font-family:var(--mono);font-size:11px;color:var(--muted)}
"""
    open_h, close_h = _section_shell("SEO", dark_mode, css)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">🔎</div>
  <div><h1>SEO Analysis</h1><div class="sub">{len(issues)} search engine optimization finding(s)</div></div>
  <div class="score-badge">
    <div class="score-num" style="color:{_score_color(score)}">{score}</div>
    <div class="score-lbl" style="color:{_score_color(score)}">{_score_label(score)}</div>
  </div>
</div>

<div class="section-label">Title &amp; Meta Description</div>
<div class="card">
  <div class="card-header"><div class="card-title">HTML Page Title</div><span class="badge {"badge-good" if 30 <= tl <= 60 else "badge-bad"}">{tl} chars</span></div>
  <div class="card-body">
    <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:8px">{_esc(seo["title"] or "(empty title)")}</div>
    <div class="cmeter"><span>0</span><div class="cbar"><div class="cfill" style="width:{t_pct}%;background:{t_color}"></div></div><span>60</span></div>
  </div>
</div>
<div class="card">
  <div class="card-header"><div class="card-title">Meta Description</div><span class="badge {"badge-good" if ml <= 160 and ml > 0 else "badge-bad"}">{ml} chars</span></div>
  <div class="card-body">
    <div style="font-size:13px;color:var(--muted);margin-bottom:8px;line-height:1.6">{_esc((seo["meta_desc"] or "(missing meta description)")[:160])}</div>
    <div class="cmeter"><span>0</span><div class="cbar"><div class="cfill" style="width:{m_pct}%;background:{m_color}"></div></div><span>160</span></div>
  </div>
</div>

<div class="section-label">Social &amp; OpenGraph Meta</div>
<div class="card">
  <div class="card-header"><div class="card-title">OpenGraph Graph Tags</div>{_bool_badge(bool(seo["og"]))}</div>
  <div class="card-body"><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">{og_items}</div></div>
</div>
<div class="card">
  <div class="card-header"><div class="card-title">Twitter Card Properties</div>{_bool_badge(bool(seo["twitter"]))}</div>
  <div class="card-body">{"".join(f"<div class='info-row'><div class='info-key'>{_esc(k)}</div><div class='info-val'>{_esc(v)}</div></div>" for k, v in seo["twitter"].items()) or '<span style="color:var(--muted);font-family:var(--mono);font-size:12px">No twitter: tags discovered</span>'}</div>
</div>

<div class="section-label">Heading Structure</div>
<div class="card">
  <div class="card-header"><div class="card-title">Hierarchy Structure</div>{_bool_badge(len(h1s) == 1, "✓ Single H1", "⚠ Invalid H1 count")}</div>
  <div class="card-body">{"<div>" + h_rows + "</div>" if h_rows else '<p style="color:var(--muted)">No heading elements found</p>'}</div>
</div>

<div class="section-label">Links, Media &amp; Crawler Hints</div>
<div class="grid-2">
  <div class="card">
    <div class="card-header"><div class="card-title">Link Topology</div></div>
    <div class="card-body">
      <div class="info-row"><div class="info-key">Internal Links</div><div class="info-val"><span class="badge badge-info">{seo["internal_links"]}</span></div></div>
      <div class="info-row"><div class="info-key">External Links</div><div class="info-val"><span class="badge badge-info">{seo["external_links"]}</span></div></div>
      <div class="info-row"><div class="info-key">Canonical Link</div><div class="info-val">{_bool_badge(bool(seo["canonical"]))}</div></div>
      <div class="info-row"><div class="info-key">Structured JSON-LD</div><div class="info-val"><span class="badge badge-{"good" if seo["structured_data"] else "bad"}">{seo["structured_data"]} block(s)</span></div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-header"><div class="card-title">Images &amp; Viewport</div></div>
    <div class="card-body">
      <div class="info-row"><div class="info-key">Total Images</div><div class="info-val">{seo["images_total"]}</div></div>
      <div class="info-row"><div class="info-key">Missing Alt Text</div><div class="info-val"><span class="badge {"badge-bad" if seo["images_no_alt"] else "badge-good"}">{seo["images_no_alt"]} items</span></div></div>
      <div class="info-row"><div class="info-key">Viewport Tag</div><div class="info-val">{_bool_badge(seo["viewport"])}</div></div>
    </div>
  </div>
</div>

<div class="section-label">Identified SEO Issues</div>
<div class="card"><div class="card-body"><ul class="issue-list">{issue_li}</ul></div></div>
""" + close_h


def build_performance_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    perf = d["perf"]
    issues = d["perf_issues"]
    score = d["perf_score"]
    ttfb = perf["ttfb"]
    tc = "#00e676" if ttfb < 400 else "#ffab00" if ttfb < 800 else "#ff3d57"

    issue_li = (
        "".join(f'<li><span class="icon">⚠️</span>{_esc(x)}</li>' for x in issues)
        or '<li><span class="icon">✅</span>All performance baseline checks passed</li>'
    )

    open_h, close_h = _section_shell("Performance", dark_mode)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">⚡</div>
  <div><h1>Performance Analysis</h1><div class="sub">{len(issues)} delivery &amp; latency metric(s)</div></div>
  <div class="score-badge">
    <div class="score-num" style="color:{_score_color(score)}">{score}</div>
    <div class="score-lbl" style="color:{_score_color(score)}">{_score_label(score)}</div>
  </div>
</div>

<div class="grid-3" style="margin-bottom:20px">
  <div class="stat-card" style="--accent-color:{tc}"><div class="stat-val">{ttfb}</div><div class="stat-label">TTFB Latency (ms)</div></div>
  <div class="stat-card" style="--accent-color:#00d4ff"><div class="stat-val">{perf["page_size_kb"]}</div><div class="stat-label">Document Size (KB)</div></div>
  <div class="stat-card" style="--accent-color:{"#00e676" if perf["compressed"] else "#ff3d57"}">
    <div class="stat-val">{"ACTIVE" if perf["compressed"] else "OFF"}</div><div class="stat-label">Compression</div></div>
</div>

<div class="section-label">Caching &amp; Compression Pipeline</div>
<div class="grid-2">
  <div class="card">
    <div class="card-header"><div class="card-title">Compression Details</div>{_bool_badge(perf["compressed"])}</div>
    <div class="card-body">
      <div class="info-row"><div class="info-key">Content-Encoding</div><div class="info-val"><code>{_esc(perf["encoding"] or "None")}</code></div></div>
      <div class="info-row"><div class="info-key">Payload Weight</div><div class="info-val">{perf["page_size_kb"]} KB</div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-header"><div class="card-title">Caching Directives</div>{_bool_badge(bool(perf["cache_control"] or perf["etag"]))}</div>
    <div class="card-body">
      <div class="info-row"><div class="info-key">Cache-Control</div><div class="info-val"><code>{_esc(perf["cache_control"] or "Not Set")}</code></div></div>
      <div class="info-row"><div class="info-key">ETag</div><div class="info-val"><code>{_esc(perf["etag"] or "Not Set")}</code></div></div>
      <div class="info-row"><div class="info-key">Last-Modified</div><div class="info-val">{_esc(perf["last_modified"] or "Not Set")}</div></div>
    </div>
  </div>
</div>

<div class="section-label">Initial Resource Footprint</div>
<div class="card"><div class="card-body">
  <div class="info-row"><div class="info-key">External Scripts</div><div class="info-val">{perf["scripts"]} script tag(s)</div></div>
  <div class="info-row"><div class="info-key">Stylesheets</div><div class="info-val">{perf["css"]} link tag(s)</div></div>
  <div class="info-row"><div class="info-key">Image Elements</div><div class="info-val">{perf["images"]} img tag(s)</div></div>
</div></div>

<div class="section-label">Performance Opportunities</div>
<div class="card"><div class="card-body"><ul class="issue-list">{issue_li}</ul></div></div>
""" + close_h


def build_accessibility_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    a11y = d["a11y"]
    issues = d["a11y_issues"]
    score = d["a11y_score"]
    issue_li = (
        "".join(f'<li><span class="icon">⚠️</span>{_esc(x)}</li>' for x in issues)
        or '<li><span class="icon">✅</span>No accessibility discrepancies detected</li>'
    )

    checks = [
        ("HTML lang attr", a11y["lang"]),
        ("Alt Text on Images", a11y["missing_alts"] == 0),
        ("Form Labels", a11y["unlabeled_inputs"] == 0),
        ("Button Accessibility", a11y["empty_buttons"] == 0),
    ]
    checks_html = ""
    for label, ok in checks:
        cls = "ok" if ok else "fail"
        icon = "✅" if ok else "❌"
        checks_html += f'<div class="hdr-check {cls}"><div class="icon">{icon}</div><div class="name">{label}</div></div>'

    css = """
.hdr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:20px}
.hdr-check{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:14px 12px;text-align:center;font-family:var(--mono)}
.hdr-check .icon{font-size:18px;margin-bottom:6px}
.hdr-check .name{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.hdr-check.ok{border-color:rgba(0,230,118,.3);background:rgba(0,230,118,.05)}
.hdr-check.fail{border-color:rgba(255,61,87,.3);background:rgba(255,61,87,.05)}
"""
    open_h, close_h = _section_shell("Accessibility", dark_mode, css)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">♿</div>
  <div><h1>Accessibility &amp; WCAG</h1><div class="sub">{len(issues)} accessibility finding(s)</div></div>
  <div class="score-badge">
    <div class="score-num" style="color:{_score_color(score)}">{score}</div>
    <div class="score-lbl" style="color:{_score_color(score)}">{_score_label(score)}</div>
  </div>
</div>

<div class="section-label">Accessibility Checks</div>
<div class="hdr-grid">{checks_html}</div>

<div class="section-label">Semantic &amp; ARIA Metrics</div>
<div class="card"><div class="card-body">
  <div class="info-row"><div class="info-key">HTML lang attribute</div><div class="info-val">{_bool_badge(a11y["lang"])}</div></div>
  <div class="info-row"><div class="info-key">aria-label elements</div><div class="info-val">{a11y["aria_labels"]}</div></div>
  <div class="info-row"><div class="info-key">role elements</div><div class="info-val">{a11y["roles"]}</div></div>
  <div class="info-row"><div class="info-key">Unlabeled Form Inputs</div><div class="info-val"><span class="badge {"badge-bad" if a11y["unlabeled_inputs"] else "badge-good"}">{a11y["unlabeled_inputs"]}</span></div></div>
  <div class="info-row"><div class="info-key">Empty Icon/Buttons</div><div class="info-val"><span class="badge {"badge-bad" if a11y["empty_buttons"] else "badge-good"}">{a11y["empty_buttons"]}</span></div></div>
  <div class="info-row"><div class="info-key">Images Missing Alt</div><div class="info-val"><span class="badge {"badge-bad" if a11y["missing_alts"] else "badge-good"}">{a11y["missing_alts"]}</span></div></div>
</div></div>

<div class="section-label">Action Items</div>
<div class="card"><div class="card-body"><ul class="issue-list">{issue_li}</ul></div></div>
""" + close_h


def build_technologies_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    techs = d["techs"]
    cards = ""
    icon_map = {
        "CDN": "☁️",
        "Web Server": "🖥️",
        "Language": "🐘",
        "Framework": "🚀",
        "Runtime": "🟢",
        "Frontend": "⚛️",
    }
    for t in techs:
        icon = icon_map.get(t["cat"], "🧩")
        cards += f"""<div class="tech-card">
  <div class="tc-icon">{icon}</div>
  <div class="tc-name">{_esc(t["name"])}</div>
  <div class="tc-cat">{_esc(t["cat"])}</div>
  <div class="tc-how"><span class="detect-src">Detected via {_esc(t["via"])}</span></div>
</div>"""

    if not techs:
        cards = '<p style="color:var(--muted);font-family:var(--mono);font-size:13px">No distinctive technologies detected in headers or markup.</p>'

    css = """
.tech-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin-bottom:20px}
.tech-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;display:flex;flex-direction:column;gap:8px;transition:border-color .2s,transform .2s}
.tech-card:hover{border-color:var(--border2);transform:translateY(-2px)}
.tc-icon{font-size:26px}
.tc-name{font-size:14px;font-weight:700;color:var(--text)}
.tc-cat{font-size:10px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.tc-how{font-size:11px;color:var(--muted);font-family:var(--mono);background:var(--surface2);border:1px solid var(--border);border-radius:5px;padding:4px 8px;margin-top:4px}
.detect-src{color:var(--accent2)}
"""
    open_h, close_h = _section_shell("Technologies", dark_mode, css)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">🧩</div>
  <div><h1>Technology Stack</h1><div class="sub">{len(techs)} stack component(s) identified</div></div>
</div>

<div class="section-label">Identified Components</div>
<div class="tech-grid">{cards}</div>

<div class="section-label">Server Evidence Headers</div>
<div class="card"><div class="card-body" style="padding:0"><div class="table-wrap">
  <table><thead><tr><th>Header Marker</th><th>Signature Value</th></tr></thead><tbody>
    {"".join(
        f"<tr><td><code>{_esc(k)}</code></td><td>{_esc(d['headers'].get(k, ''))}</td></tr>"
        for k in ["Server", "X-Powered-By", "Via", "X-Generator"]
        if k in d["headers"]
    ) or "<tr><td colspan='2' style='color:var(--muted)'>No identifying fingerprint headers found</td></tr>"}
  </tbody></table>
</div></div></div>
""" + close_h


def build_dns_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    dns = d["dns"]
    if "note" in dns:
        dns_table = f'<div style="padding:20px;color:var(--muted);font-family:var(--mono);font-size:13px">{_esc(dns["note"])}</div>'
    else:
        type_cls = {"A": "", "MX": "mx", "TXT": "txt", "NS": "ns", "CNAME": "cname"}
        rows = (
            "".join(
                f'<tr><td><span class="dns-type {type_cls.get(rt, "")}">{rt}</span></td><td><code>{_esc(v)}</code></td></tr>'
                for rt, vals in dns.items()
                if rt != "cdn" and isinstance(vals, list)
                for v in vals
            )
            or "<tr><td colspan='2' style='color:var(--muted)'>No DNS records returned</td></tr>"
        )
        dns_table = f"<div class='table-wrap'><table><thead><tr><th>Record Type</th><th>Value</th></tr></thead><tbody>{rows}</tbody></table></div>"

    css = """
.dns-type{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;background:rgba(0,212,255,.1);color:var(--accent);border:1px solid rgba(0,212,255,.25);min-width:44px;text-align:center}
.dns-type.mx{background:rgba(124,92,252,.1);color:var(--accent2);border-color:rgba(124,92,252,.25)}
.dns-type.txt{background:rgba(255,171,0,.1);color:#ffab00;border-color:rgba(255,171,0,.25)}
.dns-type.ns{background:rgba(0,230,118,.1);color:var(--good);border-color:rgba(0,230,118,.25)}
.dns-type.cname{background:rgba(255,100,50,.1);color:#ff7043;border-color:rgba(255,100,50,.25)}
"""
    open_h, close_h = _section_shell("DNS & Infrastructure", dark_mode, css)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">🌍</div>
  <div><h1>DNS &amp; Infrastructure</h1><div class="sub">Routing and edge delivery telemetry</div></div>
</div>

<div class="grid-3" style="margin-bottom:20px">
  <div class="stat-card" style="--accent-color:#00d4ff"><div class="stat-val" style="font-size:20px">{_esc(dns.get("cdn", "None"))}</div><div class="stat-label">Edge CDN Provider</div></div>
  <div class="stat-card" style="--accent-color:#00e676"><div class="stat-val" style="font-size:20px">{_esc(d["ip"])}</div><div class="stat-label">Host IP Address</div></div>
  <div class="stat-card" style="--accent-color:#7c5cfc"><div class="stat-val" style="font-size:20px">{_esc(d["scheme"].upper())}</div><div class="stat-label">Transport Protocol</div></div>
</div>

<div class="section-label">CDN Discovery</div>
<div class="card">
  <div class="card-header"><div class="card-title">Content Delivery Network</div>
    <span class="badge {"badge-good" if dns.get("cdn") != "None" else "badge-warn"}">{_esc(dns.get("cdn", "None"))}</span>
  </div>
  <div class="card-body">
    <div class="info-row"><div class="info-key">Identified Edge CDN</div><div class="info-val"><span class="tech-tag">{_esc(dns.get("cdn", "None"))}</span></div></div>
    <div class="info-row"><div class="info-key">Fingerprint Method</div><div class="info-val">Edge Response Headers &amp; Ray IDs</div></div>
  </div>
</div>

<div class="section-label">Resolved DNS Records</div>
<div class="card"><div class="card-body" style="padding:0">{dns_table}</div></div>
""" + close_h


def build_charts_html(d: Dict[str, Any], dark_mode: bool = True) -> str:
    sc = d["security_score"]
    seo = d["seo_score"]
    pc = d["perf_score"]
    ac = d["a11y_score"]
    ov = d["overall_score"]
    chart_payload = json.dumps({
        "scores": [sc, seo, pc, ac],
        "issues": [
            len(d["sec_issues"]),
            len(d["seo_issues"]),
            len(d["perf_issues"]),
            len(d["a11y_issues"]),
        ],
        "overall": ov,
        "isDark": dark_mode,
        "sec_headers": [
            int(d["sec"].get("https", False)),
            int(d["sec"].get("hsts", False)),
            int(d["sec"].get("csp", False)),
            int(d["sec"].get("xframe", False)),
            int(d["sec"].get("ref", False)),
            int(d["sec"].get("xcto", False)),
            int(d["sec"].get("perms", False)),
            int(d["sec"].get("xxss", False)),
        ],
    })

    css = """
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
.chart-box-title{font-size:11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:16px}
.chart-box canvas{max-height:240px}
.score-line{display:flex;align-items:center;gap:14px;font-size:13px;margin-bottom:10px}
.score-line .sname{width:120px;flex-shrink:0;font-family:var(--mono);font-size:11px;color:var(--muted)}
.score-line .bwrap{flex:1;height:20px;background:var(--surface2);border-radius:6px;overflow:hidden}
.score-line .bfill{height:100%;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:700;color:#fff;font-family:var(--mono)}
.score-line .bnum{width:36px;text-align:right;font-family:var(--mono);font-weight:700;font-size:13px}
"""
    score_bars = ""
    for name, score in [
        ("Security", sc),
        ("SEO", seo),
        ("Performance", pc),
        ("Accessibility", ac),
        ("Overall", ov),
    ]:
        cc = _score_color(score)
        score_bars += f'<div class="score-line"><div class="sname">{name}</div><div class="bwrap"><div class="bfill" style="width:{score}%;background:{cc}">{score}</div></div><div class="bnum" style="color:{cc}">{score}</div></div>'

    open_h, close_h = _section_shell("Charts", dark_mode, css, CHARTJS)
    return open_h + f"""
<div class="page-header">
  <div class="page-header-icon">📈</div>
  <div><h1>Analytical Charts</h1><div class="sub">Visualized metric comparisons</div></div>
</div>

<div class="section-label">Dimensional Scores</div>
<div class="card"><div class="card-body">{score_bars}</div></div>

<div class="chart-grid">
  <div class="chart-box"><div class="chart-box-title">Radar &mdash; All Core Dimensions</div><canvas id="radarChart"></canvas></div>
  <div class="chart-box"><div class="chart-box-title">Total Issues by Category</div><canvas id="issueChart"></canvas></div>
</div>
<div class="chart-grid">
  <div class="chart-box"><div class="chart-box-title">Severity Proportion Mix</div><canvas id="sevChart"></canvas></div>
  <div class="chart-box"><div class="chart-box-title">Security Header Compliance</div><canvas id="secChart"></canvas></div>
</div>

<script>
const cd = {chart_payload};
const F = {{family:'JetBrains Mono',size:11}};
const G = cd.isDark ? '#1e2a38' : '#e2e8f0';
const T = cd.isDark ? '#4e6070' : '#64748b';
const COLORS = cd.scores.map(s => s>=80?'#00e676':s>=60?'#ffab00':s>=40?'#ff7043':'#ff3d57');
const NAMES = ['Security','SEO','Performance','Accessibility'];

new Chart(document.getElementById('radarChart'), {{
  type:'radar',
  data:{{labels:NAMES,datasets:[{{label:'Score',data:cd.scores,backgroundColor:'rgba(0,212,255,0.12)',borderColor:'#00d4ff',pointBackgroundColor:COLORS,pointBorderColor:'#fff',pointRadius:5,borderWidth:2}}]}},
  options:{{responsive:true,scales:{{r:{{min:0,max:100,ticks:{{stepSize:25,color:T,backdropColor:'transparent',font:F}},grid:{{color:G}},angleLines:{{color:G}},pointLabels:{{color:cd.isDark ? '#d4dfe8' : '#0f172a',font:{{...F,size:12,weight:'700'}}}}}}}},plugins:{{legend:{{display:false}}}}}}
}});

new Chart(document.getElementById('issueChart'), {{
  type:'bar',
  data:{{labels:NAMES,datasets:[{{data:cd.issues,backgroundColor:['rgba(255,61,87,.6)','rgba(255,171,0,.6)','rgba(0,230,118,.6)','rgba(124,92,252,.6)'],borderColor:['#ff3d57','#ffab00','#00e676','#7c5cfc'],borderWidth:1,borderRadius:6}}]}},
  options:{{responsive:true,plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{color:G}},ticks:{{color:T,font:F}}}},y:{{grid:{{color:G}},ticks:{{color:T,font:F}},beginAtZero:true}}}}}}
}});

const sevLabels = ['Critical','High','Medium','Low'];
new Chart(document.getElementById('sevChart'), {{
  type:'doughnut',
  data:{{labels:sevLabels,datasets:[{{data:[1, cd.issues[0], cd.issues[1]+cd.issues[3], cd.issues[2]],backgroundColor:['rgba(220,38,38,.7)','rgba(255,61,87,.7)','rgba(255,171,0,.7)','rgba(0,212,255,.7)'],borderColor:['#dc2626','#ff3d57','#ffab00','#00d4ff'],borderWidth:1}}]}},
  options:{{responsive:true,cutout:'55%',plugins:{{legend:{{position:'right',labels:{{color:cd.isDark ? '#d4dfe8' : '#0f172a',font:F,padding:10}}}}}}}}
}});

new Chart(document.getElementById('secChart'), {{
  type:'bar',
  data:{{labels:['HTTPS','HSTS','CSP','X-Frame','Referrer','X-CTO','Perms','XSS'],datasets:[{{data:cd.sec_headers,backgroundColor:cd.sec_headers.map(v=>v?'rgba(0,230,118,.6)':'rgba(255,61,87,.4)'),borderColor:cd.sec_headers.map(v=>v?'#00e676':'#ff3d57'),borderWidth:1,borderRadius:4}}]}},
  options:{{responsive:true,indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{color:G}},ticks:{{color:T,font:F}},max:1}},y:{{grid:{{color:G}},ticks:{{color:T,font:{{...F,size:10}}}}}}}}}}
}});
</script>
""" + close_h


# ══════════════════════════════════════════════════════════════════════════════
#  SPA INDEX SHELL BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_index_html(
    d: Dict[str, Any],
    dark_mode: bool = True,
    sections_html: Optional[Dict[str, str]] = None,
) -> str:
    """Build the main SPA application loader shell."""
    theme_attr = "dark" if dark_mode else "light"
    css = get_shared_css(dark_mode=dark_mode)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="{theme_attr}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WebAnalyzer &mdash; {_esc(d["domain"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
{css}
html,body{{height:100%;overflow:hidden;padding:0;margin:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);display:flex}}
.sidebar{{width:230px;min-height:100vh;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0;position:relative;z-index:10}}
.sidebar::after{{content:'';position:absolute;top:0;right:-1px;bottom:0;width:1px;background:linear-gradient(180deg,var(--accent) 0%,transparent 40%,var(--accent2) 100%);opacity:.4}}
.brand{{padding:24px 20px 20px;border-bottom:1px solid var(--border)}}
.brand-icon{{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:10px;box-shadow:0 0 20px rgba(0,212,255,.3)}}
.brand-name{{font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--text)}}
.brand-sub{{font-size:10px;color:var(--muted);margin-top:2px;font-family:var(--mono)}}
.nav{{flex:1;padding:12px 0;overflow-y:auto}}
.nav-group-label{{padding:14px 20px 6px;font-size:9px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-family:var(--mono)}}
.nav-item{{display:flex;align-items:center;gap:10px;padding:9px 20px;font-size:12.5px;font-weight:600;color:var(--muted);cursor:pointer;position:relative;transition:color .2s,background .2s;border:none;background:none;width:100%;text-align:left;border-left:2px solid transparent;letter-spacing:.01em}}
.nav-item:hover{{color:var(--text);background:var(--surface2)}}
.nav-item.active{{color:var(--accent);background:rgba(0,212,255,.06);border-left-color:var(--accent)}}
.nav-item .ico{{width:18px;text-align:center;font-size:14px;flex-shrink:0}}
.nav-item .nb{{margin-left:auto;font-family:var(--mono);font-size:9px;background:var(--surface2);border:1px solid var(--border2);color:var(--muted);padding:1px 5px;border-radius:4px}}
.nav-item.active .nb{{border-color:rgba(0,212,255,.3);color:var(--accent)}}
.sidebar-footer{{padding:14px 20px;border-top:1px solid var(--border);font-family:var(--mono);font-size:10px;color:var(--muted)}}
.sidebar-footer a{{color:var(--accent);text-decoration:none}}
.dot{{display:inline-block;width:6px;height:6px;background:var(--good);border-radius:50%;margin-right:6px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.panel{{flex:1;height:100vh;overflow:hidden;position:relative;background:var(--bg)}}
.loader{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:var(--bg);z-index:5;opacity:0;pointer-events:none;transition:opacity .2s}}
.loader.visible{{opacity:1;pointer-events:all}}
.loader-ring{{width:40px;height:40px;border:2px solid var(--border2);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.loader-text{{margin-top:14px;font-family:var(--mono);font-size:11px;color:var(--muted)}}
#content-frame{{width:100%;height:100%;border:none;opacity:0;transition:opacity .3s}}
#content-frame.loaded{{opacity:1}}
.welcome{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:40px}}
.wglow{{width:120px;height:120px;background:radial-gradient(circle,rgba(0,212,255,.15),transparent 70%);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:52px}}
.welcome h2{{font-size:22px;font-weight:800;color:var(--text);text-align:center}}
.welcome p{{font-size:13px;color:var(--muted);text-align:center;max-width:340px;line-height:1.6}}
.domain-chip{{background:var(--surface2);border:1px solid var(--border2);border-radius:6px;padding:6px 12px;font-size:11px;font-family:var(--mono);color:var(--accent);margin-top:8px}}
.score-chip{{background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.2);border-radius:6px;padding:4px 10px;font-size:12px;font-family:var(--mono);color:var(--accent);font-weight:700}}
</style>
</head>
<body>
<aside class="sidebar">
  <div class="brand">
    <div class="brand-icon">🔍</div>
    <div class="brand-name">WebAnalyzer</div>
    <div class="brand-sub">{_esc(d["domain"])}</div>
  </div>
  <nav class="nav">
    <div class="nav-group-label">Overview</div>
    <button class="nav-item" data-section="summary"><span class="ico">📊</span>Summary</button>
    <button class="nav-item" data-section="siteinfo"><span class="ico">🌐</span>Site Info</button>
    <div class="nav-group-label">Analysis</div>
    <button class="nav-item" data-section="security"><span class="ico">🔒</span>Security<span class="nb">SEC</span></button>
    <button class="nav-item" data-section="seo"><span class="ico">🔎</span>SEO<span class="nb">SEO</span></button>
    <button class="nav-item" data-section="performance"><span class="ico">⚡</span>Performance<span class="nb">PERF</span></button>
    <button class="nav-item" data-section="accessibility"><span class="ico">♿</span>Accessibility<span class="nb">A11Y</span></button>
    <div class="nav-group-label">Stack</div>
    <button class="nav-item" data-section="technologies"><span class="ico">🧩</span>Technologies</button>
    <button class="nav-item" data-section="dns"><span class="ico">🌍</span>DNS &amp; Infra</button>
    <div class="nav-group-label">Visuals</div>
    <button class="nav-item" data-section="charts"><span class="ico">📈</span>Charts</button>
  </nav>
  <div class="sidebar-footer">
    <div style="margin-bottom:6px"><span class="dot"></span>Passive Scan &bull; {_esc(d["scan_time"])}</div>
    <div>By <a href="https://github.com/gauravk310" target="_blank" rel="noopener noreferrer">Gaurav Kadam</a></div>
  </div>
</aside>
<div class="panel" id="panel">
  <div class="welcome" id="welcome">
    <div class="wglow">🔍</div>
    <h2>Analysis Complete</h2>
    <p>Select any section in the sidebar to review detailed diagnostic reports.</p>
    <div class="domain-chip">{_esc(d["domain"])}</div>
    <div class="score-chip">Overall Score: {d["overall_score"]}/100</div>
  </div>
  <div class="loader" id="loader"><div class="loader-ring"></div><div class="loader-text">Loading view...</div></div>
  <iframe id="content-frame" title="Report Section"></iframe>
</div>
<script>
const navItems = document.querySelectorAll('.nav-item[data-section]');
const frame = document.getElementById('content-frame');
const loader = document.getElementById('loader');
const welcome = document.getElementById('welcome');
let current = null;

function loadSection(id) {{
  if (id === current) return;
  current = id;
  navItems.forEach(n => n.classList.toggle('active', n.dataset.section === id));
  if (welcome) welcome.style.display = 'none';
  loader.classList.add('visible');
  frame.classList.remove('loaded');
  frame.src = 'sections/' + id + '.html';
}}

frame.addEventListener('load', () => {{
  loader.classList.remove('visible');
  frame.classList.add('loaded');
}});

navItems.forEach(btn => btn.addEventListener('click', () => loadSection(btn.dataset.section)));
document.addEventListener('keydown', e => {{
  const S = ['summary','siteinfo','security','seo','performance','accessibility','technologies','dns','charts'];
  const i = S.indexOf(current);
  if (e.key === 'ArrowDown' && i < S.length - 1) loadSection(S[i + 1]);
  if (e.key === 'ArrowUp' && i > 0) loadSection(S[i - 1]);
}});

// Initialize default view
loadSection('summary');
</script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  WEBREPORT CLASS IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════════════════

class WebReport(BaseReport):
    """Generates and exports interactive multi-section webpage reports.

    Usage::

        from reportz import WebReport

        web = WebReport()
        web.save("filename", url="https://example.com", dark_mode=True)

    Or::

        web = WebReport(url="https://example.com")
        web.save("my_report.html", open_browser=True)
    """

    def __init__(
        self,
        url: Optional[str] = None,
        dark_mode: bool = True,
        delay: int = 0,
    ) -> None:
        self.url = url
        self.dark_mode = dark_mode
        self.delay = delay
        self._data: Optional[Dict[str, Any]] = None

        if self.url:
            self.scan(self.url, delay=self.delay)

    def scan(self, url: Optional[str] = None, delay: Optional[int] = None) -> Dict[str, Any]:
        """Perform passive scan on target URL and cache telemetry results."""
        target = url or self.url
        if not target:
            raise ValueError("A target URL must be provided to perform a scan.")

        target_delay = self.delay if delay is None else delay
        self.url = target
        self._data = run_web_scan(target, delay=target_delay)
        return self._data

    def all(self) -> Dict[str, Any]:
        """Return all collected scan telemetry data."""
        if self._data is None:
            if not self.url:
                raise ValueError("No URL has been scanned yet. Call .scan(url) or pass url in .save().")
            self.scan(self.url)
        return self._data  # type: ignore

    def to_dict(self) -> Dict[str, Any]:
        """Return the collected telemetry as a Python dictionary."""
        return self.all()

    def to_json(self, indent: int = 2) -> str:
        """Return telemetry data serialized as formatted JSON."""
        return json.dumps(self.all(), indent=indent, default=str)

    def summary(self) -> Dict[str, Any]:
        """Return high-level summary metrics dictionary."""
        d = self.all()
        return {
            "domain": d["domain"],
            "url": d["url"],
            "ip": d["ip"],
            "overall_score": d["overall_score"],
            "security_score": d["security_score"],
            "seo_score": d["seo_score"],
            "performance_score": d["perf_score"],
            "accessibility_score": d["a11y_score"],
            "risk_level": d["risk_level"],
            "technologies": [t["name"] for t in d["techs"]],
            "issues_total": (
                len(d["sec_issues"])
                + len(d["seo_issues"])
                + len(d["perf_issues"])
                + len(d["a11y_issues"])
            ),
            "cdn": d["dns"].get("cdn", "None"),
            "https": d["sec"].get("https", False),
            "scan_time": d["scan_time"],
        }

    def generate_html(self, dark_mode: Optional[bool] = None, **kwargs: Any) -> str:
        """Generate standalone HTML report markup."""
        mode = self.dark_mode if dark_mode is None else dark_mode
        d = self.all()
        builders = {
            "summary": build_summary_html,
            "siteinfo": build_siteinfo_html,
            "security": build_security_html,
            "seo": build_seo_html,
            "performance": build_performance_html,
            "accessibility": build_accessibility_html,
            "technologies": build_technologies_html,
            "dns": build_dns_html,
            "charts": build_charts_html,
        }
        sections_html = {name: fn(d, dark_mode=mode) for name, fn in builders.items()}
        return build_index_html(d, dark_mode=mode, sections_html=sections_html)

    def save(
        self,
        filename: str = "web_report.html",
        url: Optional[Union[str, bool]] = None,
        dark_mode: Optional[bool] = None,
        save_file_path: Union[str, Path] = ".",
        open_browser: bool = False,
        delay: int = 0,
        **kwargs: Any,
    ) -> str:
        """Save multi-section SPA report to disk and return destination file path.

        Flexible arguments support:
        - `web.save("filename", url, darkmode)`
        - `web.save("report.html", save_file_path="./out", open_browser=True)`
        - `web.save(url="https://example.com", dark_mode=False)`
        """
        # Handle cases where url was passed as positional arg 2, or boolean dark_mode passed in arg 2
        actual_url: Optional[str] = None
        actual_dark_mode: bool = self.dark_mode if dark_mode is None else dark_mode

        if isinstance(url, bool):
            actual_dark_mode = url
        elif isinstance(url, str):
            actual_url = url

        # Also support when filename itself is a URL (e.g. web.save("https://example.com"))
        if isinstance(filename, str) and filename.startswith(("http://", "https://")):
            actual_url = filename
            filename = "web_report.html"

        if actual_url:
            self.scan(actual_url, delay=delay)
        elif self._data is None:
            if not self.url:
                raise ValueError("Target URL not specified. Pass a URL to .save() or .scan().")
            self.scan(self.url, delay=delay)

        d = self.all()

        # Resolve output destination
        target_path = resolve_report_path(filename=filename, save_file_path=save_file_path)
        base_dir = target_path.parent
        if target_path.suffix.lower() != ".html":
            # If target_path is a directory without .html suffix, treat it as the report directory
            base_dir = target_path
            target_path = base_dir / "index.html"

        sections_dir = base_dir / "sections"
        assets_dir = base_dir / "assets"
        for folder in (base_dir, sections_dir, assets_dir):
            folder.mkdir(parents=True, exist_ok=True)

        # 1. Write shared CSS asset
        css_content = get_shared_css(dark_mode=actual_dark_mode)
        (assets_dir / "shared.css").write_text(css_content, encoding="utf-8")

        # 2. Build sections
        builders = {
            "summary": build_summary_html,
            "siteinfo": build_siteinfo_html,
            "security": build_security_html,
            "seo": build_seo_html,
            "performance": build_performance_html,
            "accessibility": build_accessibility_html,
            "technologies": build_technologies_html,
            "dns": build_dns_html,
            "charts": build_charts_html,
        }
        sections_html: Dict[str, str] = {}
        for name, fn in builders.items():
            sec_html = fn(d, dark_mode=actual_dark_mode)
            sections_html[name] = sec_html
            (sections_dir / f"{name}.html").write_text(sec_html, encoding="utf-8")

        # 3. Write index shell
        index_html = build_index_html(d, dark_mode=actual_dark_mode, sections_html=sections_html)
        target_path.write_text(index_html, encoding="utf-8")

        # Also write index.html inside directory if target filename had a different name
        if target_path.name != "index.html":
            (base_dir / "index.html").write_text(index_html, encoding="utf-8")

        # 4. Write summary JSON
        summary_data = self.summary()
        summary_data["report_path"] = str(target_path.resolve())
        (base_dir / "summary.json").write_text(
            json.dumps(summary_data, indent=2), encoding="utf-8"
        )

        log.info("Saved WebAnalyzer report to %s", target_path)

        if open_browser:
            open_in_browser(target_path)

        return str(target_path.resolve())
