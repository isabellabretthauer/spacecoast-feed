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
        # skip anything without two h6s (i.e. not a launch card)
        h6s = card.select("h6")
        if len(h6s) < 2:
            continue

        date_str, time_str = h6s[0].get_text(strip=True), h6s[1].get_text(strip=True)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except ValueError:
            continue
        iso = dt.isoformat()

<<<<<<< HEAD
        mission = block.select_one("p strong").get_text(strip=True)
        status_line = block.select_one("span.card-launches__status").get_text(strip=True)
        status = status_line.split(":",1)[1].strip() if ":" in status_line else status_line
        desc_ps = block.select("p")
        description = desc_ps[1].get_text(strip=True) if len(desc_ps)>1 else ""

        # image
        fig = block.find_previous_sibling("figure.card__image") or block.select_one("figure.card__image")
        img_tag = fig.find("img") if fig else None
        img_url = img_tag.get("data-lazy-src") or img_tag.get("src") if img_tag else None
=======
        mission = card.select_one("p strong").get_text(strip=True)
        status_raw = card.select_one("span.card-launches__status").get_text(strip=True)
        status = status_raw.split(":",1)[1].strip() if ":" in status_raw else status_raw

        ps = card.select("p")
        description = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        # launch image lives in the sibling figure.card__image
        fig = card.parent.select_one("figure.card__image")
        img = fig.find("img") if fig else None
        img_url = img.get("data-lazy-src") or img.get("src") if img else None
>>>>>>> 684007d (Fix event images + summary + date/time; remove event status)

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
<<<<<<< HEAD
    for card in soup.select("div.card__content"):
        # title
        h4 = card.find("h4")
        if not h4: 
            continue
        title = h4.get_text(strip=True)

        # date/time
=======
    # each event is also in a div.card__content, but lacks two h6s
    for card in soup.select("div.card__content"):
        # skip if this is a launch (it has two h6s)
        if len(card.select("h6")) >= 2:
            continue

        # title from the h4
        h4 = card.find("h4")
        if not h4:
            continue
        title = h4.get_text(strip=True)

        # date/time from the UL
>>>>>>> 684007d (Fix event images + summary + date/time; remove event status)
        ul = h4.find_next_sibling("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        raw_date = lis[0].get_text(strip=True)
        # split off a possible range
        first_date = raw_date.split("–")[0].split("-")[0].strip()
        time_str = lis[1].get_text(strip=True).replace("Time start:", "").strip() if len(lis)>1 else ""
        try:
            dt = datetime.strptime(f"{first_date} {time_str}", "%B %d, %Y %I:%M %p")
            iso = dt.isoformat()
        except ValueError:
            iso = datetime.strptime(first_date, "%B %d, %Y").date().isoformat()

<<<<<<< HEAD
        # link
        a = card.find("a", string=lambda s: s and "View Event" in s)
        url = a["href"] if a and a.has_attr("href") else None

        # summary/description
        ps = card.select("p")
        description = ps[1].get_text(strip=True) if len(ps)>1 else (ps[0].get_text(strip=True) if ps else "")

        # image
        fig = card.find_previous_sibling("figure.card__image") or card.select_one("figure.card__image")
        if fig:
            img_tag = fig.find("img")
        else:
            img_tag = card.find("img")
        img_url = img_tag.get("data-lazy-src") or img_tag.get("src") if img_tag else None
=======
        # summary = first <p> inside card__content
        ps = card.find_all("p")
        description = ps[0].get_text(strip=True) if ps else ""

        # link = the “View Event” anchor
        a = card.find("a", string=lambda s: s and "View Event" in s)
        url = a["href"] if a and a.has_attr("href") else None

        # event image = the first img.wp-post-image inside the card
        img = card.find("img", class_="wp-post-image")
        img_url = img.get("data-lazy-src") or img.get("src") if img else None
>>>>>>> 684007d (Fix event images + summary + date/time; remove event status)

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
    ET.SubElement(channel, 'title').text         = 'Visit Space Coast Launches & Events'
    ET.SubElement(channel, 'link').text          = 'https://www.visitspacecoast.com/'
    ET.SubElement(channel, 'description').text   = 'Automated feed of Space Coast launches and events'
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
