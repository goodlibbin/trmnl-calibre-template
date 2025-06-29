"""
TRMNL Calibre Library Plugin - Calibre-web Integration

Connects to your Calibre-web server and provides book data to TRMNL e-ink devices.
Fetches data directly from your Calibre-web OPDS feed - no manual syncing required!

Features:
- Displays recently added books in a clean, linear format
- Shows book ratings, authors, and tags
- Includes a random book suggestion feature
- Supports customizable display limits and formatting
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

# USER CONFIGURATION - UPDATE THESE VALUES WITH YOUR OWN
# =======================================================
# Your Calibre-web server URL
CALIBRE_BASE_URL = os.environ.get('CALIBRE_BASE_URL', 'http://[::1]:8080')
# Your library ID (usually "Calibre_Library")
LIBRARY_ID = os.environ.get('LIBRARY_ID', 'Calibre_Library')
# =======================================================

# Additional Configuration
DEFAULT_BOOK_LIMIT = int(os.environ.get('DEFAULT_BOOK_LIMIT', 10))
MAX_BOOK_LIMIT = int(os.environ.get('MAX_BOOK_LIMIT', 50))
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 10))

def test_calibre_web_connection():
    """
    Test connection to Calibre-web server.
    
    Returns:
        dict: Connection status and server info
    """
    try:
        test_url = f"{CALIBRE_BASE_URL}/opds"
        print(f"🔍 Testing connection to: {test_url}")
        
        response = requests.get(test_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        print(f"✅ Successfully connected to Calibre-web server")
        return {
            "connected": True,
            "status_code": response.status_code,
            "server_url": CALIBRE_BASE_URL
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Calibre-web: {e}")
        return {
            "connected": False,
            "error": str(e),
            "server_url": CALIBRE_BASE_URL
        }

def fetch_opds_feed():
    """
    Fetch recent books from Calibre-web OPDS feed.
    Follows navigation to find actual book entries.
    
    Returns:
        list: Recent books data or empty list if error
    """
    try:
        # Strategy 1: Try direct endpoints for recent books
        direct_urls = [
            f"{CALIBRE_BASE_URL}/opds/new?library_id={LIBRARY_ID}",
            f"{CALIBRE_BASE_URL}/opds/recentbooks?library_id={LIBRARY_ID}",
            f"{CALIBRE_BASE_URL}/opds/newest?library_id={LIBRARY_ID}"
        ]
        
        for url in direct_urls:
            try:
                print(f"📡 Trying direct endpoint: {url}")
                response = requests.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                
                books = parse_opds_xml(response.text)
                if books:
                    print(f"✅ Found {len(books)} books from direct endpoint")
                    return books
                    
            except Exception as e:
                print(f"⚠️  Direct endpoint failed {url}: {e}")
                continue
        
        # Strategy 2: Navigate through main OPDS to find "By Newest"
        print(f"📡 Fetching main OPDS catalog: {CALIBRE_BASE_URL}/opds?library_id={LIBRARY_ID}")
        response = requests.get(f"{CALIBRE_BASE_URL}/opds?library_id={LIBRARY_ID}", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        # Parse navigation feed to find "By Newest" link
        newest_url = find_newest_link(response.text)
        if newest_url:
            print(f"📡 Following 'By Newest' link: {newest_url}")
            response = requests.get(newest_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            books = parse_opds_xml(response.text)
            if books:
                print(f"✅ Found {len(books)} books from navigation")
                return books
        
        print("❌ No OPDS feeds returned valid book data")
        return []
        
    except Exception as e:
        print(f"❌ Error fetching OPDS feed: {e}")
        return []

def find_newest_link(xml_content):
    """
    Parse main OPDS feed to find the 'By Newest' navigation link.
    
    Args:
        xml_content (str): Main OPDS XML content
        
    Returns:
        str: URL for newest books feed or None
    """
    try:
        root = ET.fromstring(xml_content)
        namespaces = {'atom': 'http://www.w3.org/2005/Atom'}
        
        # Look for entry with title containing "Newest" or "Date"
        entries = root.findall('atom:entry', namespaces)
        for entry in entries:
            title_elem = entry.find('atom:title', namespaces)
            if title_elem is not None:
                title = title_elem.text.lower()
                if 'newest' in title or 'date' in title:
                    link_elem = entry.find('atom:link[@type="application/atom+xml;type=feed;profile=opds-catalog"]', namespaces)
                    if link_elem is not None:
                        href = link_elem.get('href')
                        if href:
                            # Convert relative URL to absolute
                            if href.startswith('/'):
                                return f"{CALIBRE_BASE_URL}{href}"
                            return href
        return None
        
    except Exception as e:
        print(f"⚠️  Error finding newest link: {e}")
        return None

def parse_opds_xml(xml_content):
    """
    Parse OPDS XML feed and extract book information.
    Enhanced to capture more metadata including page counts, series, formats.
    
    Args:
        xml_content (str): OPDS XML content
        
    Returns:
        list: Parsed book data
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Define namespaces
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'dc': 'http://purl.org/dc/terms/',
            'opds': 'http://opds-spec.org/2010/catalog',
            'calibre': 'http://calibre-ebook.com'
        }
        
        books = []
        entries = root.findall('atom:entry', namespaces)
        
        print(f"📖 Parsing {len(entries)} entries from OPDS feed")
        
        for entry in entries:
            try:
                # Extract basic info
                title_elem = entry.find('atom:title', namespaces)
                title = title_elem.text if title_elem is not None else 'Unknown Title'
                
                author_elem = entry.find('atom:author/atom:name', namespaces)
                author = author_elem.text if author_elem is not None else 'Unknown Author'
                
                # Extract updated/published date
                updated_elem = entry.find('atom:updated', namespaces)
                published_elem = entry.find('atom:published', namespaces)
                
                timestamp = None
                if updated_elem is not None:
                    timestamp = updated_elem.text
                elif published_elem is not None:
                    timestamp = published_elem.text
                else:
                    timestamp = datetime.now().isoformat()
                
                # Extract summary/description
                summary_elem = entry.find('atom:summary', namespaces)
                content_elem = entry.find('atom:content', namespaces)
                description = ''
                if summary_elem is not None:
                    description = summary_elem.text or ''
                elif content_elem is not None:
                    description = content_elem.text or ''
                
                # Extract categories/tags
                categories = entry.findall('atom:category', namespaces)
                tags = []
                for cat in categories:
                    label = cat.get('label') or cat.get('term')
                    if label and label not in ['Book', 'book']:  # Filter out generic categories
                        tags.append(label)
                
                # Extract rating from various possible locations
                rating = 0
                # Try DC metadata
                rating_elem = entry.find('.//dc:rating', namespaces)
                if rating_elem is not None:
                    try:
                        rating = float(rating_elem.text)
                        # Convert 10-scale to 5-scale if needed
                        if rating > 5:
                            rating = rating / 2
                    except (ValueError, TypeError):
                        rating = 0
                
                # Extract series information
                series = ''
                series_elem = entry.find('.//dc:series', namespaces)
                if series_elem is not None:
                    series = series_elem.text or ''
                
                # Extract language
                language = ''
                lang_elem = entry.find('.//dc:language', namespaces)
                if lang_elem is not None:
                    language = lang_elem.text or ''
                
                # Extract publisher
                publisher = ''
                pub_elem = entry.find('.//dc:publisher', namespaces)
                if pub_elem is not None:
                    publisher = pub_elem.text or ''
                
                # Extract published date (different from updated)
                pub_date = ''
                pub_date_elem = entry.find('.//dc:issued', namespaces)
                if pub_date_elem is not None:
                    pub_date = pub_date_elem.text or ''
                
                # Extract page count (if available from Count Pages plugin)
                page_count = None
                # Look for page count in various locations
                for elem in entry.iter():
                    if elem.text and 'pages' in str(elem.text).lower():
                        # Try to extract number from text like "245 pages"
                        import re
                        match = re.search(r'(\d+)\s*pages?', str(elem.text), re.IGNORECASE)
                        if match:
                            try:
                                page_count = int(match.group(1))
                                break
                            except ValueError:
                                continue
                
                # Extract available formats
                formats = []
                links = entry.findall('atom:link', namespaces)
                for link in links:
                    link_type = link.get('type', '')
                    if link_type.startswith('application/') and 'opds' not in link_type:
                        # Extract format from MIME type
                        if 'epub' in link_type:
                            formats.append('EPUB')
                        elif 'pdf' in link_type:
                            formats.append('PDF')
                        elif 'mobi' in link_type:
                            formats.append('MOBI')
                        elif 'azw' in link_type:
                            formats.append('AZW')
                
                # Extract file size (from largest available format)
                file_size = None
                for link in links:
                    length = link.get('length')
                    if length:
                        try:
                            size_bytes = int(length)
                            if not file_size or size_bytes > file_size:
                                file_size = size_bytes
                        except ValueError:
                            continue
                
                # Estimate page count from file size if not available
                if not page_count and file_size:
                    # Rough estimate: 1 page ≈ 2KB for text-heavy books
                    page_count = max(1, int(file_size / 2048))
                
                book_data = {
                    'title': title.strip(),
                    'author': author.strip(),
                    'tags': ', '.join(tags) if tags else '',
                    'rating': rating,
                    'timestamp': timestamp,
                    'description': description.strip() if description else '',
                    'page_count': page_count,
                    'series': series.strip() if series else '',
                    'language': language.strip() if language else '',
                    'publisher': publisher.strip() if publisher else '',
                    'published_date': pub_date,
                    'formats': formats,
                    'file_size': file_size
                }
                
                books.append(book_data)
                
            except Exception as e:
                print(f"⚠️  Error parsing entry: {e}")
                continue
        
        print(f"✅ Successfully parsed {len(books)} books")
        return books
        
    except ET.ParseError as e:
        print(f"❌ XML parsing error: {e}")
        return []
    except Exception as e:
        print(f"❌ Error parsing OPDS XML: {e}")
        return []

