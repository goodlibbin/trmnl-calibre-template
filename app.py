"""
TRMNL Calibre Library Plugin - Cloud Service

A cloud-hosted service that syncs with your local Calibre library
and provides comprehensive book data for TRMNL e-ink displays.

Features:
- Syncs extensive book metadata from local Calibre database
- Direct OPDS feed integration when configured
- Displays title, author, rating, page count, dates, and more
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

# Configuration from Railway environment variables
CALIBRE_BASE_URL = os.environ.get('CALIBRE_BASE_URL', '')
LIBRARY_ID = os.environ.get('LIBRARY_ID', 'Calibre_Library')
SYNC_TOKEN = os.environ.get('SYNC_TOKEN', 'your-secret-sync-token-here')
USE_MOCK_DATA = os.environ.get('USE_MOCK_DATA', 'false').lower() == 'true'
PORT = int(os.environ.get('PORT', 5000))

# Storage configuration
BOOKS_FILE = 'books_data.json'
DEFAULT_BOOK_LIMIT = int(os.environ.get('DEFAULT_BOOK_LIMIT', 10))
MAX_BOOK_LIMIT = int(os.environ.get('MAX_BOOK_LIMIT', 50))

def get_mock_books():
    """
    Generate mock book data for testing when USE_MOCK_DATA is true.
    """
    mock_books = [
        {
            'id': 1,
            'title': 'Project Hail Mary',
            'author': 'Andy Weir',
            'timestamp': (datetime.now() - timedelta(days=2)).isoformat(),
            'rating': 5,
            'description': 'An astronaut wakes up alone on a spaceship with no memory of how he got there.',
            'page_count': 476,
            'tags': 'Science Fiction, Space, Adventure',
            'series': None,
            'publisher': 'Ballantine Books',
            'published': '2021-05-04',
            'language': 'English',
            'isbn': '9780593135204',
            'format': 'EPUB'
        },
        {
            'id': 2,
            'title': 'The Thursday Murder Club',
            'author': 'Richard Osman',
            'timestamp': (datetime.now() - timedelta(days=5)).isoformat(),
            'rating': 4,
            'description': 'Four retirees at a British retirement home form a club to investigate cold cases.',
            'page_count': 382,
            'tags': 'Mystery, Crime, Humor',
            'series': 'Thursday Murder Club',
            'publisher': 'Viking',
            'published': '2020-09-03',
            'language': 'English',
            'isbn': '9781984880956',
            'format': 'EPUB'
        },
        {
            'id': 3,
            'title': 'Atomic Habits',
            'author': 'James Clear',
            'timestamp': (datetime.now() - timedelta(days=10)).isoformat(),
            'rating': 5,
            'description': 'A proven framework for improving every day through tiny changes.',
            'page_count': 320,
            'tags': 'Self-Help, Psychology, Business',
            'series': None,
            'publisher': 'Avery',
            'published': '2018-10-16',
            'language': 'English',
            'isbn': '9780735211292',
            'format': 'PDF'
        },
        {
            'id': 4,
            'title': 'The Midnight Library',
            'author': 'Matt Haig',
            'timestamp': (datetime.now() - timedelta(days=15)).isoformat(),
            'rating': 4,
            'description': 'A woman finds herself in a magical library between life and death.',
            'page_count': 288,
            'tags': 'Fiction, Philosophy, Fantasy',
            'series': None,
            'publisher': 'Canongate Books',
            'published': '2020-08-13',
            'language': 'English',
            'isbn': '9781786892737',
            'format': 'EPUB'
        },
        {
            'id': 5,
            'title': 'Dune',
            'author': 'Frank Herbert',
            'timestamp': (datetime.now() - timedelta(days=20)).isoformat(),
            'rating': 5,
            'description': 'A sprawling epic of political intrigue and adventure on a desert planet.',
            'page_count': 688,
            'tags': 'Science Fiction, Classic, Epic',
            'series': 'Dune Chronicles',
            'publisher': 'Ace',
            'published': '1965-06-01',
            'language': 'English',
            'isbn': '9780441013593',
            'format': 'EPUB'
        }
    ]
    return mock_books

def load_books_data():
    """
    Load book data from persistent storage or use mock data if configured.
    """
    # Check if mock data is enabled
    if USE_MOCK_DATA:
        mock_books = get_mock_books()
        return {
            "books": mock_books,
            "last_updated": datetime.now().isoformat(),
            "total_books": len(mock_books),
            "source": "mock_data"
        }
    
    # Load from file
    try:
        if os.path.exists(BOOKS_FILE):
            with open(BOOKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Loaded {data.get('total_books', 0)} books from storage")
                return data
    except Exception as e:
        print(f"⚠️  Error loading books data: {e}")
    
    return {
        "books": [],
        "last_updated": None,
        "total_books": 0,
        "source": "none"
    }

def save_books_data(data):
    """
    Save book data to persistent storage.
    """
    try:
        with open(BOOKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved {data.get('total_books', 0)} books to storage")
        return True
    except Exception as e:
        print(f"❌ Error saving books data: {e}")
        return False

def fetch_opds_books():
    """
    Fetch comprehensive book data from Calibre-web OPDS feed.
    """
    if not CALIBRE_BASE_URL:
        return None
    
    try:
        base_url = CALIBRE_BASE_URL.rstrip('/')
        
        # Try multiple OPDS endpoints for newest books
        endpoints = [
            f"{base_url}/opds/new",
            f"{base_url}/opds/navcatalog/4e6577",  # "New" in hex
            f"{base_url}/opds/navcatalog/new",
            f"{base_url}/opds"
        ]
        
        books = []
        
        for endpoint in endpoints:
            try:
                print(f"🔍 Trying OPDS endpoint: {endpoint}")
                response = requests.get(endpoint, timeout=10)
                
                if response.status_code != 200:
                    continue
                    
                # Parse OPDS XML
                root = ET.fromstring(response.content)
                namespaces = {
                    'atom': 'http://www.w3.org/2005/Atom',
                    'dc': 'http://purl.org/dc/terms/',
                    'opds': 'http://opds-spec.org/2010/catalog'
                }
                
                entries = root.findall('atom:entry', namespaces)
                
                for entry in entries:
                    try:
                        # Skip navigation entries
                        links = entry.findall('atom:link', namespaces)
                        is_book = any(link.get('type', '').startswith('application/epub') or 
                                    link.get('type', '').startswith('application/pdf') or
                                    link.get('rel', '') == 'http://opds-spec.org/acquisition'
                                    for link in links)
                        
                        if not is_book:
                            continue
                        
                        # Extract comprehensive metadata
                        book_data = {}
                        
                        # Basic metadata
                        title = entry.find('atom:title', namespaces)
                        book_data['title'] = title.text if title is not None else "Unknown"
                        
                        author = entry.find('atom:author/atom:name', namespaces)
                        book_data['author'] = author.text if author is not None else "Unknown"
                        
                        # ID
                        book_id = entry.find('atom:id', namespaces)
                        if book_id is not None:
                            # Extract numeric ID from URN
                            id_text = book_id.text
                            if ':' in id_text:
                                book_data['id'] = int(id_text.split(':')[-1])
                            else:
                                book_data['id'] = hash(id_text) % 100000
                        
                        # Timestamps
                        updated = entry.find('atom:updated', namespaces)
                        published = entry.find('atom:published', namespaces) or entry.find('dc:date', namespaces)
                        
                        book_data['timestamp'] = updated.text if updated is not None else datetime.now().isoformat()
                        book_data['published'] = published.text if published is not None else None
                        
                        # Content and description
                        content = entry.find('atom:content', namespaces)
                        summary = entry.find('atom:summary', namespaces)
                        
                        if content is not None and content.text:
                            content_text = content.text
                            
                            # Extract rating
                            if 'Rating:' in content_text:
                                try:
                                    rating_text = content_text.split('Rating:')[1].split('<')[0].strip()
                                    book_data['rating'] = int(float(rating_text))
                                except:
                                    book_data['rating'] = 0
                            else:
                                book_data['rating'] = 0
                            
                            # Extract page count if present
                            if 'Pages:' in content_text or 'pages' in content_text.lower():
                                try:
                                    import re
                                    pages_match = re.search(r'(\d+)\s*pages?', content_text, re.IGNORECASE)
                                    if pages_match:
                                        book_data['page_count'] = int(pages_match.group(1))
                                    else:
                                        book_data['page_count'] = None
                                except:
                                    book_data['page_count'] = None
                            else:
                                book_data['page_count'] = None
                        else:
                            book_data['rating'] = 0
                            book_data['page_count'] = None
                        
                        # Description
                        if summary is not None and summary.text:
                            book_data['description'] = summary.text.strip()[:500]
                        else:
                            book_data['description'] = ""
                        
                        # Categories/Tags
                        categories = entry.findall('atom:category', namespaces)
                        tags_list = [cat.get('label', '') for cat in categories if cat.get('label')]
                        book_data['tags'] = ', '.join(tags_list) if tags_list else ''
                        
                        # Publisher
                        publisher = entry.find('dc:publisher', namespaces)
                        book_data['publisher'] = publisher.text if publisher is not None else None
                        
                        # Language
                        language = entry.find('dc:language', namespaces)
                        book_data['language'] = language.text if language is not None else None
                        
                        # ISBN
                        identifier = entry.find('dc:identifier', namespaces)
                        book_data['isbn'] = identifier.text if identifier is not None else None
                        
                        # Format
                        format_link = None
                        for link in links:
                            link_type = link.get('type', '')
                            if 'epub' in link_type:
                                book_data['format'] = 'EPUB'
                                break
                            elif 'pdf' in link_type:
                                book_data['format'] = 'PDF'
                                break
                            elif 'mobi' in link_type:
                                book_data['format'] = 'MOBI'
                                break
                        
                        if 'format' not in book_data:
                            book_data['format'] = 'Unknown'
                        
                        # Series information (if available in categories or content)
                        book_data['series'] = None
                        for cat in categories:
                            label = cat.get('label', '')
                            if 'series:' in label.lower():
                                book_data['series'] = label.split(':', 1)[1].strip()
                                break
                        
                        books.append(book_data)
                        
                    except Exception as e:
                        print(f"⚠️  Error parsing book entry: {e}")
                        continue
                
                if books:
                    print(f"✅ Successfully fetched {len(books)} books from OPDS")
                    return books
                    
            except Exception as e:
                print(f"⚠️  Error with endpoint {endpoint}: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"❌ OPDS fetch error: {e}")
        return None

def parse_book_timestamp(timestamp_value):
    """
    Parse various timestamp formats into a datetime object.
    """
    try:
        if isinstance(timestamp_value, str):
            # Handle ISO format with timezone
            if 'T' in timestamp_value:
                # Remove timezone suffix if present
                if '+' in timestamp_value:
                    timestamp_value = timestamp_value.split('+')[0]
                elif 'Z' in timestamp_value:
                    timestamp_value = timestamp_value.replace('Z', '')
                return datetime.fromisoformat(timestamp_value)
            else:
                # Handle space-separated format
                return datetime.fromisoformat(timestamp_value)
        else:
            # Fallback for other formats
            return datetime.fromisoformat(str(timestamp_value))
    except Exception as e:
        print(f"⚠️  Timestamp parsing error: {e}")
        return datetime.now() - timedelta(days=30)

def format_book_for_display(book):
    """
    Format a single book with all metadata for TRMNL display.
    """
    timestamp = parse_book_timestamp(book.get('timestamp'))
    now = datetime.now()
    days_ago = (now - timestamp).days
    
    # Format dates
    date_added = timestamp.strftime("%m/%d")
    year_added = timestamp.strftime("%Y")
    
    # Format rating
    rating_value = book.get('rating', 0)
    stars = "★" * int(rating_value) if rating_value else ""
    
    # Format tags
    tags = book.get('tags', '').strip()
    if len(tags) > 50:
        tags = tags[:47] + "..."
    
    # Page count with formatting
    page_count = book.get('page_count')
    pages_str = f"{page_count:,} pages" if page_count else "Unknown"
    
    return {
        # Core display fields
        "title": book.get('title', 'Unknown Title').strip(),
        "author": book.get('author', 'Unknown Author').strip(),
        "rating": stars,
        "rating_value": rating_value,
        "tags": tags,
        
        # Extended metadata
        "page_count": page_count,
        "pages_formatted": pages_str,
        "description": book.get('description', '').strip(),
        "series": book.get('series'),
        "publisher": book.get('publisher'),
        "language": book.get('language', 'Unknown'),
        "isbn": book.get('isbn'),
        "format": book.get('format', 'Unknown'),
        
        # Date information
        "date_added": date_added,
        "year_added": year_added,
        "days_ago": days_ago,
        "timestamp": timestamp.isoformat(),
        "published": book.get('published'),
        
        # Additional metadata
        "id": book.get('id', 0)
    }

@app.route('/')
def home():
    """
    API information and status endpoint.
    """
    books_data = load_books_data()
    
    return jsonify({
        "name": "TRMNL Calibre Library Plugin",
        "version": "6.0.0",
        "description": "Comprehensive Calibre library service for TRMNL displays",
        "status": "✅ Service operational",
        "configuration": {
            "calibre_base_url": CALIBRE_BASE_URL if CALIBRE_BASE_URL else "Not configured",
            "library_id": LIBRARY_ID,
            "sync_configured": SYNC_TOKEN != 'your-secret-sync-token-here',
            "mock_data_enabled": USE_MOCK_DATA,
            "port": PORT
        },
        "library_stats": {
            "total_books": books_data.get("total_books", 0),
            "last_updated": books_data.get("last_updated"),
            "data_source": books_data.get("source", "none")
        },
        "endpoints": {
            "/trmnl-data": "Main display endpoint (latest book)",
            "/books/recent": "List of recent books with full metadata",
            "/books/random": "Random book suggestion",
            "/sync": "Sync endpoint for local library",
            "/health": "Service health check",
            "/debug": "Debug information"
        }
    })

@app.route('/health')
def health():
    """
    Health check endpoint.
    """
    books_data = load_books_data()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_books": books_data.get("total_books", 0),
            "last_sync": books_data.get("last_updated", "Never"),
            "data_source": books_data.get("source", "none"),
            "has_data": len(books_data.get("books", [])) > 0
        },
        "configuration": {
            "mock_data": USE_MOCK_DATA,
            "opds_configured": bool(CALIBRE_BASE_URL),
            "sync_configured": SYNC_TOKEN != 'your-secret-sync-token-here'
        }
    })

@app.route('/debug')
def debug():
    """
    Debug endpoint with detailed configuration and data status.
    """
    books_data = load_books_data()
    
    debug_info = {
        "railway_variables": {
            "CALIBRE_BASE_URL": CALIBRE_BASE_URL if CALIBRE_BASE_URL else "Not set",
            "LIBRARY_ID": LIBRARY_ID,
            "SYNC_TOKEN": "Set" if SYNC_TOKEN != 'your-secret-sync-token-here' else "Not set",
            "USE_MOCK_DATA": USE_MOCK_DATA,
            "PORT": PORT
        },
        "data_status": {
            "source": books_data.get("source", "none"),
            "total_books": books_data.get("total_books", 0),
            "last_updated": books_data.get("last_updated", "Never"),
            "has_data": len(books_data.get("books", [])) > 0
        },
        "sample_book": None
    }
    
    # Include sample book data if available
    if books_data.get("books"):
        sample = books_data["books"][0]
        debug_info["sample_book"] = {
            "title": sample.get("title"),
            "fields_available": list(sample.keys()),
            "has_page_count": "page_count" in sample and sample["page_count"] is not None
        }
    
    # Test OPDS if configured
    if CALIBRE_BASE_URL and not USE_MOCK_DATA:
        debug_info["opds_test"] = {
            "url": CALIBRE_BASE_URL,
            "endpoints_to_try": [
                f"{CALIBRE_BASE_URL}/opds/new",
                f"{CALIBRE_BASE_URL}/opds"
            ]
        }
    
    return jsonify(debug_info)

@app.route('/sync', methods=['POST'])
def sync_books():
    """
    Sync endpoint for local Calibre library data.
    Expects comprehensive book metadata from sync script.
    """
    # Verify authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {SYNC_TOKEN}":
        print("🔒 Unauthorized sync attempt")
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Parse incoming data
        sync_data = request.get_json()
        if not sync_data or 'books' not in sync_data:
            return jsonify({"error": "Invalid data format"}), 400

        # Store comprehensive book data
        timestamp = datetime.now().isoformat()
        books_data = {
            "books": sync_data['books'],
            "last_updated": timestamp,
            "total_books": len(sync_data['books']),
            "source": sync_data.get('source', 'local_sync'),
            "sync_version": "6.0.0"
        }

        if save_books_data(books_data):
            print(f"📚 Synced {len(sync_data['books'])} books")
            
            # Calculate statistics
            books_with_pages = sum(1 for b in sync_data['books'] if b.get('page_count'))
            books_with_ratings = sum(1 for b in sync_data['books'] if b.get('rating', 0) > 0)
            
            return jsonify({
                "success": True,
                "message": "Library sync completed",
                "statistics": {
                    "total_books": len(sync_data['books']),
                    "books_with_pages": books_with_pages,
                    "books_with_ratings": books_with_ratings,
                    "timestamp": timestamp
                }
            })
        else:
            return jsonify({"error": "Failed to save data"}), 500

    except Exception as e:
        print(f"❌ Sync error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/trmnl-data', methods=['GET', 'POST'])
@app.route('/calibre-status', methods=['GET', 'POST'])  # Legacy support
def trmnl_data():
    """
    Main endpoint for TRMNL display - returns latest book with full metadata.
    """
    try:
        # Load book data
        books_data = load_books_data()
        books = books_data.get('books', [])
        
        # Try OPDS if no data and configured
        if not books and CALIBRE_BASE_URL and not USE_MOCK_DATA:
            print("📡 Attempting OPDS fetch...")
            opds_books = fetch_opds_books()
            if opds_books:
                books = opds_books
                books_data['source'] = 'opds_direct'
        
        current_time = datetime.now().strftime("%m/%d %H:%M")
        
        if not books:
            # No data available
            return jsonify({
                "title": "No Books Found",
                "author": "Sync your Calibre library",
                "rating": "",
                "tags": "",
                "total_books": 0,
                "rated_books": 0,
                "rating_percentage": 0,
                "server_status": "No Data",
                "current_time": current_time,
                "last_update": "Never",
                "pages_formatted": "",
                "description": "Use the sync script or configure OPDS"
            })
        
        # Calculate statistics
        total_books = len(books)
        rated_books = sum(1 for book in books if book.get('rating', 0) > 0)
        rating_percentage = int((rated_books / total_books * 100)) if total_books > 0 else 0
        books_with_pages = sum(1 for book in books if book.get('page_count'))
        
        # Get and format latest book
        latest_book = format_book_for_display(books[0])
        
        # Build response with comprehensive data
        response = {
            # Core display fields
            "title": latest_book['title'][:50],
            "author": latest_book['author'],
            "rating": latest_book['rating'],
            "tags": latest_book['tags'],
            
            # Library statistics
            "total_books": total_books,
            "rated_books": rated_books,
            "rating_percentage": rating_percentage,
            "books_with_pages": books_with_pages,
            
            # Extended book data
            "page_count": latest_book['page_count'],
            "pages_formatted": latest_book['pages_formatted'],
            "description": latest_book['description'][:200],
            "series": latest_book['series'],
            "format": latest_book['format'],
            "language": latest_book['language'],
            
            # Status and timing
            "server_status": "Connected",
            "current_time": current_time,
            "last_update": latest_book['date_added'] + " " + latest_book['timestamp'].split('T')[1][:5],
            "data_source": books_data.get('source', 'unknown'),
            
            # Additional metadata
            "days_ago": latest_book['days_ago'],
            "year_added": latest_book['year_added']
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            "title": "Service Error",
            "author": "Check logs",
            "rating": "",
            "tags": "",
            "total_books": 0,
            "rated_books": 0,
            "rating_percentage": 0,
            "server_status": "Error",
            "current_time": datetime.now().strftime("%m/%d %H:%M"),
            "error": str(e)
        }), 500

@app.route('/books/recent', methods=['GET', 'POST'])
def recent_books():
    """
    Get a list of recent books with full metadata.
    Supports limit parameter (default 10, max 50).
    """
    try:
        # Get limit from request
        if request.method == 'POST':
            data = request.get_json() or {}
            limit = int(data.get('limit', DEFAULT_BOOK_LIMIT))
        else:
            limit = int(request.args.get('limit', DEFAULT_BOOK_LIMIT))
        
        limit = max(1, min(limit, MAX_BOOK_LIMIT))
        
        # Load books
        books_data = load_books_data()
        books = books_data.get('books', [])[:limit]
        
        # Format all books
        formatted_books = [format_book_for_display(book) for book in books]
        
        return jsonify({
            "books": formatted_books,
            "count": len(formatted_books),
            "total_available": books_data.get('total_books', 0),
            "last_updated": books_data.get('last_updated'),
            "source": books_data.get('source', 'none')
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "books": []}), 500

@app.route('/books/random', methods=['GET', 'POST'])
def random_book():
    """
    Get a random book suggestion with full metadata.
    """
    try:
        books_data = load_books_data()
        books = books_data.get('books', [])
        
        if not books:
            return jsonify({"error": "No books available", "book": None})
        
        # Select and format random book
        random_book = random.choice(books)
        formatted_book = format_book_for_display(random_book)
        
        return jsonify({
            "book": formatted_book,
            "total_books": len(books),
            "source": books_data.get('source', 'none')
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "book": None}), 500

@app.route('/clear-cache', methods=['POST', 'GET'])
def clear_cache():
    """
    Clear stored book data (does not affect mock data mode).
    """
    if USE_MOCK_DATA:
        return jsonify({
            "success": False,
            "message": "Cannot clear cache in mock data mode"
        })
    
    try:
        if os.path.exists(BOOKS_FILE):
            os.remove(BOOKS_FILE)
            return jsonify({
                "success": True,
                "message": "Book data cleared"
            })
        else:
            return jsonify({
                "success": True,
                "message": "No data to clear"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print(f"🚀 Starting TRMNL Calibre Library Plugin")
    print(f"📚 Configuration:")
    print(f"   - Port: {PORT}")
    print(f"   - Mock Data: {USE_MOCK_DATA}")
    print(f"   - Sync Token: {'Configured' if SYNC_TOKEN != 'your-secret-sync-token-here' else 'Not set'}")
    print(f"   - OPDS URL: {CALIBRE_BASE_URL if CALIBRE_BASE_URL else 'Not configured'}")
    print(f"   - Library ID: {LIBRARY_ID}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
