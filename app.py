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
- Configurable via Railway environment variables
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
CALIBRE_BASE_URL  = os.getenv('CALIBRE_BASE_URL', '').rstrip('/')
LIBRARY_ID        = os.getenv('LIBRARY_ID', 'Calibre_Library')
SYNC_TOKEN        = os.getenv('SYNC_TOKEN', 'your-secret-sync-token-here')
USE_MOCK_DATA     = os.getenv('USE_MOCK_DATA', 'false').lower() == 'true'
PORT              = int(os.getenv('PORT', 5000))

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
        # Additional mocks can be added here
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
                return json.load(f)
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
    Extracts extended metadata: cover_url, thumbnail_url,
    acquisition_links, contributors, rights, identifiers, subjects
    """
    if not CALIBRE_BASE_URL:
        return None

    endpoints = [
        f"{CALIBRE_BASE_URL}/opds/new",
        f"{CALIBRE_BASE_URL}/opds/navcatalog/4e6577",  # 'new' in hex
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
                if not any(l.get('rel','').startswith('http://opds-spec.org/acquisition') for l in links):
                    continue

                book = {}
                # Title & author
                book['title']  = entry.find('atom:title', ns).text or 'Unknown'
                book['author'] = entry.find('atom:author/atom:name', ns).text or 'Unknown'
                # ID
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
                book['description'] = (summary.text or '').strip()[:500]
                # Rating & page count from content
                content = entry.find('atom:content', ns)
                text = content.text or ''
                book['rating'] = 0
                if 'Rating:' in text:
                    try:
                        book['rating'] = int(float(text.split('Rating:')[1].split('<')[0].strip()))
                    except: pass
                import re
                m = re.search(r'(\d+)\s*pages?', text, re.IGNORECASE)
                book['page_count'] = int(m.group(1)) if m else None
                # Tags
                cats = entry.findall('atom:category', ns)
                book['tags'] = ', '.join([c.get('label') for c in cats if c.get('label')])
                # Publisher, language, identifiers
                book['publisher']   = (entry.find('dc:publisher', ns).text if entry.find('dc:publisher', ns) is not None else None)
                book['language']    = (entry.find('dc:language', ns).text if entry.find('dc:language', ns) is not None else None)
                idents = entry.findall('dc:identifier', ns)
                book['identifiers'] = [i.text for i in idents if i.text]
                # Rights
                rights = entry.find('dc:rights', ns)
                book['rights'] = rights.text if rights is not None else None
                # Series
                book['series'] = None
                for c in cats:
                    lbl = c.get('label','')
                    if 'series:' in lbl.lower():
                        book['series'] = lbl.split(':',1)[1].strip()
                # Cover, thumbnail, acquisition links
                book['cover_url']       = None
                book['thumbnail_url']   = None
                book['acquisition_links'] = []
                for l in links:
                    rel = l.get('rel',''); href = l.get('href'); t = l.get('type'); ln = l.get('length')
                    if rel.endswith('/cover'):      book['cover_url']     = href
                    if rel.endswith('/thumbnail'):  book['thumbnail_url'] = href
                    if rel.startswith('http://opds-spec.org/acquisition'):
                        book['acquisition_links'].append({'url': href, 'type': t, 'length': ln})
                # Contributors
                book['contributors'] = []
                for c in entry.findall('atom:contributor', ns):
                    book['contributors'].append({'name': c.text, 'role': c.get('role')})

                books.append(book)
            if books:
                app.logger.info(f"Fetched {len(books)} books from OPDS at {url}")
                return books
        except Exception as e:
            app.logger.warning(f"OPDS fetch error at {url}: {e}")
            continue
    return None

# -------------------------------------------------
# Timestamp Utility
# -------------------------------------------------
def parse_book_timestamp(ts_str):
    """
    Normalize timestamp strings into datetime.
    """
    try:
        if isinstance(ts_str, str) and 'T' in ts_str:
            val = ts_str.split('+')[0].replace('Z','')
            if '.' in val: val = val.split('.')[0]
            return datetime.fromisoformat(val)
        if isinstance(ts_str, str):
            txt = ts_str.split('+')[0]
            if '.' in txt: txt = txt.split('.')[0]
            return datetime.strptime(txt.strip(), "%Y-%m-%d %H:%M:%S")
        return datetime.fromisoformat(str(ts_str))
    except:
        return datetime.now()

# -------------------------------------------------
# Book Formatter
# -------------------------------------------------
def format_book_for_display(book):
    """
    Build a dict for template rendering / JSON output.
    """
    ts   = parse_book_timestamp(book.get('timestamp'))
    now  = datetime.now()
    diff = now - ts
    date_added = ts.strftime("%m/%d")
    year_added = ts.strftime("%Y")
    days_ago   = diff.days
    hours_ago  = int(diff.total_seconds() // 3600)

    return {
        'id': book.get('id'),
        'title': book.get('title','').strip(),
        'author': book.get('author','').strip(),
        'description': book.get('description',''),
        'tags': book.get('tags',''),
        'rating_value': book.get('rating',0),
        'rating': '★' * int(book.get('rating',0)),
        'page_count': book.get('page_count'),
        'format': book.get('format'),
        'publisher': book.get('publisher'),
        'published': book.get('published'),
        'language': book.get('language'),
        'isbn_list': book.get('identifiers'),
        'series': book.get('series'),
        'cover_url': book.get('cover_url'),
        'thumbnail_url': book.get('thumbnail_url'),
        'acquisition_links': book.get('acquisition_links'),
        'contributors': book.get('contributors'),
        'rights': book.get('rights'),
        'subjects': book.get('identifiers'),
        'date_added': date_added,
        'year_added': year_added,
        'days_ago': days_ago,
        'hours_ago': hours_ago,
        'timestamp_iso': ts.isoformat()
    }

# -------------------------------------------------
# Endpoint: Home
# -------------------------------------------------
@app.route('/')
def home():
    """Service info and available endpoints."""
    books_data = load_books_data()
    return jsonify({
        'name': 'TRMNL Calibre Library Plugin',
        'version': '7.0.0',
        'description': 'Comprehensive Calibre library service for TRMNL displays',
        'status': '✅ Service operational',
        'configuration': {
            'calibre_base_url': CALIBRE_BASE_URL or 'Not configured',
            'library_id': LIBRARY_ID,
            'sync_configured': SYNC_TOKEN != 'your-secret-sync-token-here',
            'mock_data_enabled': USE_MOCK_DATA,
            'port': PORT
        },
        'library_stats': {
            'total_books': books_data.get('total_books',0),
            'last_updated': books_data.get('last_updated'),
            'data_source': books_data.get('source','none')
        },
        'endpoints': list(app.url_map.iter_rules())
    })

# -------------------------------------------------
# Endpoint: Health Check
# -------------------------------------------------
@app.route('/health')
def health():
    """Basic health and metrics endpoint."""
    bd = load_books_data()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'metrics': {
            'total_books': bd.get('total_books',0),
            'last_sync': bd.get('last_updated','Never'),
            'data_source': bd.get('source','none'),
            'has_data': bool(bd.get('books'))
        },
        'configuration': {
            'mock_data': USE_MOCK_DATA,
            'opds_configured': bool(CALIBRE_BASE_URL),
            'sync_configured': SYNC_TOKEN != 'your-secret-sync-token-here'
        }
    })

# -------------------------------------------------
# Endpoint: Debug info
# -------------------------------------------------
@app.route('/debug')
def debug():
    """Dump detailed config and sample book fields."""
    bd = load_books_data()
    info = {
        'railway_vars': {
            'CALIBRE_BASE_URL': CALIBRE_BASE_URL or 'Not set',
            'LIBRARY_ID': LIBRARY_ID,
            'SYNC_TOKEN': 'Set' if SYNC_TOKEN != 'your-secret-sync-token-here' else 'Not set',
            'USE_MOCK_DATA': USE_MOCK_DATA,
            'PORT': PORT
        },
        'data_status': {
            'source': bd.get('source','none'),
            'total_books': bd.get('total_books',0),
            'last_updated': bd.get('last_updated','Never'),
            'has_data': bool(bd.get('books'))
        },
        'sample_book': None
    }
    if bd.get('books'):
        s = bd['books'][0]
        info['sample_book'] = {'title': s.get('title'), 'fields': list(s.keys())}
    return jsonify(info)

# -------------------------------------------------
# Endpoint: Sync (POST only)
# -------------------------------------------------
@app.route('/sync', methods=['POST'])
def sync_books():
    """Accept book data via POST, authenticate via SYNC_TOKEN."""
    auth = request.headers.get('Authorization','')
    expected = f"Bearer {SYNC_TOKEN}"
    if auth != expected:
        return jsonify({'error':'Authentication required'}), 401
    data = request.get_json()
    if not data or 'books' not in data:
        return jsonify({'error':'Invalid format'}), 400
    ts = datetime.now().isoformat()
    bd = {'books': data['books'], 'last_updated': ts,
          'total_books': len(data['books']), 'source': data.get('source','local_sync')}
    if save_books_data(bd):
        return jsonify({'success':True,'books_synced':len(data['books']),'timestamp':ts})
    return jsonify({'error':'Save failed'}), 500

# -------------------------------------------------
# Endpoint: TRMNL Recent
# -------------------------------------------------
@app.route('/trmnl-recent', methods=['GET','POST'])
def trmnl_recent():
    """List recent books with extended metadata and timestamps."""
    req = request.get_json() if request.method=='POST' else {}
    limit = int(req.get('limit', request.args.get('limit', DEFAULT_BOOK_LIMIT)))
    limit = max(1, min(limit, MAX_BOOK_LIMIT))
    bd = load_books_data()
    books = bd.get('books', [])
    if not books and CALIBRE_BASE_URL and not USE_MOCK_DATA:
        fetched = fetch_opds_books()
        if fetched:
            books = fetched
            bd['source'] = 'opds_direct'
    now = datetime.now()
    ct = now.strftime("%m/%d %H:%M")
    ctl = now.strftime("%B %d, %Y, %I:%M %p")
    cti = now.isoformat()
    recents = [format_book_for_display(b) for b in books[:limit]]
    suggestion = format_book_for_display(random.choice(books[limit:])) if len(books)>limit else None
    return jsonify({'books':recents,'book_suggestion':suggestion,
                    'total_books':bd.get('total_books',len(books)),
                    'current_time':ct,'current_time_long':ctl,'current_time_iso':cti,'source':bd.get('source')})

# -------------------------------------------------
# Legacy & Additional Endpoints
# -------------------------------------------------
@app.route('/trmnl-data', methods=['GET','POST'])
@app.route('/calibre-status', methods=['GET','POST'])
def trmnl_data():
    """Return latest book with core & extended metadata for TRMNL display."""
    bd = load_books_data()
    books = bd.get('books',[])
    if not books and CALIBRE_BASE_URL and not USE_MOCK_DATA:
        opds = fetch_opds_books()
        if opds:
            books = opds
            bd['source'] = 'opds_direct'
    if not books:
        return jsonify({'error':'No books'}),404
    latest = format_book_for_display(books[0])
    total = len(books)
    rated = sum(1 for b in books if b.get('rating',0)>0)
    pct = int(rated/total*100) if total>0 else 0
    pages = sum(1 for b in books if b.get('page_count'))
    lt = latest['date_added'] + ' ' + latest['timestamp_iso'].split('T')[1][:5]
    resp = {'title':latest['title'],'author':latest['author'],
            'rating':latest['rating'],'tags':latest['tags'],
            'total_books':total,'rated_books':rated,'rating_percentage':pct,'books_with_pages':pages,
            'page_count':latest['page_count'],'pages_formatted':f"{latest['page_count']} pages",
            'description':latest['description'],'series':latest['series'],'format':latest['format'],'language':latest['language'],
            'server_status':'Connected','current_time':datetime.now().strftime("%m/%d %H:%M"),
            'last_update':lt,'data_source':bd.get('source'),'days_ago':latest['days_ago'],'year_added':latest['year_added']}
    return jsonify(resp)

@app.route('/books/recent', methods=['GET','POST'])
def recent_books():
    """Raw JSON list of recent books with full metadata."""
    req = request.get_json() if request.method=='POST' else {}
    limit = int(req.get('limit', request.args.get('limit', DEFAULT_BOOK_LIMIT)))
    limit = max(1, min(limit, MAX_BOOK_LIMIT))
    bd = load_books_data()
    books = bd.get('books',[])[:limit]
    return jsonify({'books':[format_book_for_display(b) for b in books],
                    'count':len(books),'total_available':bd.get('total_books'),'last_updated':bd.get('last_updated'),'source':bd.get('source')})

@app.route('/books/random', methods=['GET','POST'])
def random_book():
    """Random book suggestion with full metadata."""
    bd = load_books_data(); books=bd.get('books',[])
    if not books: return jsonify({'book':None,'error':'No books'})
    return jsonify({'book':format_book_for_display(random.choice(books)),'total_books':len(books),'source':bd.get('source')})

@app.route('/trmnl-list-data', methods=['GET','POST'])
def trmnl_list_data():
    """List books grouped by this week, last week, earlier."""
    bd = load_books_data(); books=bd.get('books',[])
    if not books and CALIBRE_BASE_URL and not USE_MOCK_DATA:
        opds=fetch_opds_books();
        if opds: books=opds; bd['source']='opds_direct'
    now=datetime.now()
    tw=[]; lw=[]; eb=[]
    for i,b in enumerate(books):
        ts=parse_book_timestamp(b.get('timestamp')); d=(now-ts).days
        f={'index':i+1,'title':b.get('title')[:50],'author':b.get('author'),'tags':b.get('tags','')[:40],'rating':'★'*int(b.get('rating',0)),'days_ago':d,'page_count':b.get('page_count'),'description':b.get('description','')[:200]}
        if d<=7: tw.append(f)
        elif d<=14: lw.append(f)
        else: eb.append(f)
    return jsonify({'this_week_books':tw[:10],'last_week_books':lw[:10],'earlier_books':eb[:10],'total_books':len(books),'source':bd.get('source'),'current_time':now.strftime("%m/%d %H:%M")})

@app.route('/trmnl-simple-list', methods=['GET','POST'])
def trmnl_simple_list():
    """Linear list of recent books with date_display and roulette."""
    bd=load_books_data(); books=bd.get('books',[])
    if not books and CALIBRE_BASE_URL and not USE_MOCK_DATA:
        opds=fetch_opds_books();
        if opds: books=opds; bd['source']='opds_direct'
    now=datetime.now();
    limit=int(request.get_json().get('limit',request.args.get('limit',DEFAULT_BOOK_LIMIT))) if request.method=='POST' else int(request.args.get('limit',DEFAULT_BOOK_LIMIT))
    limit=max(1,min(limit,MAX_BOOK_LIMIT));
    recent=[]
    for i,b in enumerate(books[:limit]):
        ts=parse_book_timestamp(b.get('timestamp')); d=(now-ts).days
        if d==0: dd='Today'
        elif d==1: dd='Yesterday'
        elif d<7: dd=f"{d} days ago"
        else: dd=ts.strftime('%b %d')
        recent.append({'index':i+1,'title':b.get('title')[:60],'author':b.get('author'),'tags':b.get('tags','')[:50],'rating':'★'*int(b.get('rating',0)),'date_display':dd,'days_ago':d,'page_count':b.get('page_count')})
    roulette=None
    if len(books)>5: rb=random.choice(books[5:]); roulette={'title':rb.get('title'),'author':rb.get('author'),'rating':'★'*int(rb.get('rating',0)),'page_count':rb.get('page_count'),'description':rb.get('description','')[:150]}
    return jsonify({'recent_books':recent,'roulette':roulette,'total_books':bd.get('total_books'),'rated_books':sum(1 for b in books if b.get('rating',0)>0),'current_time':now.strftime("%m/%d %H:%M")})

@app.route('/clear-cache', methods=['POST','GET'])
def clear_cache():
    """Remove local cache file (mock mode disabled)."""
    if USE_MOCK_DATA:
        return jsonify({'success':False,'message':'Cannot clear mock data cache'})
    try:
        if os.path.exists(BOOKS_FILE): os.remove(BOOKS_FILE)
        return jsonify({'success':True,'message':'Cache cleared'})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)})

# -------------------------------------------------
# Main Runner
# -------------------------------------------------
if __name__ == '__main__':
    print(f"🚀 Starting TRMNL Calibre Library Plugin on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)
