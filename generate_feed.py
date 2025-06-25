#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

def scrape_launches():
    resp = requests.get("https://www.visitspacecoast.com/launches/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen = set()
    launches = []
    for block in soup.select("div.card__content"):
        # grab date/time
        h6s = block.select("h6")
        if len(h6s) < 2: 
            continue
        date_str, time_str = h6s[0].get_text(strip=True), h6s[1].get_text(strip=True)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except ValueError:
            continue

        # mission, status, description
        mission = block.select_one("p strong").get_text(strip=True)
        status = block.select_one("span.card-launches__status").get_text(strip=True).split(":",1)[1].strip()
        ps = block.select("p")
        description = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        # grab the first image in this block, if any
        img_tag = block.select_one("img")
        img_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None

        key = (mission, dt.isoformat())
        if key in seen:
            continue
        seen.add(key)

        launches.append({
            "datetime": dt.isoformat(),
            "mission": mission,
            "status": status,
            "description": description,
            "image": img_url
        })

    return launches

def scrape_events():
    resp = requests.get("https://www.visitspacecoast.com/events/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    for title_tag in soup.find_all("h4"):
        title = title_tag.get_text(strip=True)
        ul = title_tag.find_next_sibling("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        raw_date = lis[0].get_text(strip=True)
        first_date = raw_date.split("–")[0].split("-")[0].strip()
        time_str = lis[1].get_text(strip=True).replace("Time start:", "").strip() if len(lis) > 1 else ""

        try:
            dt = datetime.strptime(f"{first_date} {time_str}", "%B %d, %Y %I:%M %p")
            dt_iso = dt.isoformat()
        except ValueError:
            dt_iso = datetime.strptime(first_date, "%B %d, %Y").date().isoformat()

        # grab image if there is one in the card
        block = title_tag.find_parent("div.card__content")
        img_tag = block.select_one("img") if block else None
        img_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None

        link_tag = title_tag.find_next("a", string=lambda s: s and "View Event" in s)
        url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None

        events.append({
            "datetime": dt_iso,
            "title": title,
            "url": url,
            "image": img_url
        })

    return events

def create_rss(launches, events, filename="spacecoast_feed.xml"):
    rss     = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text         = 'Visit Space Coast Launches & Events'
    ET.SubElement(channel, 'link').text          = 'https://www.visitspacecoast.com/'
    ET.SubElement(channel, 'description').text   = 'Automated feed of Space Coast launches and events'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def add_item(item, prefix):
        it = ET.SubElement(channel, 'item')
        ET.SubElement(it, 'title').text       = f"{prefix}: {item.get('mission', item.get('title'))}"
        ET.SubElement(it, 'link').text        = item.get('url') or 'https://www.visitspacecoast.com/launches/'
        ET.SubElement(it, 'description').text = f"{item.get('status','')}: {item.get('description','')}".strip()
        ET.SubElement(it, 'pubDate').text     = datetime.fromisoformat(item['datetime']).strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(it, 'guid').text        = f"{prefix.lower()}-{item.get('mission',item.get('title'))}-{item['datetime']}"
        # enclosure if we have an image
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
