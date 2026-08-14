#! /usr/bin/env python

# Use this script to populate bot.txt with names from https://www.procyclingstats.com
# Refer to http://cdn.zwift.com/gameassets/GameDictionary.xml
# pip install beautifulsoup4 country-converter fuzzywuzzy curl_cffi
# scripts/get_pro_names.py -h


from bs4 import BeautifulSoup
import urllib.request
import urllib.parse
import json
import re
import country_converter as coco
import argparse
import os
import sys
import xml.etree.ElementTree as ET
import unicodedata
from fuzzywuzzy import process
from fuzzywuzzy import fuzz

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


_SESSION = None


def fetch_html(url):
    global _SESSION
    if _SESSION is None:
        from curl_cffi.requests import Session

        _SESSION = Session(impersonate="chrome")
        try:
            _SESSION.get(
                "https://www.procyclingstats.com/",
                headers=BROWSER_HEADERS,
                timeout=30,
            )
        except Exception as e:
            print("SESSION WARM FAILED: %s" % e)
    resp = _SESSION.get(url, headers=BROWSER_HEADERS, timeout=30)
    if resp.status_code != 200 or b"cf-mitigated" in resp.content:
        try:
            resp = _SESSION.get(url, headers=BROWSER_HEADERS, timeout=30)
        except Exception as e:
            print("FETCH RETRY FAILED: %s (%s)" % (url, e))
    if resp.status_code != 200:
        print("FETCH WARNING: %s returned HTTP %d" % (url, resp.status_code))
    return resp.content


base_url = "https://www.procyclingstats.com/rankings.php?filter=Filter"
cc = coco.CountryConverter()

TEAMS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "get_pro_names.json"
)
with open(TEAMS_FILE, encoding="utf-8") as _tf:
    teams = json.load(_tf)


MATCH_THRESHOLD = 85


TEAM_STOPWORDS = {
    "team",
    "cycling",
    "pro",
    "men",
    "women",
    "racing",
    "continental",
    "academy",
    "dev",
    "development",
    "u23",
    "world",
    "tour",
    "elite",
    "equipe",
    "junior",
}


GEAR_STOPWORDS = {"wheels"}


def normalize_team(name):
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


TEAM_INDEX = {normalize_team(k): k for k in teams}

TEAM_PAGE_CACHE = {}


def fetch_team_name(href):
    if href in TEAM_PAGE_CACHE:
        return TEAM_PAGE_CACHE[href]
    url = (
        href
        if href.startswith("http")
        else "https://www.procyclingstats.com/" + href.lstrip("/")
    )
    try:
        page = BeautifulSoup(fetch_html(url), "html.parser")
        name = ""
        if page.title and page.title.string:
            name = page.title.string.split("|")[0].strip()
        TEAM_PAGE_CACHE[href] = name
        return name
    except Exception as e:
        print("TEAMPAGE FETCH FAILED: %s (%s)" % (url, e))
        TEAM_PAGE_CACHE[href] = None
        return None


TEAM_CODE_CACHE = {}


def fetch_team_code(href):
    if href in TEAM_CODE_CACHE:
        return TEAM_CODE_CACHE[href]
    url = (
        href
        if href.startswith("http")
        else "https://www.procyclingstats.com/" + href.lstrip("/")
    )
    code = ""
    try:
        page = BeautifulSoup(fetch_html(url), "html.parser")
        for title in page.select("div.title"):
            if "Abbreviation" in title.get_text():
                val = title.find_next_sibling("div")
                if val:
                    code = val.get_text(strip=True)
                break
    except Exception as e:
        print("TEAMCODE FETCH FAILED: %s (%s)" % (url, e))
    TEAM_CODE_CACHE[href] = code
    return code


