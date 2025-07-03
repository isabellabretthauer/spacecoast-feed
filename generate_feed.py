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
        h6s = block.select("h6")
        if len(h6s) < 2:
            continue
        date_s, time_s = h6s[0].get_text(strip=True), h6s[1].get_text(strip=True)
        try:
            dt = datetime.strptime(f"{date_s} {time_s}", "%B %d, %Y %I:%M %p")
        except ValueError:
            continue
        iso = dt.isoformat()

        mission = block.select_one("p strong").get_text(strip=True)
        status_txt = block.select_one("span.card-launches__status").get_text(strip=True)
        status = status_txt.split(":",1)[1].strip() if ":" in status_txt else status_txt

        desc_p = block.select("p")
        description = desc_p[1].get_text(strip=True) if len(desc_p) > 1 else ""

        # launch image from nearby <figure>
        fig = block.find_previous_sibling("figure", class_="card__image") or block.select_one("figure.card__image")
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
        title_tag = block.find("h4")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        # date & time
        ul = block.find("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        raw_date = lis[0].get_text(strip=True)
        date_only = raw_date.split("–")[0].split("-")[0].strip()
        time_txt = (
            lis[1].get_text(strip=True).replace("Time start:", "").strip()
            if len(lis) > 1 else ""
        )
        try:
            dt = datetime.strptime(f"{date_only} {time_txt}", "%B %d, %Y %I:%M %p")
            iso = dt.isoformat()
        except ValueError:
            try:
                iso = datetime.strptime(date_only, "%B %d, %Y").date().isoformat()
            except ValueError:
                iso = None

        # summary (first <p> after UL)
        p = ul.find_next_sibling("p")
        summary = p.get_text(strip=True) if p else ""

        # URL
        link_tag = block.find("a", string=lambda s: s and "View Event" in s)
        url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        if url and url.startswith("/"):
            url = BASE + url

        # event image (any <img> inside block)
        img_tag = block.find("img")
        img_url = img_tag.get("src") if img_tag and img_tag.has_attr("src") else None

        events.append({
            "datetime":    iso,
            "title":       title,
            "description": summary,
            "url":         url,
            "image":       img_url
        })
    return events

def create_rss(launches, events, filename="spacecoast_feed.xml"):
    rss = ET.Element("rss", version="2.0")
    ch  = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text       = "Visit Space Coast Launches & Events"
    ET.SubElement(ch, "link").text        = BASE
    ET.SubElement(ch, "description").text = "Automated feed of Space Coast launches and events"
    ET.SubElement(ch, "lastBuildDate").text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    def add_item(itm, kind):
        it = ET.SubElement(ch, "item")
        label = itm.get("mission") or itm.get("title")
        ET.SubElement(it, "title").text = f"{kind}: {label}"
        ET.SubElement(it, "link").text  = itm.get("url","")
        # description: full for events, status+full for launches
        if kind == "Launch":
            desc = f"Status: {itm.get('status','')}\n{itm.get('description','')}"
        else:
            desc = itm.get("description","")
        ET.SubElement(it, "description").text = desc
        dt = itm.get("datetime")
        if dt:
            ET.SubElement(it, "pubDate").text = datetime.fromisoformat(dt).strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(it, "guid").text = f"{kind.lower()}-{label}-{dt}"
        if itm.get("image"):
            ET.SubElement(it, "enclosure", url=itm["image"], type="image/jpeg")

    for l in launches: add_item(l, "Launch")
    for e in events:   add_item(e, "Event")

    xml = parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml)
    print("Generated", filename)

if __name__=="__main__":
    create_rss(scrape_launches(), scrape_events())
