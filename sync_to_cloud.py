#!/usr/bin/env python3
"""
Calibre Library Sync Script for TRMNL

This script syncs your local Calibre library to your cloud service.
Update the configuration section below before running.
"""

import os
import sqlite3
import json
import requests
import time
from datetime import datetime

# ===== CONFIGURATION - UPDATE THESE VALUES =====
CLOUD_URL = "https://your-app.up.railway.app"  # Your Railway/Render URL
SYNC_TOKEN = "your-secure-token-here"          # Must match cloud service
CALIBRE_PATH = os.path.expanduser("~/Calibre Library")  # Your library path
# ===============================================


def find_calibre_database():
    """Find the Calibre database file."""
    db_path = os.path.join(CALIBRE_PATH, "metadata.db")
    if os.path.exists(db_path):
        print(f"✅ Found Calibre database at: {db_path}")
        return db_path
    
    print(f"❌ Database not found at: {db_path}")
    print(f"   Please update CALIBRE_PATH in this script")
    return None


def extract_books(limit=50):
    """Extract book data from Calibre database."""
    db_path = find_calibre_database()
    if not db_path:
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get recent books with basic metadata
        cursor.execute("""
            SELECT b.id, b.title, b.author_sort, b.timestamp
            FROM books b
            ORDER BY b.timestamp DESC
            LIMIT ?
        """, (limit,))
        
        books = []
        for row in cursor.fetchall():
            book_id, title, author, timestamp = row
            
            book_data = {
                'id': book_id,
                'title': title or f"Book {book_id}",
                'author': author or "Unknown",
                'timestamp': timestamp or "2020-01-01 00:00:00",
                'rating': 0,
                'tags': "",
                'page_count': None
            }
            
            # Get rating
            try:
                cursor.execute("""
                    SELECT r.rating FROM books_ratings_link brl 
                    JOIN ratings r ON brl.rating = r.id 
                    WHERE brl.book = ?
                """, (book_id,))
                result = cursor.fetchone()
                if result:
                    book_data['rating'] = (result[0] or 0) // 2
            except:
                pass
            
            # Get tags
            try:
                cursor.execute("""
                    SELECT GROUP_CONCAT(t.name, ', ') 
                    FROM books_tags_link btl
                    JOIN tags t ON btl.tag = t.id
                    WHERE btl.book = ?
                """, (book_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    book_data['tags'] = result[0]
            except:
                pass
            
            books.append(book_data)
        
        conn.close()
        print(f"✅ Extracted {len(books)} books from Calibre")
        return books
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        return []


def sync_to_cloud(books):
    """Send books to cloud service."""
    if not books:
        print("⚠️  No books to sync")
        return False
    
    headers = {
        "Authorization": f"Bearer {SYNC_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "books": books,
        "source": "local_calibre"
    }
    
    try:
        print(f"📤 Syncing {len(books)} books to cloud...")
        response = requests.post(
            f"{CLOUD_URL}/sync",
            json=data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Sync successful!")
            return True
        else:
            print(f"❌ Sync failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def main():
    """Main sync process."""
    print("\n📚 TRMNL Calibre Library Sync")
    print("=" * 40)
    
    # Check configuration
    if CLOUD_URL == "https://your-app.up.railway.app":
        print("❌ Please update CLOUD_URL in this script")
        return
    
    if SYNC_TOKEN == "your-secure-token-here":
        print("❌ Please update SYNC_TOKEN in this script")
        return
    
    # Extract and sync
    books = extract_books()
    if books:
        sync_to_cloud(books)
    
    print("\n✨ Done!")


if __name__ == "__main__":
    main()
