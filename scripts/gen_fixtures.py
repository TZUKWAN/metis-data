"""Generate all test fixture pages + data files (idempotent).

Pages (served by pytest fixture_server on 127.0.0.1 random port):
  pages/locator_test.html    — Download button moves top→bottom (A7)
  pages/captcha.html ...     — intervention fixtures (A9)
  pages/login.html           — valid/invalid credentials (A12)
  pages/register.html        — registration result states (A13)
  pages/downloads.html       — real browser download trigger (A16)
Data fixtures (A15/A17/A18/A20): multi-format files, 120MB csv, malicious zips.
"""
from __future__ import annotations

import io
import json
import random
import sqlite3
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "metis" / "backend" / "tests" / "fixtures"
PAGES = ROOT / "pages"
DATA = ROOT / "data"

BASE_JS = ""


def w(name: str, html: str) -> None:
    (PAGES / name).write_text(html, encoding="utf-8")


def gen_pages() -> None:
    PAGES.mkdir(parents=True, exist_ok=True)
    style = "<style>body{font-family:sans-serif;margin:40px} .btn{padding:12px 24px;font-size:18px} input{padding:8px;margin:6px 0;display:block} .msg{color:red}</style>"

    w("index.html", f"<html><head><title>Metis Fixture Home</title>{style}</head><body><h1>Fixture Home</h1><a id='to-locator' href='locator_test.html'>Locator test</a><a id='to-login' href='login.html'>Login</a><a id='to-register' href='register.html'>Register</a><a id='to-downloads' href='downloads.html'>Downloads</a></body></html>")

    # A7: locator target moves from top to bottom dynamically
    w("locator_test.html", f"""<html><head><title>Locator Test</title>{style}</head>
<body>
<div id="top"><button id="dl-btn" class="btn" onclick="moveButton()">Download</button></div>
<div style="height:60px"></div>
<button id="mover" class="btn" onclick="moveButton()">Move Button Now</button>
<div id="spacer" style="height:10px"></div>
<script>
let moved=false;
function moveButton(){{
  if(moved) return; moved=true;
  const b=document.getElementById('dl-btn');
  b.remove();
  const d=document.createElement('div'); d.style.marginTop='1400px';
  d.appendChild(b); document.body.appendChild(d);
}}
setTimeout(moveButton, 2500);
</script>
<div style="height:1600px"></div>
</body></html>""")

    # A9 intervention fixtures
    w("captcha.html", f"<html><head><title>Verify</title>{style}</head><body><h2>Human verification</h2><div class='g-recaptcha'>reCAPTCHA widget placeholder — prove you are not a robot</div><form><input placeholder='captcha code'><button>CHECK</button></form></body></html>")
    w("mfa.html", f"<html><head><title>Two-factor</title>{style}</head><body><h2>Two-factor authentication</h2><p>Enter the 6-digit code from your authenticator app.</p><input placeholder='2FA code'><button>Verify</button></body></html>")
    w("phone_otp.html", f"<html><head><title>SMS</title>{style}</head><body><h2>短信验证码</h2><p>我们已发送验证码到您的手机。</p><input placeholder='验证码'><button>提交</button></body></html>")
    w("institution.html", f"<html><head><title>Institutional Login</title>{style}</head><body><h2>Institutional Login (Shibboleth)</h2><p>Select your organization to continue.</p><select><option>University A</option></select><button>Continue</button></body></html>")
    w("identity.html", f"<html><head><title>Identity Verification</title>{style}</head><body><h2>实名认证</h2><p>请上传身份证以完成实名认证。</p><input type='file'><button>Upload</button></body></html>")
    w("agreement.html", f"<html><head><title>Restricted Data Agreement</title>{style}</head><body><h2>Restricted Data Use Agreement</h2><p>You must sign a legally binding data use agreement before accessing restricted data.</p><button id='agree'>I agree</button></body></html>")
    w("payment.html", f"<html><head><title>Checkout</title>{style}</head><body><h2>Payment required</h2><p>Complete your purchase to download this dataset ($49.00).</p><button id='pay'>Pay now</button></body></html>")

    # A12 login fixture
    w("login.html", f"""<html><head><title>Fixture Login</title>{style}</head><body>
<h2>Sign in</h2>
<form id="login-form" onsubmit="return doLogin()">
<input id="email" placeholder="email"><input id="password" type="password" placeholder="password">
<button id="login-btn" type="submit">Sign in</button><p id="err" class="msg"></p></form>
<script>
function doLogin(){{
  const e=document.getElementById('email').value, p=document.getElementById('password').value;
  if(e==='researcher@example.edu' && p==='Corr3ct-Passw0rd!'){{ localStorage.setItem('metis_logged_in','1'); location.href='login_success.html'; return false; }}
  document.getElementById('err').textContent='Invalid credentials'; return false;
}}
</script></body></html>""")
    w("login_success.html", f"""<html><head><title>My Account</title>{style}</head><body onload="if(!localStorage.getItem('metis_logged_in')){{location.href='login.html'}}else{{document.getElementById('welcome-user').textContent='researcher@example.edu'}}">
<h1>Welcome back, <span id="welcome-user"></span></h1><a href='downloads.html'>Downloads</a></body></html>""")

    # A13 registration fixture
    w("register.html", f"""<html><head><title>Fixture Register</title>{style}</head><body>
<h2>Create account</h2>
<form onsubmit="return doReg()">
<input id="name" placeholder="full name"><input id="email" placeholder="email">
<input id="password" type="password" placeholder="password">
<label><input type="checkbox" id="captcha" style="display:inline;width:auto"> simulate CAPTCHA</label>
<button id="reg-btn" type="submit">Register</button><p id="msg" class="msg"></p></form>
<script>
const EXISTING=['taken@example.edu'];
function doReg(){{
  if(document.getElementById('captcha').checked){{ document.getElementById('msg').textContent='CAPTCHA required'; return false; }}
  const e=document.getElementById('email').value, p=document.getElementById('password').value;
  if(EXISTING.includes(e)){{ document.getElementById('msg').textContent='duplicate email: an account with this email already exists'; return false; }}
  if(p.length<8 || !/[A-Z]/.test(p) || !/[a-z]/.test(p) || !/[0-9]/.test(p)){{ document.getElementById('msg').textContent='password rule failed: need 8+ chars with upper, lower, digit'; return false; }}
  if(e==='verify@example.edu'){{ location.href='verify_email.html'; return false; }}
  location.href='register_done.html?email='+encodeURIComponent(e); return false;
}}
</script></body></html>""")
    w("register_done.html", f"<html><head><title>Account created</title>{style}</head><body><h1>Account created successfully</h1><p id='who'>Registration complete.</p></body></html>")
    w("verify_email.html", f"<html><head><title>Verify email</title>{style}</head><body><h1>Check your inbox</h1><p>We sent a verification link. Account pending until verified.</p></body></html>")

    # A16 download fixture
    w("downloads.html", f"<html><head><title>Downloads</title>{style}</head><body><h1>Dataset downloads</h1><a id='dl-link' class='btn' href='../data/panel_data.csv' download>Download</a><p id='status'></p><script>document.getElementById('dl-link').addEventListener('click',()=>{{document.getElementById('status').textContent='download successful';}});</script></body></html>")

    # search page for browser-search E2E
    w("search.html", f"""<html><head><title>Fixture Data Catalog</title>{style}</head><body>
<h1>Catalog search</h1>
<input id="q" placeholder="Search datasets..."><button id="search-btn" onclick="runSearch()">Search</button>
<div id="results"></div>
<script>
function runSearch(){{
  const q=document.getElementById('q').value.toLowerCase();
  const items=[{{t:'Youth unemployment panel 2015-2023',u:'dataset_a.html'}},{{t:'GDP per capita world table',u:'dataset_b.html'}},{{t:'Education attainment OECD',u:'dataset_c.html'}}];
  document.getElementById('results').innerHTML=items.filter(i=>!q||i.t.toLowerCase().includes(q.split(' ')[0])).map(i=>`<div><a href="${{i.u}}">${{i.t}}</a></div>`).join('');
}}
</script></body></html>""")
    for i, t in [("a", "Youth unemployment panel 2015-2023"), ("b", "GDP per capita world table"), ("c", "Education attainment OECD")]:
        w(f"dataset_{i}.html", f"<html><head><title>{t}</title>{style}</head><body><h1>{t}</h1><a href='../data/panel_data.csv'>Download</a></body></html>")


