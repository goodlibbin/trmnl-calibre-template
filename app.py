#!/usr/bin/env python3
"""
TRMNL Calibre-web Plugin
Display your Calibre library status on TRMNL e-ink devices
"""

from flask import Flask, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import random
import os

app = Flask(__name__)

# USER CONFIGURATION - UPDATE THESE VALUES WITH YOUR OWN
# =======================================================
# Your Calibre-web server URL (update with your actual server)
CALIBRE_BASE_URL = "http://your-calibre-server.com:8080"  # Update this
# Your library ID (usually "Calibre_Library")  
LIBRARY_ID = "Calibre_Library"
# =======================================================

# Cache to avoid hitting server too frequently
CACHE = {
    'books': None,
    'books_timestamp': None,
    'cache_duration': 300  # 5 minutes
}

def is_cache_valid():
    """Check if cached data is still valid"""
    if CACHE['books_timestamp'] is None:
        return False
    
    time_diff = (datetime.now() - CACHE['books_timestamp']).total_seconds()
    return time_diff < CACHE['cache_duration']

def get_newest_books():
    """Get newest books from Calibre-web with caching"""
    
    # Return cached data if valid
    if is_cache_valid() and CACHE['books']:
        return CACHE['books']
    
    try:
        url = f"{CALIBRE_BASE_URL}/opds/navcatalog/4f6e6577657374?library_id={LIBRARY_ID}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse the XML feed
        root = ET.fromstring(response.content)
        books = []
        
        # Extract book information
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = entry.find('.//{http://www.w3.org/2005/Atom}title')
            author_elem = entry.find('.//{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')
            content_elem = entry.find('.//{http://www.w3.org/2005/Atom}content')
            published_elem = entry.find('.//{http://www.w3.org/2005/Atom}published')
            
            if title_elem is not None and title_elem.text:
                book_info = {
                    'title': title_elem.text,
                    'author': author_elem.text if author_elem is not None else 'Unknown Author',
                    'published': published_elem.text if published_elem is not None else '',
                }
                
                # Extract rating and tags from content if available
                if content_elem is not None and content_elem.text:
                    content = content_elem.text
                    
                    # Extract rating
                    if 'RATING:' in content:
                        rating_start = content.find('RATING:') + 8
                        rating_end = content.find('<br/>', rating_start)
                        if rating_end > rating_start:
                            book_info['rating'] = content[rating_start:rating_end].strip()
                    
                    # Extract tags
                    if 'TAGS:' in content:
                        tags_start = content.find('TAGS:') + 6
                        tags_end = content.find('<br/>', tags_start)
                        if tags_end > tags_start:
                            tags = content[tags_start:tags_end].strip()
                            book_info['tags'] = tags.split(', ')[:3]  # First 3 tags
                
                books.append(book_info)
                
        # Cache the results
        CACHE['books'] = books[:10]  # Keep top 10
        CACHE['books_timestamp'] = datetime.now()
        
        return CACHE['books']
        
    except Exception as e:
        print(f"Error getting books: {e}")
        # Return cached data if available, even if expired
        return CACHE['books'] if CACHE['books'] else []

def get_library_stats():
    """Get library statistics"""
    books = get_newest_books()
    
    if not books:
        return None
    
    rated_books = len([book for book in books if book.get('rating')])
    total_books = len(books)
    
    # Get the most recent book
    latest_book = books[0] if books else None
    
    return {
        'total_recent_books': total_books,
        'rated_books': rated_books,
        'latest_book': latest_book,
        'server_status': 'Connected',
        'last_update': datetime.now().strftime('%m/%d %H:%M')
    }

@app.route('/trmnl-data')
def trmnl_data():
    """Main TRMNL data endpoint - returns JSON for template system"""
    
    try:
        books = get_newest_books()
        stats = get_library_stats()
        
        if not books or not stats:
            return jsonify({
                'error': 'Unable to fetch library data',
                'title': 'Library Offline',
                'status': 'error',
                'current_time': datetime.now().strftime('%m/%d %H:%M')
            })
        
        latest_book = stats['latest_book']
        
        # Format the response for TRMNL templates
        response_data = {
            'title': latest_book['title'][:40] + ('...' if len(latest_book['title']) > 40 else ''),
            'author': latest_book['author'],
            'rating': latest_book.get('rating', 'Not rated'),
            'tags': ', '.join(latest_book.get('tags', [])[:2]) if latest_book.get('tags') else 'No tags',
            'total_books': stats['total_recent_books'],
            'rated_books': stats['rated_books'],
            'rating_percentage': round((stats['rated_books'] / stats['total_recent_books']) * 100) if stats['total_recent_books'] > 0 else 0,
            'server_status': stats['server_status'],
            'last_update': stats['last_update'],
            'current_time': datetime.now().strftime('%m/%d %H:%M')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'title': 'Error',
            'status': 'error',
            'current_time': datetime.now().strftime('%m/%d %H:%M')
        }), 500

