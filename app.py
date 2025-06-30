#!/usr/bin/env python3
"""
TRMNL Calibre Library Plugin - Cloud Service

A cloud-hosted service that syncs with your local Calibre library
and provides comprehensive book data for TRMNL e-ink displays.

Features:
- Syncs extensive book metadata from local Calibre database
- Direct OPDS feed integration when configured via CALIBRE_BASE_URL
- Exposes cover images, acquisition links, identifiers, subjects, contributors, rights, and more
- Provides multiple date/time formats and per-book timestamps
- Configurable via Railway environment variables (CALIBRE_BASE_URL, LIBRARY_ID, SYNC_TOKEN, USE_MOCK_DATA, PORT)
- Optimized for TRMNL's e-ink display framework
"""

import os
import json
import random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)

# -------------------------------------------------
# Configuration (Railway environment variables)
# -------------------------------------------------
CALIBRE_BASE_URL = os.getenv('CALIBRE_BASE_URL', '').rstrip('/')
LIBRARY_ID       = os.getenv('LIBRARY_ID', 'Calibre_Library')
SYNC_TOKEN       = os.getenv('SYNC_TOKEN', 'your-secret-sync-token-here')
USE_MOCK_DATA    = os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
PORT             = int(os.getenv('PORT', 5000))

# Storage settings
BOOKS_FILE        = 'books_data.json'
DEFAULT_BOOK_LIMIT = int(os.getenv('DEFAULT_BOOK_LIMIT', 10))
MAX_BOOK_LIMIT     = int(os.getenv('MAX_BOOK_LIMIT', 50))

# -------------------------------------------------
# Mock Data Generator (for testing)
# -------------------------------------------------
def get_mock_books():
    """
    Generate mock book data when USE_MOCK_DATA is enabled.
    """
    now = datetime.now()
    return [
        {
            'id': 1,
            'title': 'Project Hail Mary',
            'author': 'Andy Weir',
            'timestamp': (now - timedelta(days=2)).isoformat(),
            'rating': 5,
            'description': 'An astronaut wakes up alone on a spaceship...',
            'page_count': 476,
            'tags': 'Science Fiction, Space, Adventure',
            'series': None,
            'publisher': 'Ballantine Books',
            'published': '2021-05-04',
            'language': 'English',
            'isbn': '9780593135204',
            'format': 'EPUB'
        },
        # ... add additional mocks if needed
    ]