def parse_book_timestamp(timestamp_value):
    """
    Parse various timestamp formats into a datetime object.
    
    Args:
        timestamp_value: Timestamp in various formats
        
    Returns:
        datetime: Parsed timestamp or default if parsing fails
    """
    try:
        if isinstance(timestamp_value, str):
            timestamp_str = timestamp_value
            # Remove timezone info if present
            if '+' in timestamp_str:
                timestamp_str = timestamp_str.split('+')[0]
            # Handle T separator
            if 'T' in timestamp_str:
                timestamp_str = timestamp_str.replace('T', ' ')
            return datetime.fromisoformat(timestamp_str)
        else:
            # Handle other formats
            timestamp_str = str(timestamp_value).replace('T', ' ').split('+')[0]
            return datetime.fromisoformat(timestamp_str)
    except Exception as e:
        print(f"⚠️  Timestamp parsing error: {e}")
        # Return a date 30 days ago as fallback
        return datetime.now() - timedelta(days=30)

def prepare_recent_books(books, book_limit=None):
    """
    Prepare a linear list of recently added books for TRMNL display.
    
    Args:
        books (list): Raw book data from Calibre
        book_limit (int): Maximum number of books to return
        
    Returns:
        list: Formatted book data optimized for TRMNL display
    """
    if book_limit is None:
        book_limit = DEFAULT_BOOK_LIMIT
    
    book_limit = max(1, min(book_limit, MAX_BOOK_LIMIT))
    recent_books = []
    now = datetime.now()
    
    print(f"📚 Preparing {min(len(books), book_limit)} books for display")
    
    for i, book in enumerate(books[:book_limit]):
        # Parse timestamp for sorting and display
        timestamp = parse_book_timestamp(book.get('timestamp'))
        days_ago = (now - timestamp).days
        
        # Format date for display (MM/DD format)
        date_added = timestamp.strftime("%m/%d")
        
        # Format rating as stars or empty string
        rating_value = book.get('rating', 0)
        stars = "★" * int(rating_value) if rating_value else ""
        
        # Clean and format tags
        tags = book.get('tags', '').strip()
        if len(tags) > 30:  # Truncate long tag lists for e-ink display
            tags = tags[:27] + "..."
        
        # Create optimized book data for TRMNL
        book_data = {
            "index": i + 1,
            "title": book.get('title', 'Unknown Title').strip(),
            "author": book.get('author', 'Unknown Author').strip(),
            "tags": tags,
            "rating": stars,
            "has_rating": bool(rating_value),
            "description": book.get('description', '').strip(),
            "page_count": book.get('page_count'),
            "date_added": date_added,
            "days_ago": days_ago,
            "timestamp": timestamp.isoformat()
        }
        
        recent_books.append(book_data)
    
    print(f"✅ Formatted {len(recent_books)} books for TRMNL display")
    return recent_books