@app.route('/api/recent')
def api_recent():
    """Legacy endpoint for backwards compatibility"""
    books = get_newest_books()
    
    if not books:
        return jsonify({
            'success': False,
            'error': 'Could not fetch books from Calibre-web'
        })
    
    content = []
    content.append("📚 Recently Added Books")
    content.append("")
    
    # Show top 5 recent books
    for i, book in enumerate(books[:5], 1):
        title = book['title']
        if len(title) > 35:
            title = title[:32] + "..."
        
        author = book['author']
        if len(author) > 25:
            author = author[:22] + "..."
            
        rating = book.get('rating', '')
        rating_display = f" {rating}" if rating else ""
        
        content.append(f"{i}. {title}")
        content.append(f"   by {author}{rating_display}")
        if i < 5:
            content.append("")
    
    return jsonify({
        'success': True,
        'data': {
            'title': 'Recent Additions',
            'content': content
        }
    })

@app.route('/debug')
def debug():
    """Debug endpoint to see raw data"""
    books = get_newest_books()
    stats = get_library_stats()
    
    return jsonify({
        'books_count': len(books) if books else 0,
        'latest_books': books[:3] if books else [],
        'stats': stats,
        'cache_status': {
            'is_valid': is_cache_valid(),
            'timestamp': CACHE['books_timestamp'].isoformat() if CACHE['books_timestamp'] else None
        },
        'config': {
            'calibre_url': CALIBRE_BASE_URL,
            'library_id': LIBRARY_ID
        }
    })

@app.route('/clear-cache')
def clear_cache():
    """Clear cache to force fresh data"""
    CACHE['books'] = None
    CACHE['books_timestamp'] = None
    return jsonify({'status': 'Cache cleared'})

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        books = get_newest_books()
        is_healthy = len(books) > 0 if books else False
        
        return jsonify({
            'status': 'healthy' if is_healthy else 'unhealthy',
            'calibre_url': CALIBRE_BASE_URL,
            'library_id': LIBRARY_ID,
            'books_found': len(books) if books else 0,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/')
def index():
    """Index page with setup instructions"""
    return """
    <h1>TRMNL Calibre Plugin</h1>
    <p>Your Calibre-web TRMNL plugin is running!</p>
    
    <h2>Endpoints:</h2>
    <ul>
        <li><a href="/trmnl-data">/trmnl-data</a> - Main TRMNL template data</li>
        <li><a href="/debug">/debug</a> - Debug information</li>
        <li><a href="/health">/health</a> - Health check</li>
        <li><a href="/clear-cache">/clear-cache</a> - Clear cache</li>
    </ul>
    
    <h2>Configuration:</h2>
    <p>Update the CALIBRE_BASE_URL and LIBRARY_ID in app.py</p>
    <p>Current Calibre URL: <code>{}</code></p>
    <p>Current Library ID: <code>{}</code></p>
    """.format(CALIBRE_BASE_URL, LIBRARY_ID)

if __name__ == '__main__':
    # Get port from environment variable for deployment compatibility
    port = int(os.environ.get('PORT', 5001))
    
    print("🚀 Starting TRMNL Calibre Plugin...")
    print(f"📚 Calibre-web URL: {CALIBRE_BASE_URL}")
    print(f"📖 Library: {LIBRARY_ID}")
    print(f"🌐 Server starting on port {port}")
    
    # Test connection on startup
    print("🔍 Testing connection...")
    test_books = get_newest_books()
    if test_books:
        print(f"✅ Success! Found {len(test_books)} recent books")
        print(f"📖 Latest: {test_books[0]['title']}")
    else:
        print("❌ Could not connect to Calibre-web")
    
    app.run(host='0.0.0.0', port=port, debug=False)