def gen_data() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    # panel_data.csv (golden-ish: countries x years)
    rows = ["country_name,iso3,year,gdp_per_capita"]
    for c, iso in [("United States", "USA"), ("China", "CHN"), ("Germany", "DEU"), ("Brazil", "BRA"), ("India", "IND")]:
        for y in range(2015, 2024):
            rows.append(f"{c},{iso},{y},{round(rng.uniform(2000, 70000), 1)}")
    (DATA / "panel_data.csv").write_text("\n".join(rows), encoding="utf-8")

    # dataset B: youth unemployment (different naming for join test)
    rows = ["country,country_code,year,youth_unemployment"]
    for c, code in [("United States", "USA"), ("China", "CHN"), ("Germany", "DEU"), ("Brazil", "BRA"), ("Japan", "JPN")]:
        for y in range(2015, 2024):
            rows.append(f"{c},{code},{y},{round(rng.uniform(5, 25), 1)}")
    (DATA / "youth_unemployment.csv").write_text("\n".join(rows), encoding="utf-8")

    # GBK Chinese CSV
    pd.DataFrame({"城市": ["北京", "上海", "广州", "深圳", "武汉"], "年份": [2020] * 5, "生产总值": [36102, 38700, 25019, 27670, 15616]}).to_csv(DATA / "china_cities_gbk.csv", index=False, encoding="gbk")

    # TSV
    pd.DataFrame({"name": ["a", "b", "c"], "value": [1.5, 2.5, 3.5]}).to_csv(DATA / "simple.tsv", sep="\t", index=False)

    # XLS (via openpyxl as xlsx is fine; real .xls via xlwt not available — use xlsx + document) and XLSX multi-sheet
    with pd.ExcelWriter(DATA / "multi_sheet.xlsx", engine="openpyxl") as xw:
        pd.DataFrame({"country": ["USA", "CHN"], "gdp": [21000, 15000]}).to_excel(xw, sheet_name="gdp", index=False)
        pd.DataFrame({"country": ["USA", "CHN"], "unemp": [3.9, 5.1]}).to_excel(xw, sheet_name="unemployment", index=False)

    # JSON / JSONL
    (DATA / "sample.json").write_text(json.dumps([{"id": 1, "v": "x"}, {"id": 2, "v": "y"}]), encoding="utf-8")
    (DATA / "sample.jsonl").write_text('\n'.join(json.dumps({"i": i, "val": i * 2.5}) for i in range(5)), encoding="utf-8")

    # Parquet
    pd.DataFrame({"k": range(10), "v": np.random.default_rng(1).normal(size=10)}).to_parquet(DATA / "sample.parquet", index=False)

    # DTA with labels; SAV with labels; SAS xport
    df = pd.DataFrame({"gender": [0, 1, 0, 1], "income": [1200.0, 4500.0, 3200.0, 5100.0]})
    try:
        df.to_stata(DATA / "labels.dta", write_index=False, variable_labels={"gender": "Respondent gender", "income": "Monthly income"})
        import pyreadstat

        pyreadstat.write_sav(df, str(DATA / "labels.sav"), column_labels=["Gender coding", "Monthly income"], variable_value_labels={"gender": {0: "male", 1: "female"}})
        pyreadstat.write_xport(df, str(DATA / "labels.xpt"), table_name="LAB", file_label="labels fixture")
    except Exception as e:  # noqa: BLE001
        print("stat-format fixture warning:", e)

    # GeoJSON
    (DATA / "points.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [116.4, 39.9]}, "properties": {"city": "Beijing", "code": 110000}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [114.3, 30.6]}, "properties": {"city": "Wuhan", "code": 420100}},
        ],
    }), encoding="utf-8")

    # Shapefile via pyshp
    try:
        import shapefile

        shp = shapefile.Writer(str(DATA / "points_shp"), shapeType=shapefile.POINT)
        shp.field("city", "C", size=40)
        shp.field("code", "N", size=10)
        shp.point(116.4, 39.9)
        shp.record("Beijing", 110000)
        shp.point(114.3, 30.6)
        shp.record("Wuhan", 420100)
        shp.close()
    except Exception as e:  # noqa: BLE001
        print("shapefile fixture warning:", e)

    # NetCDF
    try:
        from netCDF4 import Dataset

        ds = Dataset(DATA / "climate.nc", "w", format="NETCDF4")
        ds.createDimension("time", 12)
        ds.createDimension("lat", 3)
        ds.createDimension("lon", 4)
        t = ds.createVariable("time", "f4", ("time",))
        lat = ds.createVariable("lat", "f4", ("lat",))
        lon = ds.createVariable("lon", "f4", ("lon",))
        temp = ds.createVariable("temperature", "f4", ("time", "lat", "lon"))
        t.units = "months since 2020-01"
        temp.long_name = "surface temperature anomaly"
        t[:] = np.arange(12)
        lat[:] = [30, 40, 50]
        lon[:] = [100, 110, 120, 130]
        temp[:] = np.random.default_rng(2).normal(0, 0.5, (12, 3, 4))
        ds.close()
    except Exception as e:  # noqa: BLE001
        print("netcdf fixture warning:", e)

    # SQLite
    con = sqlite3.connect(DATA / "sample.db")
    con.execute("DROP TABLE IF EXISTS observations")
    con.execute("CREATE TABLE observations (country TEXT, year INT, value REAL)")
    con.executemany("INSERT INTO observations VALUES (?,?,?)", [("USA", 2020, 1.1), ("CHN", 2020, 6.5), ("DEU", 2021, 3.2)])
    con.commit()
    con.close()

    # HTML table
    (DATA / "table.html").write_text("<html><body><table><tr><th>country</th><th>year</th><th>rate</th></tr><tr><td>USA</td><td>2021</td><td>5.4</td></tr><tr><td>CHN</td><td>2021</td><td>5.0</td></tr></table></body></html>", encoding="utf-8")

    # A17: HTML disguised as CSV / ZIP
    (DATA / "login_page_disguised.csv").write_text("<html><head><title>Sign in</title></head><body><form><input name='password'></form></body></html>", encoding="utf-8")
    (DATA / "error_page_disguised.zip").write_bytes(b"HTTP/1.1 500 Internal Server Error\nContent-Type: text/html\n\n<html><body><h1>Server Error</h1></body></html>")

    # A18: safe-extraction fixtures
    with zipfile.ZipFile(DATA / "normal.zip", "w") as z:
        z.writestr("data/file1.csv", "a,b\n1,2\n3,4\n")
        z.writestr("data/file2.csv", "a,b\n5,6\n")
    with zipfile.ZipFile(DATA / "evil_slip.zip", "w") as z:
        z.writestr("../evil.txt", "pwned")
        z.writestr("ok.txt", "fine")
    with zipfile.ZipFile(DATA / "bomb.zip", "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("bomb.csv", b"0\n" * (512 * 1024 * 1024 // 2))  # 512MB uncompressed -> bomb guard
    with zipfile.ZipFile(DATA / "many_files.zip", "w") as z:
        for i in range(3000):
            z.writestr(f"f{i}.txt", "x")

    # A15: 120MB CSV (streaming download test)
    big = DATA / "big_measurements.csv"
    if not big.exists() or big.stat().st_size < 100 * 1024 * 1024:
        header = "sensor_id,timestamp,value,quality\n"
        with big.open("w", encoding="utf-8") as f:
            f.write(header)
            chunk = []
            for i in range(4_200_000):
                chunk.append(f"S{rng.randrange(1, 500)},2020-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d},{rng.random()*100:.4f},G")
                if len(chunk) >= 50_000:
                    f.write("\n".join(chunk) + "\n")
                    chunk = []
            if chunk:
                f.write("\n".join(chunk) + "\n")
    print(f"big csv: {big.stat().st_size/1e6:.1f} MB")

    # profile test: 100MB+ CSV
    prof = DATA / "profile_100mb.csv"
    if not prof.exists() or prof.stat().st_size < 100 * 1024 * 1024:
        with prof.open("w", encoding="utf-8") as f:
            f.write("id,group,value,category\n")
            for i in range(4_200_000):
                f.write(f"{i},g{i % 7},{rng.random():.6f},cat{i % 4}\n")
    print(f"profile csv: {prof.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    gen_pages()
    gen_data()
    print("fixtures generated under", ROOT)