@app.route('/')
def home():
    """
    API information and status endpoint.
    
    Returns:
        JSON response with service information and current status
    """
    connection_status = test_calibre_web_connection()
    
    return jsonify({
        "name": "TRMNL Calibre Library Plugin",
        "version": "4.0.0",
        "description": "Calibre-web integration for TRMNL e-ink devices",
        "status": "✅ Service operational",
        "calibre_web": {
            "server_url": CALIBRE_BASE_URL,
            "library_id": LIBRARY_ID,
            "connected": connection_status["connected"],
            "connection_test": connection_status
        },
        "endpoints": {
            "/calibre-status": "Main data endpoint for TRMNL devices",
            "/trmnl-data": "Legacy endpoint (backwards compatibility)",
            "/health": "Service health monitoring",
            "/debug": "Debug information and connection test"
        },
        "configuration": {
            "default_book_limit": DEFAULT_BOOK_LIMIT,
            "max_book_limit": MAX_BOOK_LIMIT,
            "request_timeout": REQUEST_TIMEOUT
        }
    })

@app.route('/health')
def health():
    """
    Health check endpoint for monitoring service status.
    
    Returns:
        JSON response with health status and metrics
    """
    connection_status = test_calibre_web_connection()
    
    health_status = {
        "status": "healthy" if connection_status["connected"] else "degraded",
        "timestamp": datetime.now().isoformat(),
        "calibre_web": {
            "server_reachable": connection_status["connected"],
            "server_url": CALIBRE_BASE_URL,
            "last_check": datetime.now().isoformat()
        },
        "service_info": {
            "version": "4.0.0",
            "environment": "calibre-web-integration",
            "data_source": "OPDS feed"
        }
    }
    
    print(f"💚 Health check: Calibre-web {'connected' if connection_status['connected'] else 'disconnected'}")
    return jsonify(health_status)

