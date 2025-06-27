"""
TRMNL Calibre Library Plugin Backend

A Flask application that connects to your Calibre library database and provides
book data in TRMNL-compatible JSON format. Designed for self-hosting by users
who want to display their personal library on TRMNL e-ink devices.

Features:
- Direct Calibre database integration for accurate metadata
- Support for ratings, tags, descriptions, and page counts
- Time-based book categorization (This Week, Last Week, Earlier)
- Book roulette feature for discovery
- TRMNL form field integration
- Smart caching to reduce database load

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
    """
    Locate the Calibre library database file.
    
    Searches common Calibre installation locations and returns the path
    to metadata.db. Users may need to customize this for non-standard
    installations.
    
    Returns:
        str: Path to the Calibre metadata.db file
    """
    possible_paths = [
        os.path.expanduser("~/Calibre Library/metadata.db"),
        os.path.expanduser("~/Documents/Calibre Library/metadata.db"),
        os.path.expanduser("~/Library/Calibre Library/metadata.db"),  # macOS
        "/Users/Shared/Calibre Library/metadata.db",
        os.path.expanduser("~/calibre-library/metadata.db"),
        # Add Windows common paths
        os.path.expanduser("~/Documents/My Digital Editions/metadata.db"),
        # Docker/server paths
        "/calibre/metadata.db",
        "/data/calibre/metadata.db"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Default fallback
    return os.path.expanduser("~/Calibre Library/metadata.db")


def get_books_from_calibre(book_limit=20):
    """
    Extract book data from the Calibre database.
    
    Queries the Calibre SQLite database for book metadata including:
    - Basic info (title, authors, timestamp)
    - Ratings (from built-in rating system)
    - Descriptions (from comments)
    - Page counts (from Count Pages plugin custom column)
    - Tags (categories/genres)
    
    Args:
        book_limit (int): Maximum number of books to return
        
    Returns:
        list: List of book dictionaries with metadata
    """
    db_path = get_calibre_db_path()
    
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Comprehensive query for book data with page count support
        query = """
        SELECT 
            b.id,
            b.title,
            GROUP_CONCAT(a.name, ' & ') as authors,
            b.timestamp,
            r.rating,
            c.text as description,
            cp.value as page_count
        FROM books b
        LEFT JOIN books_authors_link bal ON b.id = bal.book
        LEFT JOIN authors a ON bal.author = a.id
        LEFT JOIN books_ratings_link brl ON b.id = brl.book
        LEFT JOIN ratings r ON brl.rating = r.id
        LEFT JOIN comments c ON b.id = c.book
        LEFT JOIN books_custom_column_links ccl ON b.id = ccl.book
        LEFT JOIN custom_columns cc ON ccl.column = cc.id AND cc.lookup_name = '#pages'
        LEFT JOIN custom_column_text cp ON ccl.value = cp.id
        GROUP BY b.id, b.title, b.timestamp, r.rating, c.text, cp.value
        ORDER BY b.timestamp DESC
        LIMIT ?
        """
        
        cursor.execute(query, (book_limit * 2,))  # Get extra for filtering
        books = cursor.fetchall()
        conn.close()
        
        return books
        
    except Exception as e:
        print(f"Database error: {e}")
        return []


def get_book_tags(book_id):
    """
    Get tags/categories for a specific book.
    
    Args:
        book_id (int): Calibre book ID
        
    Returns:
        str: Comma-separated list of tags
    """
    db_path = get_calibre_db_path()
    
    if not os.path.exists(db_path):
        return ""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = """
        SELECT GROUP_CONCAT(t.name, ', ') as tags
        FROM books_tags_link btl
        JOIN tags t ON btl.tag = t.id
        WHERE btl.book = ?
        """
        
        cursor.execute(query, (book_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else ""
        
    except Exception as e:
        print(f"Tag query error: {e}")
        return ""


def create_sample_data():
    """
    Generate sample library data for testing and demonstration.
    
    This is displayed when no Calibre database is found or for users
    testing the plugin before connecting their actual library.
    
    Returns:
        dict: Sample book data in the expected format
    """
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
                "description": "Between life and death there is a library, and within that library, the shelves go on forever. Every book provides a chance to try another life you could have lived.",
                "page_count": 288
            },
            {
                "index": 2,
                "title": "Atomic Habits",
                "author": "James Clear",
                "tags": "Self-Help, Psychology",
                "rating": "★★★★",
                "has_rating": True,
                "description": "Tiny changes, remarkable results. An easy and proven way to build good habits and break bad ones.",
                "page_count": 320
            }
        ],
        "last_week_books": [
            {
                "index": 3,
                "title": "Dune",
                "author": "Frank Herbert",
                "tags": "Science Fiction, Classic",
                "rating": "★★★★★",
                "has_rating": True,
                "description": "Set on the desert planet Arrakis, Dune is the story of the boy Paul Atreides, heir to a noble family tasked with ruling an inhospitable world.",
                "page_count": 688
            }
        ],
        "earlier_books": [
            {
                "index": 4,
                "title": "The Seven Husbands of Evelyn Hugo",
                "author": "Taylor Jenkins Reid",
                "tags": "Romance, Historical Fiction",
                "rating": "★★★★",
                "has_rating": True,
                "description": "Reclusive Hollywood icon Evelyn Hugo finally decides to tell her life story to an unknown journalist.",
                "page_count": 400
            }
        ],
        "this_week_count": 2,
        "last_week_count": 1,
        "earlier_count": 1,
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
        "total_books_found": 4,
        "current_time": datetime.now().strftime("%m/%d %H:%M")
    }


@app.route('/')
def home():
    """API information endpoint."""
    return jsonify({
        "name": "TRMNL Calibre Library Plugin",
        "version": "1.0.0",
        "description": "Display your Calibre library on TRMNL e-ink devices",
        "endpoints": {
            "/calibre-status": "Main data endpoint for TRMNL",
            "/health": "Service health check",
            "/debug": "Connection diagnostics"
        },
        "repository": "https://github.com/your-username/trmnl-calibre-template",
        "documentation": "See README.md for setup instructions"
    })


@app.route('/health')
def health():
    """
    Health check endpoint for monitoring service status.
    
    Returns:
        JSON with service status and database connectivity
    """
    db_accessible = os.path.exists(get_calibre_db_path())
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_accessible": db_accessible,
        "database_path": get_calibre_db_path(),
        "cache_entries": len(cache)
    })


@app.route('/debug')
def debug():
    """
    Diagnostic endpoint for troubleshooting setup issues.
    
    Provides detailed information about database connectivity,
    sample data, and configuration for user debugging.
    """
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
            books = get_books_from_calibre(5)  # Get first 5 books
            debug_info["total_books"] = len(books)
            
            if books:
                # Process first book for detailed info
                book = books[0]
                book_id, title, authors, timestamp_str, rating, description, page_count_str = book
                
                tags = get_book_tags(book_id)
                debug_info["tags_working"] = bool(tags)
                debug_info["page_counts_available"] = bool(page_count_str)
                
                debug_info["sample_books"] = [{
                    "title": title,
                    "author": authors,
                    "tags": tags,
                    "has_rating": bool(rating),
                    "has_description": bool(description),
                    "has_page_count": bool(page_count_str),
                    "timestamp": timestamp_str
                }]
                
        except Exception as e:
            debug_info["database_error"] = str(e)
    
    return jsonify(debug_info)


@app.route('/calibre-status', methods=['GET', 'POST'])
def calibre_status():
    """
    Main endpoint for TRMNL integration.
    
    Accepts configuration from TRMNL form fields and returns book data
    in the format expected by TRMNL templates.
    
    Form Fields (from TRMNL):
    - book_limit: Number of books to display per section
    - show_descriptions: Whether to include book descriptions
    - show_page_counts: Whether to include page count data
    
    Returns:
        JSON with categorized book data for TRMNL display
    """
    try:
        # Extract configuration from TRMNL form fields
        book_limit = 10
        show_descriptions = True
        show_page_counts = True
        
        # Handle both POST (webhook) and GET (polling) requests
        if request.method == 'POST':
            data = request.get_json() or {}
            # TRMNL sends form field values in the request
            book_limit = int(data.get('book_limit', 10))
            show_descriptions = data.get('show_descriptions', True)
            show_page_counts = data.get('show_page_counts', True)
        else:
            # Query parameters for direct testing
            book_limit = int(request.args.get('book_limit', 10))
            show_descriptions = request.args.get('show_descriptions', 'true').lower() == 'true'
            show_page_counts = request.args.get('show_page_counts', 'true').lower() == 'true'
        
        # Validate book limit
        book_limit = max(1, min(book_limit, 50))  # Between 1 and 50
        
        # Check cache first
        cache_key = f"books:{book_limit}:{show_descriptions}:{show_page_counts}"
        if cache_key in cache:
            cache_time, cached_data = cache[cache_key]
            if datetime.now() - cache_time < timedelta(seconds=CACHE_DURATION):
                return jsonify(cached_data)
        
        # Get books from database
        books = get_books_from_calibre(book_limit * 3)  # Get extra for date filtering
        
        if not books:
            # Return sample data if no database found
            result = create_sample_data()
            result["empty_library"] = True
            result["message"] = "No Calibre library found. Check your database path and permissions."
            return jsonify(result)
        
        # Categorize books by addition date
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        
        this_week_books = []
        last_week_books = []
        earlier_books = []
        
        for i, book in enumerate(books, 1):
            book_id, title, authors, timestamp_str, rating, description, page_count_str = book
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('T', ' ').split('+')[0])
            except:
                timestamp = datetime.now() - timedelta(days=30)  # Default to older
            
            # Get tags for this book
            tags = get_book_tags(book_id)
            
            # Process page count
            page_count = None
            if show_page_counts and page_count_str:
                try:
                    page_count = int(page_count_str)
                except (ValueError, TypeError):
                    pass
            
            # Format rating as stars
            stars = "★" * rating if rating else ""
            
            # Clean description
            clean_description = ""
            if show_descriptions and description:
                clean_description = re.sub(r'<[^>]+>', '', description).strip()
                if len(clean_description) > 200:
                    clean_description = clean_description[:197] + "..."
            
            book_data = {
                "index": i,
                "title": title or "Unknown Title",
                "author": authors or "Unknown Author",
                "tags": tags,
                "rating": stars,
                "has_rating": bool(rating),
                "description": clean_description,
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
    # Production configuration for Railway/Render deployment
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    print(f"Starting TRMNL Calibre Library Plugin on port {port}")
    print(f"Calibre database path: {get_calibre_db_path()}")
    print(f"Database accessible: {os.path.exists(get_calibre_db_path())}")
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