def match_team(raw, href=None, use_teampage=False, threshold=MATCH_THRESHOLD):
    norm = normalize_team(raw)
    if norm in TEAM_INDEX:
        return TEAM_INDEX[norm]
    best = process.extractOne(raw, list(TEAM_INDEX.keys()), scorer=fuzz.token_set_ratio)
    if best and best[1] >= threshold:
        print(
            "FUZZY TEAM MATCH: %r -> %r (score %d)"
            % (raw, TEAM_INDEX[best[0]], best[1])
        )
        return TEAM_INDEX[best[0]]
    if use_teampage and href:
        canon = fetch_team_name(href)
        if canon:
            cnorm = normalize_team(canon)
            if cnorm in TEAM_INDEX:
                print("TEAMPAGE MATCH: %r -> %r" % (canon, TEAM_INDEX[cnorm]))
                return TEAM_INDEX[cnorm]
            best2 = process.extractOne(
                canon, list(TEAM_INDEX.keys()), scorer=fuzz.token_set_ratio
            )
            if best2 and best2[1] >= threshold:
                print(
                    "TEAMPAGE FUZZY MATCH: %r -> %r (score %d)"
                    % (canon, TEAM_INDEX[best2[0]], best2[1])
                )
                return TEAM_INDEX[best2[0]]
    print("UNMATCHED TEAM: %r" % raw)
    return None


def fuzzy_jersey(raw_team, tmp):
    q = strip_accents(raw_team).lower()
    norm_jerseys = {strip_accents(k).lower(): k for k in jerseys}
    best_match = process.extractOne(
        q, list(norm_jerseys.keys()), scorer=fuzz.token_set_ratio
    )
    print(
        "%s %s : %s - %s" % (tmp["first_name"], tmp["last_name"], raw_team, best_match)
    )
    return jerseys[norm_jerseys[best_match[0]]]


def get_pros(
    url,
    male,
    get_jersey,
    get_equipment,
    team_abbrv,
    use_teampage=False,
    threshold=MATCH_THRESHOLD,
):
    data = []
    seen = set()

    site = fetch_html(url)
    soup = BeautifulSoup(site, "html.parser")

    tmp = {}
    for td in soup.find_all("td"):
        if td.span and td.contents[0]:
            tmp = {}
            span_cls = td.span.get("class") or []
            if "flag" in span_cls:
                code = td.span.get_attribute_list("class")[1]
                tmp["country_code"] = cc.convert(names=code, to="ISOnumeric")
                tmp["is_male"] = male
                if td.a:
                    fn = []
                    ln = []
                    for n in td.a.contents[0].split():
                        if n.isupper():
                            ln.append(n.title())
                        else:
                            fn.append(n)
                    tmp["first_name"] = " ".join(fn)
                    tmp["last_name"] = " ".join(ln)
        if td.a and td.contents[0]:
            if "cu600" in repr(td) and td.a.contents:
                if "first_name" in tmp:
                    raw_team = td.a.contents[0]
                    team_key = match_team(
                        raw_team, td.a.get("href"), use_teampage, threshold
                    )
                    team = teams.get(team_key) if team_key else None
                    if team_abbrv and team and "abv" in team:
                        tmp["last_name"] += " (" + team["abv"] + ")"
                    if get_jersey:
                        if team:
                            if not male and "womens_jersey_signature" in team:
                                tmp["ride_jersey"] = team["womens_jersey_signature"]
                            elif "jersey_signature" in team:
                                tmp["ride_jersey"] = team["jersey_signature"]
                            else:
                                tmp["ride_jersey"] = fuzzy_jersey(raw_team, tmp)
                        else:
                            tmp["ride_jersey"] = fuzzy_jersey(raw_team, tmp)
                    if get_equipment and team:
                        if "bike_signature" in team:
                            tmp["bike_frame"] = team["bike_signature"]
                        if "bike_frame_colour_signature" in team:
                            tmp["bike_frame_colour"] = (
                                team["bike_frame_colour_signature"] << 32
                            )
                        if "front_wheel_signature" in team:
                            tmp["bike_wheel_front"] = team["front_wheel_signature"]
                        if "rear_wheel_signature" in team:
                            tmp["bike_wheel_rear"] = team["rear_wheel_signature"]
                        if "helmet_signature" in team:
                            tmp["ride_helmet_type"] = team["helmet_signature"]

                    key = (
                        tmp.get("first_name"),
                        tmp.get("last_name"),
                        tmp.get("country_code"),
                    )
                    if key not in seen:
                        seen.add(key)
                        data.append(tmp)

    return data


gd_file = "GameDictionary.xml"
if not os.path.isfile(gd_file):
    open(gd_file, "wb").write(
        urllib.request.urlopen("http://cdn.zwift.com/gameassets/%s" % gd_file).read()
    )