# -------------------------------------------------
# Data Persistence
# -------------------------------------------------
def load_books_data():
    """
    Load book data from local storage or return mock data.
    """
    if USE_MOCK_DATA:
        books = get_mock_books()
        return { 'books': books,
                 'last_updated': datetime.now().isoformat(),
                 'total_books': len(books),
                 'source': 'mock_data' }
    try:
        if os.path.exists(BOOKS_FILE):
            with open(BOOKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
    except Exception as e:
        app.logger.warning(f"Error loading books_data.json: {e}")
    return { 'books': [], 'last_updated': None, 'total_books': 0, 'source': 'none' }


def save_books_data(data):
    """
    Save book data to local storage (books_data.json).
    """
    try:
        with open(BOOKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"Error saving books_data.json: {e}")
        return False

# -------------------------------------------------
# OPDS Fetch & Parsing (extended metadata)
# -------------------------------------------------
def fetch_opds_books():
    """
    Fetch and parse book entries from Calibre-web OPDS feed.
    Extracts extended metadata:
      - cover_url, thumbnail_url
      - acquisition_links (url, type, length)
      - contributors (name, role)
      - rights, identifiers, subjects
    """
    if not CALIBRE_BASE_URL:
        return None

    endpoints = [
        f"{CALIBRE_BASE_URL}/opds/new",
        f"{CALIBRE_BASE_URL}/opds/navcatalog/4e6577",  # "new" in hex
        f"{CALIBRE_BASE_URL}/opds/navcatalog/new",
        f"{CALIBRE_BASE_URL}/opds"
    ]
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'dc':   'http://purl.org/dc/terms/',
        'opds': 'http://opds-spec.org/2010/catalog'
    }

    for url in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
            entries = root.findall('atom:entry', ns)
            books = []

            for entry in entries:
                links = entry.findall('atom:link', ns)
                # Determine if this is an acquisition entry
                if not any(l.get('rel','').startswith('http://opds-spec.org/acquisition') for l in links):
                    continue

                book = {}
                # Basic metadata
                book['title']  = entry.find('atom:title', ns).text if entry.find('atom:title', ns) is not None else 'Unknown'
                book['author'] = entry.find('atom:author/atom:name', ns).text if entry.find('atom:author/atom:name', ns) is not None else 'Unknown'

                # Unique ID (extract numeric or hash)
                raw_id = entry.find('atom:id', ns)
                if raw_id is not None and raw_id.text:
                    txt = raw_id.text
                    book['id'] = int(txt.split(':')[-1]) if ':' in txt else abs(hash(txt)) % 100000

                # Timestamps
                updated = entry.find('atom:updated', ns)
                book['timestamp'] = updated.text if updated is not None else datetime.now().isoformat()
                pub = entry.find('atom:published', ns) or entry.find('dc:date', ns)
                book['published'] = pub.text if pub is not None else None

                # Description & summary
                summary = entry.find('atom:summary', ns)
                book['description'] = summary.text.strip()[:500] if summary is not None and summary.text else ''

                # Rating & page count from <content>
                content = entry.find('atom:content', ns)
                text = content.text or ''
                # Rating
                if 'Rating:' in text:
                    try:
                        book['rating'] = int(float(text.split('Rating:')[1].split('<')[0].strip()))
                    except: book['rating'] = 0
                else:
                    book['rating'] = 0
                # Page count
                import re
                m = re.search(r'(\d+)\s*pages?', text, re.IGNORECASE)
                book['page_count'] = int(m.group(1)) if m else None

                # Tags (categories)
                cats = entry.findall('atom:category', ns)
                labels = [c.get('label') for c in cats if c.get('label')]
                book['tags'] = ', '.join(labels)

                # Publisher, language, ISBN
                pubr = entry.find('dc:publisher', ns)
                book['publisher'] = pubr.text if pubr is not None else None
                lang = entry.find('dc:language', ns)
                book['language'] = lang.text if lang is not None else None
                ident = entry.findall('dc:identifier', ns)
                book['identifiers'] = [i.text for i in ident if i.text]

                # Rights
                r = entry.find('dc:rights', ns)
                book['rights'] = r.text if r is not None else None

                # Series info (if present)
                book['series'] = None
                for c in cats:
                    l = c.get('label','')
                    if 'series:' in l.lower():
                        book['series'] = l.split(':',1)[1].strip()

                # Cover and thumbnail links
                book['cover_url']     = None
                book['thumbnail_url'] = None
                book['acquisition_links'] = []
                for l in links:
                    rel = l.get('rel','')
                    href = l.get('href')
                    t   = l.get('type')
                    ln  = l.get('length')
                    if rel == 'http://opds-spec.org/cover':
                        book['cover_url'] = href
                    if rel == 'http://opds-spec.org/thumbnail':
                        book['thumbnail_url'] = href
                    if rel.startswith('http://opds-spec.org/acquisition'):
                        book['acquisition_links'].append({ 'url': href, 'type': t, 'length': ln })

                # Contributors (editors, translators)
                book['contributors'] = []
                for c in entry.findall('atom:contributor', ns):
                    book['contributors'].append({ 'name': c.text, 'role': c.get('role') })

                # Append to list
                books.append(book)

            if books:
                app.logger.info(f"Fetched {len(books)} OPDS books from {url}")
                return books
        except Exception as err:
            app.logger.warning(f"OPDS fetch error at {url}: {err}")
            continue
    return None

