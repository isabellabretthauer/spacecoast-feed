#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

BASE = "https://www.visitspacecoast.com"

def scrape_launches():
    resp = requests.get(f"{BASE}/launches/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen = set()
    launches = []
    for block in soup.select("div.card__content"):
        h6s = block.select("h6")
        if len(h6s) < 2:
            continue
        date_str = h6s[0].get_text(strip=True)
        time_str = h6s[1].get_text(strip=True)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except ValueError:
            continue
        iso = dt.isoformat()

        mission = block.select_one("p strong").get_text(strip=True)
        status_line = block.select_one("span.card-launches__status").get_text(strip=True)
        status = status_line.split(":",1)[1].strip() if ":" in status_line else status_line

        desc_ps = block.select("p")
        description = desc_ps[1].get_text(strip=True) if len(desc_ps) > 1 else ""

        # Fetch the figure immediately before or around this block
        fig = block.find_previous_sibling(
            lambda tag: tag.name=="figure" and "card__image" in tag.get("class",[])
        ) or block.select_one("figure.card__image")
        img_tag = fig.find("img") if fig else None
        img_url = (img_tag.get("data-lazy-src") or img_tag.get("src")) if img_tag else None

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
            "image":       img_url,
        })

    return launches

def scrape_events():
    resp = requests.get(f"{BASE}/events/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    for title_tag in soup.find_all("h4"):
        # skip itinerary cards wrapped in .card__content
        if title_tag.find_parent("div", class_="card__content"):
            continue

        title = title_tag.get_text(strip=True)

        ul = title_tag.find_next_sibling("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        raw_date = lis[0].get_text(strip=True)
        # take first day if range
        date_only = raw_date.split("–")[0].split("-")[0].strip()
        time_str = lis[1].get_text(strip=True).replace("Time start:", "").strip() if len(lis)>1 else ""

        try:
            dt = datetime.strptime(f"{date_only} {time_str}", "%B %d, %Y %I:%M %p")
            iso = dt.isoformat()
        except ValueError:
            try:
                iso = datetime.strptime(date_only, "%B %d, %Y").date().isoformat()
            except ValueError:
                iso = None

        # summary paragraph
        p = ul.find_next_sibling("p")
        summary = p.get_text(strip=True) if p else ""

        # view-event link
        link_tag = ul.find_next_sibling("a", string=lambda s: s and "View Event" in s)
        url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        if url and url.startswith("/"):
            url = BASE + url

        # flyer image after that link (or after p)
        img_tag = link_tag.find_next("img") if link_tag else (p.find_next("img") if p else None)
        img_url = img_tag.get("src") if img_tag and img_tag.has_attr("src") else None

        events.append({
            "datetime":    iso,
            "title":       title,
            "description": summary,
            "url":         url,
            "image":       img_url,
        })

    return events

def create_rss(launches, events, filename="spacecoast_feed.xml"):
    rss     = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text         = 'Visit Space Coast Launches & Events'
    ET.SubElement(channel, 'link').text          = BASE
    ET.SubElement(channel, 'description').text   = 'Automated feed of Space Coast launches and events'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def add_item(item, kind):
        it = ET.SubElement(channel, 'item')
        label = item.get('mission') or item.get('title')
        ET.SubElement(it, 'title').text       = f"{kind}: {label}"
        ET.SubElement(it, 'link').text        = item.get('url') or ""
        # build description
        if kind == "Launch":
            desc = f"Status: {item.get('status','')}"
            if item.get('description'):
                desc += "\n" + item['description']
        else:
            # events: just summary
            desc = item.get('description','')
        ET.SubElement(it, 'description').text = desc.strip()
        if item.get('datetime'):
            dt_obj = datetime.fromisoformat(item['datetime'])
            ET.SubElement(it, 'pubDate').text = dt_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(it, 'guid').text        = f"{kind.lower()}-{label}-{item.get('datetime')}"
        if item.get('image'):
            ET.SubElement(it, 'enclosure', url=item['image'], type='image/jpeg')

    for l in launches:
        add_item(l, "Launch")
    for e in events:
        add_item(e, "Event")

    xml_str = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"Generated {filename}")

if __name__ == "__main__":
    launches = scrape_launches()
    events   = scrape_events()
    create_rss(launches, events)