tree = ET.parse(gd_file)
jerseys = {}
for x in tree.findall("./JERSEYS/JERSEY"):
    jerseys[x.get("name")] = int(x.get("signature"))

bikes = {}
bikes_class = {}
front_wheels = {}
rear_wheels = {}
helmets = {}
shoes = {}
paintjobs = {}
for x in tree.findall("./BIKEFRAMES/BIKEFRAME"):
    if x.get("isTT") == "1":
        continue
    bikes[x.get("name")] = int(x.get("signature"))
    bikes_class[x.get("name")] = x.get("bikeClass")
for x in tree.findall("./BIKEFRONTWHEELS/BIKEFRONTWHEEL"):
    front_wheels[x.get("name")] = int(x.get("signature"))
for x in tree.findall("./BIKEREARWHEELS/BIKEREARWHEEL"):
    rear_wheels[x.get("name")] = int(x.get("signature"))
for x in tree.findall("./HEADGEARS/HEADGEAR"):
    helmets[x.get("name")] = int(x.get("signature"))
for x in tree.findall("./BIKESHOES/BIKESHOE"):
    shoes[x.get("name")] = int(x.get("signature"))
for x in tree.findall("./PAINTJOBS/PAINTJOB"):
    paintjobs[x.get("name")] = int(x.get("signature"))


def derive_abv(name):
    caps = [
        w.upper()
        for w in name.split()
        if w.isupper() and w.isalpha() and 1 < len(w) <= 4
    ]
    if caps:
        return "".join(caps)[:4]
    words = [w for w in normalize_team(name).split() if w not in TEAM_STOPWORDS]
    if not words:
        return ""
    return "".join(w[0] for w in words).upper()[:3]


def best_match(query, choices):
    if not query or not choices:
        return None, 0
    norm_choices = {strip_accents(k).lower(): k for k in choices}
    best = None
    best_score = 0
    qbase = " ".join(
        w for w in strip_accents(query).lower().split() if w not in GEAR_STOPWORDS
    )
    for q in (qbase, qbase.replace(" ", "")):
        m = process.extractOne(
            q, list(norm_choices.keys()), scorer=fuzz.token_set_ratio
        )
        if m and m[1] > best_score:
            best = m
            best_score = m[1]
    if best:
        return norm_choices[best[0]], best[1]
    return None, 0


BIKE_PRIORITY = {"HIGH_END": 0, "MID_RANGE": 1, "ENTRY": 2, "CONCEPT": 3}


def best_bike(query):
    if not query:
        return None, 0
    norm_bikes = {strip_accents(k).lower(): k for k in bikes}
    best = None
    best_score = 0
    qbase = " ".join(
        w for w in strip_accents(query).lower().split() if w not in GEAR_STOPWORDS
    )
    for q in (qbase, qbase.replace(" ", "")):
        cands = process.extract(
            q, list(norm_bikes.keys()), scorer=fuzz.token_set_ratio, limit=10
        )
        cands = [c for c in cands if c[1] >= MATCH_THRESHOLD]
        if not cands:
            continue
        cands.sort(
            key=lambda c: (
                BIKE_PRIORITY.get(bikes_class.get(norm_bikes[c[0]], ""), 9),
                -c[1],
            )
        )
        c = cands[0]
        if c[1] > best_score:
            best = c
            best_score = c[1]
    if best:
        return norm_bikes[best[0]], best[1]
    return None, 0


def resolve_paintjob(team_name, bike_brand):
    tnorm = normalize_team(team_name)
    bnorm = normalize_team(bike_brand) if bike_brand else ""
    tokens = [t for t in tnorm.split() if len(t) > 2 and t not in TEAM_STOPWORDS]
    preferred = None
    fallback = None
    for name, sig in paintjobs.items():
        if "-" not in name:
            continue
        raw_model, raw_suffix = name.split("-", 1)
        model = normalize_team(raw_model)
        suffix = normalize_team(raw_suffix)
        if not any(t in suffix.split() for t in tokens):
            continue
        if bnorm and model.split()[0] == bnorm.split()[0]:
            preferred = (name, sig, raw_model)
        elif fallback is None:
            fallback = (name, sig, raw_model)
    if preferred:
        return preferred[0], preferred[1], preferred[2], True
    if fallback:
        return fallback[0], fallback[1], fallback[2], False
    return None, 0, None, False