# -------------------------------------------------
# Timestamp Parsing Utility
# -------------------------------------------------
def parse_book_timestamp(ts_str):
    """
    Normalize various timestamp formats into a datetime object.
    """
    try:
        if isinstance(ts_str, str) and 'T' in ts_str:
            val = ts_str.split('+')[0].replace('Z','')
            if '.' in val:
                val = val.split('.')[0]
            return datetime.fromisoformat(val)
        if isinstance(ts_str, str):
            txt = ts_str.split('+')[0]
            if '.' in txt:
                txt = txt.split('.')[0]
            return datetime.strptime(txt.strip(), "%Y-%m-%d %H:%M:%S")
        return datetime.fromisoformat(str(ts_str))
    except Exception:
        return datetime.now()

# -------------------------------------------------
# Book Formatting for TRMNL Display
# -------------------------------------------------
def format_book_for_display(book):
    """
    Convert raw book data into a rich dict for TRMNL templates:
      - Core fields: title, author, rating, tags, page_count
      - Extended metadata: publisher, language, identifiers, subjects, etc.
      - Timestamps: date_added, year_added, days_ago, hours_ago, timestamp_iso
    """
    ts   = parse_book_timestamp(book.get('timestamp'))
    now  = datetime.now()
    diff = now - ts

    date_added = ts.strftime("%m/%d")
    year_added = ts.strftime("%Y")
    days_ago   = diff.days
    hours_ago  = int(diff.total_seconds() // 3600)

    return {
        # Core
        'id':              book.get('id'),
        'title':           book.get('title','Unknown Title'),
        'author':          book.get('author','Unknown Author'),
        'description':     book.get('description',''),
        'tags':            book.get('tags',''),
        'rating_value':    book.get('rating',0),
        'rating':          '★' * int(book.get('rating',0)),
        'page_count':      book.get('page_count'),
        'format':          book.get('format'),

        # OPDS extras
        'publisher':       book.get('publisher'),
        'published':       book.get('published'),
        'language':        book.get('language'),
        'isbn_list':       book.get('identifiers'),
        'series':          book.get('series'),
        'cover_url':       book.get('cover_url'),
        'thumbnail_url':   book.get('thumbnail_url'),
        'acquisition_links': book.get('acquisition_links'),
        'contributors':    book.get('contributors'),
        'rights':          book.get('rights'),
        'subjects':        book.get('identifiers'),

        # Timing
        'date_added':      date_added,
        'year_added':      year_added,
        'days_ago':        days_ago,
        'hours_ago':       hours_ago,
        'timestamp_iso':   ts.isoformat()
    }

# -------------------------------------------------
# Endpoint: /trmnl-recent (enhanced)
# -------------------------------------------------
@app.route('/trmnl-recent', methods=['GET','POST'])
def trmnl_recent():
    """
    Return a flat list of recent books with full metadata and multiple timestamp formats:
      - current_time:      "MM/DD HH:MM"
      - current_time_long: "Month DD, YYYY, hh:MM AM/PM"
      - current_time_iso:  ISO8601
    """
    data = request.get_json() if request.method == 'POST' else {}
    limit = int(data.get('limit', request.args.get('limit', DEFAULT_BOOK_LIMIT)))
    limit = max(1, min(limit, MAX_BOOK_LIMIT))

    books_data = load_books_data()
    books = books_data.get('books', [])
    if not books and CALIBRE_BASE_URL and not USE_MOCK_DATA:
        fetched = fetch_opds_books()
        if fetched:
            books = fetched
            books_data['source'] = 'opds_direct'

    now = datetime.now()
    current_time      = now.strftime("%m/%d %H:%M")
    current_time_long = now.strftime("%B %d, %Y, %I:%M %p")
    current_time_iso  = now.isoformat()

    # Format each book
    recent_books = [format_book_for_display(b) for b in books[:limit]]

    # Suggest random older book
    suggestion = None
    if len(books) > limit:
        suggestion = format_book_for_display(random.choice(books[limit:]))

    return jsonify({
        'books':              recent_books,
        'book_suggestion':    suggestion,
        'total_books':        books_data.get('total_books', len(books)),
        'current_time':       current_time,
        'current_time_long':  current_time_long,
        'current_time_iso':   current_time_iso,
        'source':             books_data.get('source')
    })

# -------------------------------------------------
# Other endpoints remain unchanged: /, /health, /debug, /sync, /trmnl-data, etc.
# -------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
