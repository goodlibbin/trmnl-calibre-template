"""
TRMNL Calibre Library Plugin - Cloud Service

A cloud-hosted service that syncs with your local Calibre library
and provides book data to TRMNL e-ink devices.

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
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration
SYNC_TOKEN = os.environ.get('SYNC_TOKEN', 'your-secret-sync-token-here')
BOOKS_FILE = 'books_data.json'
DEFAULT_BOOK_LIMIT = int(os.environ.get('DEFAULT_BOOK_LIMIT', 10))
MAX_BOOK_LIMIT = int(os.environ.get('MAX_BOOK_LIMIT', 50))

def load_books_data():
    """
    Load book data from persistent storage.
    
    Returns:
        dict: Book data with metadata or empty structure if no data exists
    """
    try:
        if os.path.exists(BOOKS_FILE):
            with open(BOOKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Loaded {data.get('total_books', 0)} books from storage")
                return data
    except Exception as e:
        print(f"⚠️  Error loading books data: {e}")
    
    # Return empty structure if no data available
    return {
        "books": [],
        "last_updated": None,
        "total_books": 0
    }

def save_books_data(data):
    """
    Save book data to persistent storage.
    
    Args:
        data (dict): Book data to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(BOOKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved {data.get('total_books', 0)} books to storage")
        return True
    except Exception as e:
        print(f"❌ Error saving books data: {e}")
        return False

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
    books_data = load_books_data()
    
    return jsonify({
        "name": "TRMNL Calibre Library Plugin",
        "version": "4.0.0",
        "description": "Cloud-hosted Calibre library service for TRMNL e-ink devices",
        "status": "✅ Service operational",
        "library_stats": {
            "total_books": books_data.get("total_books", 0),
            "last_updated": books_data.get("last_updated"),
            "data_source": "Cloud sync service"
        },
        "endpoints": {
            "/calibre-status": "Main data endpoint for TRMNL devices",
            "/sync": "Book data synchronization endpoint",
            "/health": "Service health monitoring",
            "/config": "Display configuration options"
        },
        "configuration": {
            "default_book_limit": DEFAULT_BOOK_LIMIT,
            "max_book_limit": MAX_BOOK_LIMIT
        }
    })

@app.route('/health')
def health():
    """
    Health check endpoint for monitoring service status.
    
    Returns:
        JSON response with health status and metrics
    """
    books_data = load_books_data()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": "operational",
        "library_status": {
            "total_books": books_data.get("total_books", 0),
            "last_sync": books_data.get("last_updated", "Never"),
            "data_available": len(books_data.get("books", [])) > 0
        },
        "service_info": {
            "version": "4.0.0",
            "environment": "cloud",
            "storage": "persistent"
        }
    }
    
    print(f"💚 Health check: {health_status['library_status']['total_books']} books available")
    return jsonify(health_status)

@app.route('/config')
def get_config():
    """
    Return available configuration options for display customization.
    
    Returns:
        JSON response with configuration options
    """
    return jsonify({
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
        "available_fields": [
            "title", "author", "tags", "rating", "description", 
            "page_count", "date_added", "days_ago"
        ],
        "features": {
            "random_suggestion": True,
            "rating_display": True,
            "tag_truncation": True,
            "overflow_handling": True
        }
    })

@app.route('/sync', methods=['POST'])
def sync_books():
    """
    Endpoint for synchronizing book data from local Calibre installations.
    Requires authentication via Bearer token.
    
    Returns:
        JSON response confirming sync status
    """
    # Verify authentication token
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {SYNC_TOKEN}":
        print("🔒 Unauthorized sync attempt blocked")
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Parse incoming book data
        sync_data = request.get_json()
        if not sync_data or 'books' not in sync_data:
            print("❌ Invalid sync data format received")
            return jsonify({"error": "Invalid data format - 'books' array required"}), 400

        # Prepare data for storage
        timestamp = datetime.now().isoformat()
        books_data = {
            "books": sync_data['books'],
            "last_updated": timestamp,
            "total_books": len(sync_data['books']),
            "sync_source": sync_data.get('source', 'local_calibre'),
            "sync_version": "4.0.0"
        }

        # Save to persistent storage
        if save_books_data(books_data):
            print(f"📚 Successfully synced {len(sync_data['books'])} books at {timestamp}")
            return jsonify({
                "message": "Library sync completed successfully",
                "books_synced": len(sync_data['books']),
                "timestamp": timestamp,
                "status": "success"
            })
        else:
            print("❌ Failed to save synced book data")
            return jsonify({"error": "Storage error during sync"}), 500

    except Exception as e:
        print(f"❌ Sync operation failed: {e}")
        return jsonify({"error": f"Sync failed: {str(e)}"}), 500

@app.route('/calibre-status', methods=['GET', 'POST'])
def calibre_status():
    """
    Main endpoint for TRMNL device integration.
    Returns formatted book data optimized for e-ink display.
    
    Supports both GET and POST requests with optional configuration parameters.
    
    Returns:
        JSON response with book data formatted for TRMNL templates
    """
    try:
        # Load current book data
        books_data = load_books_data()
        books = books_data.get('books', [])
        current_date = datetime.now().strftime("%m/%d")

        print(f"📊 TRMNL request: {len(books)} books available")

        # Handle empty library state
        if not books:
            print("📭 No books available - returning empty library state")
            return jsonify({
                "empty_library": True,
                "server_connected": True,
                "message": "Your Calibre library is ready for books! Sync from your local library to get started.",
                "recent_books": [],
                "book_suggestion": None,
                "library_stats": {
                    "total_books_found": 0,
                    "last_sync": books_data.get('last_updated', 'Never'),
                    "data_source": "Cloud service"
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
                "last_sync": books_data.get('last_updated'),
                "data_source": "Cloud service",
                "sync_version": books_data.get('sync_version', 'legacy')
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
            "server_connected": True,
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
    print(f"📚 Default book limit: {DEFAULT_BOOK_LIMIT}")
    print(f"🔧 Debug mode: {debug_mode}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