def parse_gear(team_href):
    slug = team_href.rstrip("/").split("/")[-1]
    url = "https://www.procyclingstats.com/team/%s/more/gear" % slug
    gear = {}
    try:
        soup = BeautifulSoup(fetch_html(url), "html.parser")
        for li in soup.find_all("li"):
            parts = [s.strip() for s in li.stripped_strings]
            if len(parts) >= 2:
                label = parts[0].rstrip(":").lower()
                brand = parts[1]
                if label == "bike":
                    gear["bike"] = brand
                elif label == "helmets":
                    gear["helmet"] = brand
                elif label == "shoes":
                    gear["shoe"] = brand
                elif label == "wheels":
                    gear["wheel"] = brand
    except Exception as e:
        print("GEAR FETCH FAILED: %s (%s)" % (url, e))
    return gear


def fetch_team_rankings(limit):
    pages = [
        ("https://www.procyclingstats.com/rankings/teams", False),
        ("https://www.procyclingstats.com/rankings/we/teams", True),
    ]
    found = []
    seen = set()
    for base, is_women in pages:
        offset = 0
        page_count = 0
        while page_count < limit:
            url = base if offset == 0 else "%s&offset=%d" % (base, offset)
            try:
                soup = BeautifulSoup(fetch_html(url), "html.parser")
            except Exception as e:
                print("RANKINGS FETCH FAILED: %s (%s)" % (url, e))
                break
            links = soup.select("a[href^='team/']")
            got = False
            for a in links:
                h = a.get("href")
                href = h if isinstance(h, str) else ""
                if href in seen or not href.startswith("team/"):
                    continue
                name = a.get_text(strip=True)
                if not name:
                    continue
                seen.add(href)
                found.append((name, href, is_women))
                got = True
                page_count += 1
                if page_count >= limit:
                    break
            if not got:
                break
            offset += 100
    return found


def generate_teams(limit):
    results = {}
    for team_name, href, is_women in fetch_team_rankings(limit):
        entry = {}
        abv = fetch_team_code(href)
        if abv:
            entry["abv"] = abv
        jname, jscore = best_match(team_name, jerseys)
        if jname and jscore >= MATCH_THRESHOLD:
            print("JERSEY: %r -> %r (score %d)" % (team_name, jname, jscore))
            if is_women:
                entry["womens_jersey_name"] = jname
                entry["womens_jersey_signature"] = jerseys[jname]
            entry["jersey_name"] = jname
            entry["jersey_signature"] = jerseys[jname]
        else:
            print(
                "UNMATCHED JERSEY: %r (best %r score %d)" % (team_name, jname, jscore)
            )

        gear = parse_gear(href)
        brand = gear.get("bike")

        pjname, pjsig, model, ok = resolve_paintjob(team_name, brand)
        if pjname and ok:
            print("PAINTJOB: %r -> %r (model %r)" % (team_name, pjname, model))
            entry["bike_frame_colour_name"] = pjname
            entry["bike_frame_colour_signature"] = pjsig
        else:
            if pjname:
                print(
                    "PAINTJOB (brand mismatch, ignored): %r -> %r" % (team_name, pjname)
                )
            if brand:
                bname, bscore = best_bike(brand)
                if bname and bscore >= MATCH_THRESHOLD:
                    print("FUZZY BIKE: %r -> %r (score %d)" % (brand, bname, bscore))
                    entry["bike_name"] = bname
                    entry["bike_signature"] = bikes[bname]
                else:
                    print(
                        "UNMATCHED BIKE: %r (best %r score %d)" % (brand, bname, bscore)
                    )
            else:
                print("NO GEAR BIKE: %r" % team_name)

        if gear.get("wheel"):
            wname, wscore = best_match(gear["wheel"], front_wheels)
            if wname and wscore >= MATCH_THRESHOLD:
                print("FUZZY FRONT WHEEL: %r -> %r" % (gear["wheel"], wname))
                entry["front_wheel_name"] = wname
                entry["front_wheel_signature"] = front_wheels[wname]
            else:
                print("UNMATCHED FRONT WHEEL: %r" % gear["wheel"])
            wname2, wscore2 = best_match(gear["wheel"], rear_wheels)
            if wname2 and wscore2 >= MATCH_THRESHOLD:
                print("FUZZY REAR WHEEL: %r -> %r" % (gear["wheel"], wname2))
                entry["rear_wheel_name"] = wname2
                entry["rear_wheel_signature"] = rear_wheels[wname2]
            else:
                print("UNMATCHED REAR WHEEL: %r" % gear["wheel"])

        if gear.get("helmet"):
            hname, hscore = best_match(gear["helmet"], helmets)
            if hname and hscore >= MATCH_THRESHOLD:
                print("FUZZY HELMET: %r -> %r" % (gear["helmet"], hname))
                entry["helmet_name"] = hname
                entry["helmet_signature"] = helmets[hname]
            else:
                print("UNMATCHED HELMET: %r" % gear["helmet"])

        if gear.get("shoe"):
            sname, sscore = best_match(gear["shoe"], shoes)
            if sname and sscore >= MATCH_THRESHOLD:
                print("FUZZY SHOE: %r -> %r" % (gear["shoe"], sname))
                entry["shoe_name"] = sname
                entry["shoe_signature"] = shoes[sname]
            else:
                print("UNMATCHED SHOE: %r" % gear["shoe"])

        results[team_name] = entry

    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("WROTE %d teams to %s" % (len(results), TEAMS_FILE))


