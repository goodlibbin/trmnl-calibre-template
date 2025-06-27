"""
TRMNL Calibre Library Plugin Backend

A Flask application that connects to your Calibre library database and provides
book data in TRMNL-compatible JSON format.

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


def get_calibre_db_path():
    """Find the Calibre library database file."""
    possible_paths = [
        os.path.expanduser("~/Calibre Library/metadata.db"),
        os.path.expanduser("~/Documents/Calibre Library/metadata.db"),
        os.path.expanduser("~/Library/Calibre Library/metadata.db"),  # macOS
        "/Users/Shared/Calibre Library/metadata.db",
        os.path.expanduser("~/calibre-library/metadata.db"),
        "/calibre/metadata.db",
        "/data/calibre/metadata.db"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return os.path.expanduser("~/Calibre Library/metadata.db")


def get_books_from_calibre(book_limit=50):
    """Get books from Calibre database with simplified queries."""
    db_path = get_calibre_db_path()
    
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First, get basic book info - simplified query
        cursor.execute("""
            SELECT b.id, b.title, b.timestamp, b.author_sort, b.path
            FROM books b
            ORDER BY b.timestamp DESC
            LIMIT ?
        """, (book_limit,))
        
        basic_books = cursor.fetchall()
        
        if not basic_books:
            conn.close()
            return []
        
        books = []
        
        for book_id, title, timestamp, author_sort, path in basic_books:
            book_data = {
                'id': book_id,
                'title': title or "Unknown Title",
                'author': author_sort or "Unknown Author",
                'timestamp': timestamp,
                'rating': 0,
                'description': "",
                'page_count': None,
                'tags': ""
            }
            
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
            
            # Get description
            cursor.execute("""
                SELECT text FROM comments WHERE book = ?
            """, (book_id,))
            desc_result = cursor.fetchone()
            if desc_result and desc_result[0]:
                description = re.sub(r'<[^>]+>', '', desc_result[0]).strip()
                if len(description) > 200:
                    description = description[:197] + "..."
                book_data['description'] = description
            
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
            
            # Get page count from custom column (if exists)
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
            
            books.append(book_data)
        
        conn.close()
        return books
        
    except Exception as e:
        print(f"Database error: {e}")
        return []


def create_sample_data():
    """Generate sample library data for testing."""
    return {
        "empty_library": False,
        "server_connected": False,
        "message": "Sample data - Connect your Calibre library to see your actual books",
        "this_week_books": [
            {
                "index": 1,
                "title": "The Midnight Library",
                "author": "Matt Haig",
                "tags": "Fiction, Philosophy",
                "rating": "★★★★★",
                "has_rating": True,
                "description": "Between life and death there is a library, and within that library, the shelves go on forever.",
                "page_count": 288
            }
        ],
        "last_week_books": [],
        "earlier_books": [],
        "this_week_count": 1,
        "last_week_count": 0,
        "earlier_count": 0,
        "book_suggestion": {
            "index": 1,
            "title": "The Midnight Library",
            "author": "Matt Haig",
            "tags": "Fiction, Philosophy",
            "rating": "★★★★★",
            "has_rating": True,
            "description": "Between life and death there is a library, and within that library, the shelves go on forever.",
            "page_count": 288
        },
        "total_books_found": 1,
        "current_time": datetime.now().strftime("%m/%d %H:%M")
    }


@app.route('/')
def home():
    """API information endpoint."""
    return jsonify({
        "name": "TRMNL Calibre Library Plugin",
        "version": "1.1.0",
        "description": "Display your Calibre library on TRMNL e-ink devices",
        "endpoints": {
            "/calibre-status": "Main data endpoint for TRMNL",
            "/health": "Service health check",
            "/debug": "Connection diagnostics",
            "/test-db": "Simple database test"
        },
        "repository": "https://github.com/goodlibbin/trmnl-calibre-template"
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    db_accessible = os.path.exists(get_calibre_db_path())
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_accessible": db_accessible,
        "database_path": get_calibre_db_path(),
        "cache_entries": len(cache)
    })


@app.route('/test-db')
def test_db():
    """Simple database test endpoint."""
    db_path = get_calibre_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Simple count query
        cursor.execute("SELECT COUNT(*) FROM books")
        total_count = cursor.fetchone()[0]
        
        # Get first few books with basic info
        cursor.execute("SELECT id, title, timestamp, author_sort FROM books ORDER BY timestamp DESC LIMIT 5")
        sample_books = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "database_path": db_path,
            "total_books": total_count,
            "sample_books": [
                {
                    "id": b[0], 
                    "title": b[1], 
                    "timestamp": b[2],
                    "author": b[3]
                } for b in sample_books
            ]
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e), 
            "database_path": db_path
        })


@app.route('/debug')
def debug():
    """Diagnostic endpoint for troubleshooting."""
    db_path = get_calibre_db_path()
    db_exists = os.path.exists(db_path)
    
    debug_info = {
        "database_path": db_path,
        "database_exists": db_exists,
        "sample_books": [],
        "total_books": 0,
        "tags_working": False,
        "page_counts_available": False
    }
    
    if db_exists:
        try:
            books = get_books_from_calibre(3)  # Get first 3 books
            debug_info["total_books"] = len(books)
            
            if books:
                book = books[0]
                debug_info["tags_working"] = bool(book.get('tags'))
                debug_info["page_counts_available"] = bool(book.get('page_count'))
                
                debug_info["sample_books"] = [{
                    "title": book['title'],
                    "author": book['author'],
                    "tags": book['tags'],
                    "has_rating": bool(book['rating']),
                    "has_description": bool(book['description']),
                    "has_page_count": bool(book['page_count']),
                    "timestamp": book['timestamp']
                }]
                
        except Exception as e:
            debug_info["database_error"] = str(e)
    
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
            show_descriptions = data.get('show_descriptions', True)
            show_page_counts = data.get('show_page_counts', True)
        else:
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
            result["empty_library"] = True
            result["message"] = "No books found in Calibre library. Check your database path and permissions."
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
                    # Calibre stores timestamps as strings like "2024-06-27 18:30:45+00:00"
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
        
        # Select random book for roulette feature
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
            "current_time": now.strftime("%m/%d %H:%M")
        }
        
        # Cache the result
        cache[cache_key] = (datetime.now(), result)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in calibre_status: {str(e)}")
        return jsonify({
            "error": f"Service error: {str(e)}",
            "empty_library": True,
            "server_connected": False,
            "message": "Unable to process library data. Check logs for details.",
            "current_time": datetime.now().strftime("%m/%d %H:%M")
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    print(f"Starting TRMNL Calibre Library Plugin on port {port}")
    print(f"Calibre database path: {get_calibre_db_path()}")
    print(f"Database accessible: {os.path.exists(get_calibre_db_path())}")
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
