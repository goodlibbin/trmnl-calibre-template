"""
TRMNL Calibre Library Plugin Backend

A Flask application that connects directly to your local Calibre library database
and provides book data in TRMNL-compatible JSON format.

Setup:
1. Install Flask: pip install flask
2. Run this script on the same computer as your Calibre library
3. Point your TRMNL plugin to: http://YOUR_LOCAL_IP:5001/calibre-status

Repository: https://github.com/goodlibbin/trmnl-calibre-template
License: MIT
"""

import os
import sqlite3
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import re

app = Flask(__name__)

# Cache for reducing database queries
cache = {}
CACHE_DURATION = 300  # 5 minutes

# Configuration
DEFAULT_PORT = 5001
CALIBRE_DB_PATH = os.environ.get('CALIBRE_DB_PATH')  # Optional custom path


def get_calibre_db_path():
    """Find the Calibre library database file."""
    # Use custom path if provided via environment variable
    if CALIBRE_DB_PATH:
        return CALIBRE_DB_PATH

    # Common Calibre database locations
    possible_paths = [
        os.path.expanduser("~/Calibre Library/metadata.db"),
        os.path.expanduser("~/Documents/Calibre Library/metadata.db"),
        os.path.expanduser("~/Library/Calibre Library/metadata.db"),  # macOS
        "/Users/Shared/Calibre Library/metadata.db",  # macOS shared
        os.path.expanduser("~/calibre-library/metadata.db"),
        # Windows paths
        os.path.expanduser("~/Documents/Calibre Library/metadata.db"),
        os.path.expanduser("~/My Documents/Calibre Library/metadata.db"),
        # Linux paths
        os.path.expanduser("~/.config/calibre/metadata.db"),
        "/opt/calibre/metadata.db"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # Default fallback
    return os.path.expanduser("~/Calibre Library/metadata.db")


def get_books_from_calibre(book_limit=50):
    """Get books from local Calibre database with robust error handling."""
    db_path = get_calibre_db_path()

    if not os.path.exists(db_path):
        print(f"❌ Calibre database not found at: {db_path}")
        return []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # First, test basic connectivity
        cursor.execute("SELECT COUNT(*) FROM books")
        total_books = cursor.fetchone()[0]
        print(f"📚 Found {total_books} total books in database")

        if total_books == 0:
            conn.close()
            return []

        # Get basic book info with simpler query
        try:
            cursor.execute("""
                SELECT id, title, timestamp, author_sort, path
                FROM books
                ORDER BY timestamp DESC
                LIMIT ?
            """, (book_limit,))

            basic_books = cursor.fetchall()
            print(f"📖 Retrieved {len(basic_books)} recent books")

        except Exception as e:
            print(f"❌ Error in basic book query: {e}")
            # Fallback to even simpler query
            cursor.execute("""
                SELECT id, title, timestamp
                FROM books
                ORDER BY id DESC
                LIMIT ?
            """, (book_limit,))
            basic_books = [(row[0], row[1], row[2], "Unknown Author", "") for row in cursor.fetchall()]
            print(f"📖 Using fallback query, retrieved {len(basic_books)} books")

        if not basic_books:
            conn.close()
            return []

        books = []

        for i, book_info in enumerate(basic_books):
            book_id = book_info[0]
            title = book_info[1] or f"Book {book_id}"
            timestamp = book_info[2] or "2020-01-01 00:00:00"
            author_sort = book_info[3] if len(book_info) > 3 else "Unknown Author"

            book_data = {
                'id': book_id,
                'title': title,
                'author': author_sort,
                'timestamp': timestamp,
                'rating': 0,
                'description': "",
                'page_count': None,
                'tags': ""
            }

            # Try to get additional metadata (with error handling for each)
            try:
                # Get rating
                cursor.execute("""
                    SELECT r.rating 
                    FROM books_ratings_link brl 
                    JOIN ratings r ON brl.rating = r.id 
                    WHERE brl.book = ?
                """, (book_id,))
                rating_result = cursor.fetchone()
                if rating_result:
                    book_data['rating'] = rating_result[0] or 0
            except Exception as e:
                print(f"⚠️  Rating query failed for book {book_id}: {e}")

            try:
                # Get description/comments
                cursor.execute("SELECT text FROM comments WHERE book = ?", (book_id,))
                desc_result = cursor.fetchone()
                if desc_result and desc_result[0]:
                    description = re.sub(r'<[^>]+>', '', str(desc_result[0])).strip()
                    if len(description) > 200:
                        description = description[:197] + "..."
                    book_data['description'] = description
            except Exception as e:
                print(f"⚠️  Description query failed for book {book_id}: {e}")

            try:
                # Get tags
                cursor.execute("""
                    SELECT GROUP_CONCAT(t.name, ', ') as tags
                    FROM books_tags_link btl
                    JOIN tags t ON btl.tag = t.id
                    WHERE btl.book = ?
                """, (book_id,))
                tags_result = cursor.fetchone()
                if tags_result and tags_result[0]:
                    book_data['tags'] = tags_result[0]
            except Exception as e:
                print(f"⚠️  Tags query failed for book {book_id}: {e}")

            try:
                # Get page count from Count Pages plugin
                cursor.execute("""
                    SELECT cp.value as page_count
                    FROM books_custom_column_links ccl
                    JOIN custom_columns cc ON ccl.column = cc.id
                    JOIN custom_column_text cp ON ccl.value = cp.id
                    WHERE ccl.book = ? AND cc.lookup_name = '#pages'
                """, (book_id,))
                page_result = cursor.fetchone()
                if page_result and page_result[0]:
                    try:
                        book_data['page_count'] = int(page_result[0])
                    except (ValueError, TypeError):
                        pass
            except Exception as e:
                print(f"⚠️  Page count query failed for book {book_id}: {e}")

            books.append(book_data)

        conn.close()
        print(f"✅ Successfully loaded {len(books)} books from Calibre")
        return books

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return []


def create_sample_data():
    """Generate sample library data when no Calibre database is found."""
    now = datetime.now()
    return {
        "empty_library": True,
        "server_connected": False,
        "message": "No Calibre library found. Make sure Calibre is installed and you have books in your library.",
        "this_week_books": [],
        "last_week_books": [],
        "earlier_books": [],
        "this_week_count": 0,
        "last_week_count": 0,
        "earlier_count": 0,
        "book_suggestion": None,
        "total_books_found": 0,
        "current_time": now.strftime("%m/%d"),
        "instructions": "1. Install Calibre and add some books, 2. Run this script on the same computer, 3. Connect TRMNL to this server"
    }


@app.route('/')
def home():
    """API information and setup instructions."""
    db_path = get_calibre_db_path()
    db_exists = os.path.exists(db_path)

    return jsonify({
        "name": "TRMNL Calibre Library Plugin",
        "version": "2.0.0",
        "description": "Display your local Calibre library on TRMNL e-ink devices",
        "mode": "Local database access",
        "status": "✅ Ready" if db_exists else "❌ Calibre library not found",
        "database_path": db_path,
        "database_found": db_exists,
        "endpoints": {
            "/calibre-status": "Main data endpoint for TRMNL",
            "/health": "Service health check",
            "/debug": "Connection diagnostics"
        },
        "setup_instructions": {
            "1": "Make sure Calibre is installed with books in your library",
            "2": "Run this script: python app.py",
            "3": "In TRMNL, set Backend URL to: http://YOUR_LOCAL_IP:5001",
            "4": "Find your local IP with: ipconfig (Windows) or ifconfig (Mac/Linux)"
        },
        "repository": "https://github.com/goodlibbin/trmnl-calibre-template"
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    db_path = get_calibre_db_path()
    db_accessible = os.path.exists(db_path)

    # Get book count if database is accessible
    book_count = 0
    if db_accessible:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            book_count = cursor.fetchone()[0]
            conn.close()
        except:
            pass

    return jsonify({
        "status": "healthy" if db_accessible else "database_not_found",
        "timestamp": datetime.now().isoformat(),
        "database_path": db_path,
        "database_accessible": db_accessible,
        "total_books": book_count,
        "cache_entries": len(cache)
    })


@app.route('/debug')
def debug():
    """Diagnostic endpoint for troubleshooting."""
    db_path = get_calibre_db_path()
    db_exists = os.path.exists(db_path)

    debug_info = {
        "database_path": db_path,
        "database_exists": db_exists,
        "current_directory": os.getcwd(),
        "environment_calibre_path": CALIBRE_DB_PATH,
        "sample_books": [],
        "total_books": 0,
        "features": {
            "tags_working": False,
            "ratings_working": False,
            "descriptions_working": False,
            "page_counts_available": False
        }
    }

    if db_exists:
        try:
            books = get_books_from_calibre(3)  # Get first 3 books for testing
            debug_info["total_books"] = len(books)

            if books:
                book = books[0]
                debug_info["features"]["tags_working"] = bool(book.get('tags'))
                debug_info["features"]["ratings_working"] = bool(book.get('rating'))
                debug_info["features"]["descriptions_working"] = bool(book.get('description'))
                debug_info["features"]["page_counts_available"] = bool(book.get('page_count'))

                debug_info["sample_books"] = [{
                    "title": book['title'],
                    "author": book['author'],
                    "tags": book['tags'],
                    "has_rating": bool(book['rating']),
                    "has_description": bool(book['description']),
                    "has_page_count": bool(book['page_count']),
                    "timestamp": book['timestamp']
                } for book in books]

        except Exception as e:
            debug_info["error"] = str(e)

    return jsonify(debug_info)


@app.route('/calibre-status', methods=['GET', 'POST'])
def calibre_status():
    """Main endpoint for TRMNL integration."""
    try:
        # Extract configuration from TRMNL form fields
        book_limit = 10
        show_descriptions = True
        show_page_counts = True

        if request.method == 'POST':
            data = request.get_json() or {}
            book_limit = int(data.get('book_limit', 10))
            show_descriptions = str(data.get('show_descriptions', 'true')).lower() == 'true'
            show_page_counts = str(data.get('show_page_counts', 'true')).lower() == 'true'
        else:
            # Support query parameters for testing
            book_limit = int(request.args.get('book_limit', 10))
            show_descriptions = request.args.get('show_descriptions', 'true').lower() == 'true'
            show_page_counts = request.args.get('show_page_counts', 'true').lower() == 'true'

        # Validate book limit
        book_limit = max(1, min(book_limit, 50))

        # Check cache first
        cache_key = f"books:{book_limit}:{show_descriptions}:{show_page_counts}"
        if cache_key in cache:
            cache_time, cached_data = cache[cache_key]
            if datetime.now() - cache_time < timedelta(seconds=CACHE_DURATION):
                return jsonify(cached_data)

        # Get books from database
        books = get_books_from_calibre(book_limit * 3)  # Get extra for date filtering

        if not books:
            result = create_sample_data()
            return jsonify(result)

        # Categorize books by addition date
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        this_week_books = []
        last_week_books = []
        earlier_books = []

        for i, book in enumerate(books, 1):
            # Parse timestamp
            try:
                if isinstance(book['timestamp'], str):
                    timestamp = datetime.fromisoformat(book['timestamp'].replace('T', ' ').split('+')[0])
                else:
                    timestamp = datetime.fromisoformat(str(book['timestamp']).replace('T', ' ').split('+')[0])
            except:
                timestamp = datetime.now() - timedelta(days=30)  # Default to older

            # Format rating as stars
            stars = "★" * int(book['rating']) if book['rating'] else ""

            # Apply user preferences
            description = book['description'] if show_descriptions else ""
            page_count = book['page_count'] if show_page_counts else None

            book_data = {
                "index": i,
                "title": book['title'],
                "author": book['author'],
                "tags": book['tags'],
                "rating": stars,
                "has_rating": bool(book['rating']),
                "description": description,
                "page_count": page_count
            }

            # Categorize by date
            if timestamp >= one_week_ago:
                if len(this_week_books) < book_limit:
                    this_week_books.append(book_data)
            elif timestamp >= two_weeks_ago:
                if len(last_week_books) < book_limit:
                    last_week_books.append(book_data)
            else:
                if len(earlier_books) < book_limit:
                    earlier_books.append(book_data)

        # Random book suggestion for roulette feature
        all_books = this_week_books + last_week_books + earlier_books
        book_suggestion = random.choice(all_books) if all_books else None

        result = {
            "empty_library": False,
            "server_connected": True,
            "this_week_books": this_week_books,
            "last_week_books": last_week_books,
            "earlier_books": earlier_books,
            "this_week_count": len(this_week_books),
            "last_week_count": len(last_week_books),
            "earlier_count": len(earlier_books),
            "book_suggestion": book_suggestion,
            "total_books_found": len(books),
            "current_time": now.strftime("%m/%d"),
            "data_source": "Local Calibre database"
        }

        # Cache the result
        cache[cache_key] = (datetime.now(), result)

        return jsonify(result)

    except Exception as e:
        print(f"❌ Error in calibre_status: {str(e)}")
        return jsonify({
            "error": f"Service error: {str(e)}",
            "empty_library": True,
            "server_connected": False,
            "message": "Unable to access Calibre library. Check that Calibre is installed and has books.",
            "current_time": datetime.now().strftime("%m/%d")
        }), 500


@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear the data cache to force fresh database queries."""
    global cache
    cache = {}
    return jsonify({
        "message": "Cache cleared successfully",
        "timestamp": datetime.now().isoformat()
    })


def get_local_ip():
    """Get the local IP address for user instructions."""
    import socket
    try:
        # Connect to a remote server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"


if __name__ == '__main__':
    port = int(os.environ.get('PORT', DEFAULT_PORT))

    print("=" * 60)
    print("🚀 TRMNL Calibre Library Plugin Starting...")
    print("=" * 60)

    db_path = get_calibre_db_path()
    db_exists = os.path.exists(db_path)
    local_ip = get_local_ip()

    print(f"📚 Calibre database: {db_path}")
    print(f"✅ Database found: {db_exists}")

    if db_exists:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            book_count = cursor.fetchone()[0]
            conn.close()
            print(f"📖 Total books: {book_count}")
        except:
            print("⚠️  Could not count books")

    print(f"🌐 Server starting on: http://{local_ip}:{port}")
    print(f"🔗 TRMNL Backend URL: http://{local_ip}:{port}")
    print("=" * 60)

    if not db_exists:
        print("❌ WARNING: No Calibre library found!")
        print("   Make sure Calibre is installed and you have books in your library.")
        print("   The server will show sample data until connected to a real library.")
        print("=" * 60)

    app.run(
        debug=False,
        host='0.0.0.0',  # Allow connections from network
        port=port
    )