def main(argv):
    global args

    parser = argparse.ArgumentParser(
        description="Populate Bot names with professional riders"
    )
    parser.add_argument(
        "-n", "--nation", help="Riders from specified nation only", default=False
    )
    parser.add_argument(
        "-f", "--female", help="Female riders only", default=False, action="store_true"
    )
    parser.add_argument(
        "-m", "--male", help="Male riders only", default=False, action="store_true"
    )
    parser.add_argument(
        "-a",
        "--alltime",
        help="Use all time ranking",
        default=False,
        action="store_true",
    )
    parser.add_argument("-p", "--pages", help="Number of pages to process", default=1)
    parser.add_argument(
        "-j", "--jersey", help="Get team jerseys", default=False, action="store_true"
    )
    parser.add_argument(
        "-e",
        "--equipment",
        help="Get team bike and wheels",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-t",
        "--teamabbrv",
        help="Add team abbreviation to last name",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--teampage",
        help="Fetch procyclingstats team pages to resolve canonical team names for low-confidence matches",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--threshold",
        help="Minimum fuzzy match score (0-100) to accept a team name match",
        default=MATCH_THRESHOLD,
        type=int,
    )
    parser.add_argument(
        "--generate-teams",
        help="Auto-build get_pro_names.json from top-ranked procyclingstats teams",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--team-limit",
        help="Number of ranked teams to include when generating",
        default=100,
        type=int,
    )
    args = parser.parse_args()

    if args.generate_teams:
        generate_teams(args.team_limit)
        return
    url_additions = ""
    url_list = []
    if args.alltime:
        url_additions += "&s=all-time"
    if args.nation:
        url_additions += "&nation=" + args.nation
    if args.female:
        url_list = [{"url": base_url + url_additions + "&p=we", "is_male": False}]
    elif args.male:
        url_list = [{"url": base_url + url_additions + "&p=me", "is_male": True}]
    else:
        url_list = [
            {"url": base_url + url_additions + "&p=me", "is_male": True},
            {"url": base_url + url_additions + "&p=we", "is_male": False},
        ]
    if args.pages:
        new_url_list = url_list.copy()
        for x in range(1, int(args.pages)):
            offset = str(x * 100)
            for url in url_list:
                new_url_list += [
                    {"url": url["url"] + "&offset=" + offset, "is_male": url["is_male"]}
                ]
        url_list = new_url_list.copy()

    total_data = {}
    total_data["riders"] = []
    for item in url_list:
        total_data["riders"] = total_data["riders"] + get_pros(
            item["url"],
            item["is_male"],
            args.jersey,
            args.equipment,
            args.teamabbrv,
            args.teampage,
            args.threshold,
        )

    with open("bot.txt", "w") as outfile:
        json.dump(total_data, outfile, indent=2)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)
