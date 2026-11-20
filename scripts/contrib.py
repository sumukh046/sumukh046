#!/usr/bin/env python3
"""Builds assets/contrib.svg: an animated contribution calendar with streak stats.
Uses the GitHub GraphQL API when GITHUB_TOKEN is set, else the public contributions page."""
import json, os, re, sys, html, datetime as dt
from pathlib import Path
from urllib.request import Request, urlopen

USER = os.environ.get("GH_USER", "sumukh046")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path(__file__).resolve().parent.parent / "assets" / "contrib.svg"
UA = {"User-Agent": "profile-contrib-graph"}
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def from_graphql():
    q = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
         "weeks{contributionDays{date contributionCount contributionLevel}}}}}}")
    req = Request("https://api.github.com/graphql",
                  data=json.dumps({"query": q, "variables": {"login": USER}}).encode(),
                  headers={**UA, "Authorization": "bearer " + TOKEN, "Content-Type": "application/json"})
    data = json.load(urlopen(req, timeout=30))
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(d["date"], d["contributionCount"], LEVELS[d["contributionLevel"]])
            for w in weeks for d in w["contributionDays"]]


def from_public_page():
    page = urlopen(Request(f"https://github.com/users/{USER}/contributions", headers=UA), timeout=30).read().decode()
    cells = re.findall(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-\d+-\d+)"[^>]*data-level="(\d)"', page)
    tips = dict(re.findall(r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>\s*([^<]*)', page))
    days = []
    for date, cid, level in cells:
        m = re.match(r"(\d+)", tips.get(cid, "").strip())
        days.append((date, int(m.group(1)) if m else 0, int(level)))
    return days


def get_days():
    days = []
    if TOKEN:
        try:
            days = from_graphql()
        except Exception as e:
            print("GraphQL failed, falling back:", e, file=sys.stderr)
    if not days:
        days = from_public_page()
    days = sorted(set(days))
    if not days:
        raise SystemExit("No contribution data found")
    return days


def streaks(days):
    counts = [c for _, c, _ in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur, i = 0, len(counts) - 1
    if counts[i] == 0:
        i -= 1  # today may still be empty
    while i >= 0 and counts[i] > 0:
        cur += 1
        i -= 1
    return cur, longest


def render(days):
    total = sum(c for _, c, _ in days)
    cur, longest = streaks(days)
    by_wd = [0] * 7
    for d, c, _ in days:
        by_wd[dt.date.fromisoformat(d).weekday()] += c
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    busiest = names[by_wd.index(max(by_wd))] if total else "-"

    first = dt.date.fromisoformat(days[0][0])
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    pos = []
    for d, c, lv in days:
        dd = dt.date.fromisoformat(d)
        pos.append(((dd - start).days // 7, (dd.weekday() + 1) % 7, lv, dd))
    ncols = max(p[0] for p in pos) + 1
    P, S = 18, 14
    labelW = 34
    gridW = ncols * P - 4
    left = (1200 - (labelW + gridW)) / 2
    gx, gy = left + labelW, 132
    H = 306

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{H}" viewBox="0 0 1200 {H}" role="img" aria-labelledby="t">')
    a(f'<title id="t">{total} contributions in the last year, current streak {cur} days, longest streak {longest} days</title>')
    a('''<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset=".55" stop-color="#8b5cf6"/><stop offset="1" stop-color="#f472b6"/></linearGradient>
<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".10"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<style>
.m{font-family:'JetBrains Mono','Fira Code','SFMono-Regular',Consolas,'Liberation Mono','Courier New',monospace}
.s{font-family:'Inter','Segoe UI','Helvetica Neue',Arial,sans-serif}
.c0{fill:#0f1830}.c1{fill:#0e7490}.c2{fill:#22d3ee}.c3{fill:#8b5cf6}.c4{fill:#f472b6}
.cell{transform-box:fill-box;transform-origin:center;animation:pop .55s cubic-bezier(.2,.9,.3,1.3) backwards}
.hot{animation:pop .55s cubic-bezier(.2,.9,.3,1.3) backwards,glow 3.4s ease-in-out infinite}
.rise{animation:rise .8s ease-out backwards}
.ring{fill:none;stroke:#e6edf3;stroke-width:1.5;animation:ring 2s ease-in-out infinite}
@keyframes pop{from{opacity:0;transform:scale(.2)}}
@keyframes glow{0%,100%{opacity:.72}50%{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(10px)}}
@keyframes ring{0%,100%{stroke-opacity:.25}50%{stroke-opacity:1}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
</style>''')
    a('<rect x=".5" y=".5" width="1199" height="%d" rx="16" fill="#070b17" stroke="#1c2745"/>' % (H - 1))
    stats = [(str(total), "contributions in the last year"), (str(cur), "day current streak"),
             (str(longest), "day longest streak"), (busiest, "busiest day of the week")]
    for i, (num, lab) in enumerate(stats):
        x = left + i * 262
        a(f'<g class="rise" style="animation-delay:{i*0.12:.2f}s"><text x="{x:.0f}" y="62" class="s" font-size="40" font-weight="800" fill="url(#g)">{html.escape(num)}</text>'
          f'<text x="{x:.0f}" y="86" class="m" font-size="13" fill="#8392b3">{html.escape(lab)}</text></g>')
    # weekday labels
    for r, nm in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        a(f'<text x="{left:.0f}" y="{gy + r*P + 11}" class="m" font-size="11" fill="#6b7a99">{nm}</text>')
    # month labels
    prev, last_x = None, -99
    for c in range(ncols):
        d = start + dt.timedelta(days=7 * c)
        if d.month != prev:
            x = gx + c * P
            if x - last_x >= 40 and c < ncols - 1:
                a(f'<text x="{x:.0f}" y="{gy - 10}" class="m" font-size="11" fill="#6b7a99">{d.strftime("%b")}</text>')
                last_x = x
            prev = d.month
    # cells
    last = None
    for col, row, lv, dd in pos:
        x, y = gx + col * P, gy + row * P
        delay = 0.3 + col * 0.022 + row * 0.01
        if lv >= 3:
            a(f'<rect class="cell hot c{lv}" x="{x:.1f}" y="{y}" width="{S}" height="{S}" rx="3.5" style="animation-delay:{delay:.2f}s,{1.6 + (col % 9) * 0.3:.1f}s"/>')
        else:
            a(f'<rect class="cell c{lv}" x="{x:.1f}" y="{y}" width="{S}" height="{S}" rx="3.5" style="animation-delay:{delay:.2f}s"/>')
        last = (x, y)
    a(f'<rect class="ring" x="{last[0]-2:.1f}" y="{last[1]-2}" width="{S+4}" height="{S+4}" rx="5"/>')
    # sweep highlight across the grid
    a(f'<clipPath id="gc"><rect x="{gx:.0f}" y="{gy}" width="{gridW}" height="{7*P-4}"/></clipPath>')
    a(f'<g clip-path="url(#gc)"><rect x="{gx-160:.0f}" y="{gy}" width="160" height="{7*P-4}" fill="url(#sweep)">'
      f'<animateTransform attributeName="transform" type="translate" from="0 0" to="{gridW+320}" dur="6s" begin="2.2s" repeatCount="indefinite"/></rect></g>')
    # legend
    lx = gx + gridW - 5 * P - 70
    ly = gy + 7 * P + 14
    a(f'<text x="{lx:.0f}" y="{ly+11}" class="m" font-size="11" fill="#6b7a99">Less</text>')
    for i in range(5):
        a(f'<rect class="c{i}" x="{lx + 34 + i*P:.0f}" y="{ly}" width="{S}" height="{S}" rx="3.5"/>')
    a(f'<text x="{lx + 34 + 5*P + 4:.0f}" y="{ly+11}" class="m" font-size="11" fill="#6b7a99">More</text>')
    a(f'<text x="{left:.0f}" y="{ly+11}" class="m" font-size="11" fill="#4b5878">updated {days[-1][0]}</text>')
    a('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    days = get_days()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(days), encoding="utf-8")
    print(f"wrote {OUT} ({len(days)} days, {sum(c for _, c, _ in days)} contributions)")
