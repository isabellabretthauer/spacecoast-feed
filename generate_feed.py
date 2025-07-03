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
    for card in soup.select("div.card__content"):
        # only launch cards have two <h6> tags
        h6s = card.select("h6")
        if len(h6s) < 2:
            continue

        # parse datetime
        date_str, time_str = h6s[0].get_text(strip=True), h6s[1].get_text(strip=True)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except ValueError:
            continue
        iso = dt.isoformat()

        mission = card.select_one("p strong").get_text(strip=True)
        status_line = card.select_one("span.card-launches__status").get_text(strip=True)
        status = status_line.split(":",1)[1].strip() if ":" in status_line else status_line

        ps = card.select("p")
        description = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        # find launch image in neighboring <figure class="card__image">
        fig = card.parent.select_one("figure.card__image")
        img_tag = fig.find("img") if fig else None
        img_url = img_tag.get("data-lazy-src") or img_tag.get("src") if img_tag else None

        key = (mission, iso)
        if key in seen:
            continue
        seen.add(key)

        launches.append({
            "datetime":    iso,
            "mission":     mission,
            "status":      status,
            "description": description,
            "url":         "https://www.visitspacecoast.com/launches/",
            "image":       img_url,
        })
    return launches

def scrape_events():
    resp = requests.get("https://www.visitspacecoast.com/events/")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    for card in soup.select("div.card__content"):
        # skip launch cards
        if len(card.select("h6")) >= 2:
            continue

        h4 = card.find("h4")
        if not h4:
            continue
        title = h4.get_text(strip=True)

        # parse date/time from the <ul>
        ul = h4.find_next_sibling("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        raw_date = lis[0].get_text(strip=True)
        first_date = raw_date.split("–")[0].split("-")[0].strip()
        time_str = lis[1].get_text(strip=True).replace("Time start:", "").strip() if len(lis)>1 else ""
        try:
            dt = datetime.strptime(f"{first_date} {time_str}", "%B %d, %Y %I:%M %p")
            iso = dt.isoformat()
        except ValueError:
            iso = datetime.strptime(first_date, "%B %d, %Y").date().isoformat()

        # summary from first <p>
        ps = card.find_all("p")
        description = ps[0].get_text(strip=True) if ps else ""

        # link to “View Event”
        a = card.find("a", string=lambda s: s and "View Event" in s)
        url = a["href"] if a and a.has_attr("href") else None

        # event image inside .wp-post-image
        img = card.find("img", class_="wp-post-image")
        img_url = img.get("data-lazy-src") or img.get("src") if img else None

        events.append({
            "datetime":    iso,
            "title":       title,
            "description": description,
            "url":         url,
            "image":       img_url,
        })
    return events

def create_rss(launches, events, filename="spacecoast_feed.xml"):
    rss     = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text       = 'Visit Space Coast Launches & Events'
    ET.SubElement(channel, 'link').text        = 'https://www.visitspacecoast.com/'
    ET.SubElement(channel, 'description').text = 'Automated feed of Space Coast launches and events'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def add_item(item, kind):
        it = ET.SubElement(channel, 'item')
        ET.SubElement(it, 'title').text       = f"{kind}: {item.get('mission', item.get('title'))}"
        ET.SubElement(it, 'link').text        = item.get('url') or ''
        ET.SubElement(it, 'description').text = item.get('description','')
        ET.SubElement(it, 'pubDate').text     = datetime.fromisoformat(item['datetime']).strftime('%a, %d %b %Y %H:%M:%S GMT')
        guid_text = item.get('mission') or item.get('title')
        ET.SubElement(it, 'guid').text        = f"{kind.lower()}-{guid_text}-{item['datetime']}"
        if item.get('image'):
            ET.SubElement(it, 'enclosure', url=item['image'], type='image/jpeg')

    for l in launches:
        add_item(l, "Launch")
    for e in events:
        add_item(e, "Event")

    pretty = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(pretty)
    print(f"Generated {filename}")

if __name__ == "__main__":
    launches = scrape_launches()
    events   = scrape_events()
    create_rss(launches, events)