@app.route('/debug')
def debug():
    """
    Debug endpoint for troubleshooting Calibre-web connection.
    
    Returns:
        JSON response with detailed debug information
    """
    connection_status = test_calibre_web_connection()
    
    # Try to fetch a sample of books
    books = fetch_opds_feed()
    
    debug_info = {
        "calibre_web_connection": connection_status,
        "opds_feed_test": {
            "books_found": len(books),
            "sample_books": books[:3] if books else [],
            "fetch_successful": len(books) > 0
        },
        "configuration": {
            "calibre_base_url": CALIBRE_BASE_URL,
            "library_id": LIBRARY_ID,
            "default_book_limit": DEFAULT_BOOK_LIMIT,
            "request_timeout": REQUEST_TIMEOUT
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return jsonify(debug_info)

@app.route('/config')
def get_config():
    """
    Return available configuration options for display customization.
    Enhanced with all available book metadata fields.
    
    Returns:
        JSON response with configuration options
    """
    return jsonify({
        "calibre_web": {
            "server_url": CALIBRE_BASE_URL,
            "library_id": LIBRARY_ID,
            "opds_endpoints": [
                "/opds/new",
                "/opds/recentbooks", 
                "/opds/newest",
                "/opds/navcatalog/4f6e6577657374"  # By Newest navigation
            ]
        },
        "display_options": {
            "book_limit": {
                "default": DEFAULT_BOOK_LIMIT,
                "min": 1,
                "max": MAX_BOOK_LIMIT,
                "description": "Number of recent books to display"
            },
            "date_format": {
                "options": ["MM/DD", "MM/DD/YYYY", "relative"],
                "default": "MM/DD",
                "description": "How to display book addition dates"
            }
        },
        "available_fields": {
            "basic": [
                "title", "author", "tags", "rating", "description"
            ],
            "metadata": [
                "series", "language", "publisher", "published_date"
            ],
            "file_info": [
                "page_count", "page_display", "reading_time", 
                "formats", "file_info", "file_size"
            ],
            "computed": [
                "date_added", "days_ago", "is_recent", "is_new",
                "has_rating", "has_series", "has_page_count"
            ]
        },
        "display_features": {
            "opds_integration": True,
            "real_time_data": True,
            "enhanced_metadata": True,
            "page_count_support": True,
            "series_detection": True,
            "format_detection": True,
            "reading_time_estimates": True,
            "random_suggestion": True,
            "flexible_layouts": True
        },
        "template_variables": {
            "description": "All fields available in TRMNL templates",
            "book_fields": [
                "{{ book.title }}", "{{ book.author }}", "{{ book.rating }}",
                "{{ book.tags }}", "{{ book.description }}", "{{ book.date_added }}",
                "{{ book.page_display }}", "{{ book.reading_time }}",
                "{{ book.series_info }}", "{{ book.file_info }}",
                "{{ book.has_rating }}", "{{ book.is_recent }}", "{{ book.is_new }}"
            ]
        }
    })

@app.route('/calibre-status', methods=['GET', 'POST'])
@app.route('/trmnl-data', methods=['GET', 'POST'])  # Legacy endpoint
def calibre_status():
    """
    Main endpoint for TRMNL device integration.
    Returns formatted book data optimized for e-ink display.
    
    Supports both GET and POST requests with optional configuration parameters.
    
    Returns:
        JSON response with book data formatted for TRMNL templates
    """
    try:
        # Test Calibre-web connection first
        connection_status = test_calibre_web_connection()
        current_date = datetime.now().strftime("%m/%d")

        print(f"📊 TRMNL request: Testing Calibre-web connection")

        # Handle connection failure
        if not connection_status["connected"]:
            print(f"❌ Calibre-web server not reachable: {connection_status.get('error', 'Unknown error')}")
            return jsonify({
                "empty_library": True,
                "server_connected": False,
                "message": f"Cannot connect to Calibre-web server at {CALIBRE_BASE_URL}. Please check your configuration.",
                "recent_books": [],
                "book_suggestion": None,
                "library_stats": {
                    "total_books_found": 0,
                    "last_sync": "Server unreachable",
                    "data_source": "Calibre-web OPDS",
                    "connection_error": connection_status.get('error', 'Unknown error')
                },
                "display_info": {
                    "current_date": current_date,
                    "recent_books_count": 0
                }
            })

        # Fetch books from OPDS feed
        books = fetch_opds_feed()

        # Handle empty library
        if not books:
            print("📭 No books found in OPDS feed - returning empty library state")
            return jsonify({
                "empty_library": True,
                "server_connected": True,
                "message": "Your Calibre-web library is connected but no recent books were found. Add some books to see them here!",
                "recent_books": [],
                "book_suggestion": None,
                "library_stats": {
                    "total_books_found": 0,
                    "last_sync": datetime.now().isoformat(),
                    "data_source": "Calibre-web OPDS"
                },
                "display_info": {
                    "current_date": current_date,
                    "recent_books_count": 0
                }
            })

        # Extract display configuration from request
        book_limit = DEFAULT_BOOK_LIMIT
        if request.method == 'POST':
            request_data = request.get_json() or {}
            book_limit = int(request_data.get('book_limit', DEFAULT_BOOK_LIMIT))
        else:
            book_limit = int(request.args.get('book_limit', DEFAULT_BOOK_LIMIT))

        # Validate and constrain book limit
        book_limit = max(1, min(book_limit, MAX_BOOK_LIMIT))

        # Prepare books for display
        recent_books = prepare_recent_books(books, book_limit)

        # Select random book for suggestion feature
        book_suggestion = random.choice(recent_books) if recent_books else None
        if book_suggestion:
            print(f"🎲 Random suggestion: '{book_suggestion['title']}' by {book_suggestion['author']}")

        # Prepare response data
        response_data = {
            "empty_library": False,
            "server_connected": True,
            "recent_books": recent_books,
            "book_suggestion": book_suggestion,
            "library_stats": {
                "total_books_found": len(books),
                "last_sync": datetime.now().isoformat(),
                "data_source": "Calibre-web OPDS",
                "server_url": CALIBRE_BASE_URL
            },
            "display_info": {
                "current_date": current_date,
                "recent_books_count": len(recent_books),
                "book_limit_used": book_limit
            }
        }

        print(f"✅ Returning {len(recent_books)} books to TRMNL device")
        return jsonify(response_data)

    except Exception as e:
        print(f"❌ Error processing TRMNL request: {str(e)}")
        return jsonify({
            "error": f"Service error: {str(e)}",
            "empty_library": True,
            "server_connected": False,
            "message": "A service error occurred. Please check the logs or try again later.",
            "display_info": {
                "current_date": datetime.now().strftime("%m/%d")
            }
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with helpful information."""
    return jsonify({
        "error": "Endpoint not found",
        "message": "Available endpoints: /, /health, /calibre-status, /sync, /config",
        "status": 404
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors gracefully."""
    print(f"💥 Internal server error: {error}")
    return jsonify({
        "error": "Internal server error",
        "message": "A server error occurred. Please try again later.",
        "status": 500
    }), 500

if __name__ == '__main__':
    # Development server configuration
    port = int(os.environ.get('PORT', 5052))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 Starting TRMNL Calibre Library Plugin on port {port}")
    print(f"📚 Calibre-web server: {CALIBRE_BASE_URL}")
    print(f"📖 Library ID: {LIBRARY_ID}")
    print(f"🔧 Debug mode: {debug_mode}")
    
    # Test connection on startup
    connection_status = test_calibre_web_connection()
    if connection_status["connected"]:
        print(f"✅ Successfully connected to Calibre-web server")
    else:
        print(f"⚠️  Could not connect to Calibre-web server: {connection_status.get('error', 'Unknown error')}")
        print(f"💡 Make sure Calibre-web is running at: {CALIBRE_BASE_URL}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
