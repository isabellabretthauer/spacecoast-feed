#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

BASE = "https://www.visitspacecoast.com"

def scrape_launches():
    resp = requests.get(f"{BASE}/launches/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    launches = []
    seen = set()
    for block in soup.select("div.card__content"):
        # extract date & time
        h6s = block.select("h6")
        if len(h6s) < 2:
            continue
        date_str = h6s[0].get_text(strip=True)
        time_str = h6s[1].get_text(strip=True)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except ValueError:
            # skip malformed
            continue
        iso = dt.isoformat()

        # title, status, description
        mission = block.select_one("p strong").get_text(strip=True)
        status_line = block.select_one("span.card-launches__status").get_text(strip=True)
        status = status_line.split(":",1)[1].strip() if ":" in status_line else status_line
        ps = block.select("p")
        description = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        # image from preceding <figure class="card__image">
        fig = block.find_previous_sibling("figure", class_="card__image")
        if not fig:
            fig = block.select_one("figure.card__image")
        img = fig.find("img") if fig else None
        img_url = img.get("data-lazy-src") or img.get("src") if img else None

        key = (mission, iso)
        if key in seen:
            continue
        seen.add(key)

        launches.append({
            "datetime":    iso,
            "mission":     mission,
            "status":      status,
            "description": description,
            "url":         f"{BASE}/launches/",
            "image":       img_url
        })
    return launches

def scrape_events():
    resp = requests.get(f"{BASE}/events/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    for block in soup.select("div.card__content"):
        # title
        h4 = block.find("h4")
        if not h4:
            continue
        title = h4.get_text(strip=True)

        # date/time
        ul = block.find("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        raw_date = lis[0].get_text(strip=True)
        date_only = raw_date.split("–")[0].split("-")[0].strip()
        time_part = lis[1].get_text(strip=True).replace("Time start:", "").strip() if len(lis)>1 else ""
        try:
            dt = datetime.strptime(f"{date_only} {time_part}", "%B %d, %Y %I:%M %p")
            iso = dt.isoformat()
        except ValueError:
            try:
                iso = datetime.strptime(date_only, "%B %d, %Y").date().isoformat()
            except ValueError:
                iso = None

        # summary = first <p> after the <ul>
        p = ul.find_next_sibling("p")
        description = p.get_text(strip=True) if p else ""

        # URL = "View Event" link
        a = block.find("a", string=lambda s: s and "View Event" in s)
        url = a["href"] if a and a.has_attr("href") else None
        if url and url.startswith("/"):
            url = BASE + url

        # image = the nearest preceding <figure class="card__image"> or <img>
        fig = block.find_previous_sibling("figure", class_="card__image")
        if fig:
            img = fig.find("img")
            img_url = img.get("data-lazy-src") or img.get("src") if img else None
        else:
            img_tag = block.find_previous("img")
            img_url = img_tag.get("src") if img_tag and img_tag.has_attr("src") else None

        events.append({
            "datetime":    iso,
            "title":       title,
            "description": description,
            "url":         url,
            "image":       img_url
        })

    return events

def create_rss(launches, events, filename="spacecoast_feed.xml"):
    rss     = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text       = "Visit Space Coast Launches & Events"
    ET.SubElement(channel, "link").text        = BASE
    ET.SubElement(channel, "description").text = "Automated feed of Space Coast launches and events"
    ET.SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    def add_item(item, kind):
        it = ET.SubElement(channel, "item")
        label = item.get("mission") or item.get("title")
        ET.SubElement(it, "title").text = f"{kind}: {label}"
        ET.SubElement(it, "link").text  = item.get("url","")

        # description: launches = status + desc, events = full summary
        if kind == "Launch":
            desc = f"{item['status']}"
            if item.get("description"):
                desc += "\n" + item["description"]
        else:
            desc = item.get("description","")
        ET.SubElement(it, "description").text = desc

        # pubDate
        iso = item.get("datetime")
        if iso:
            # if only date, append midnight
            if len(iso)==10:
                dt = datetime.fromisoformat(iso)
            else:
                dt = datetime.fromisoformat(iso)
            ET.SubElement(it, "pubDate").text = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")

        ET.SubElement(it, "guid").text = f"{kind.lower()}-{label}-{iso or ''}"

        # image enclosure
        if item.get("image"):
            ET.SubElement(it, "enclosure", url=item["image"], type="image/jpeg")

    for l in launches:
        add_item(l, "Launch")
    for e in events:
        add_item(e, "Event")

    xml = parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml)
    print("Generated", filename)

if __name__ == "__main__":
    launches = scrape_launches()
    events   = scrape_events()
    create_rss(launches, events)

