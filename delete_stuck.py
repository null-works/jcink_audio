import sqlite3

def clean_up():
    conn = sqlite3.connect('/opt/jcink_audio/data/cache.db')
    conn.row_factory = sqlite3.Row
    
    # Let's clean up both playlists in case there are any
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracks WHERE playlist_id = 'PLnfCKRnC86UN5_jVdWnRhfuNNu7X1FyRU'")
    cursor.execute("DELETE FROM playlists WHERE id = 'PLnfCKRnC86UN5_jVdWnRhfuNNu7X1FyRU'")
    conn.commit()
    
    print(f"Direct delete successful. Deleted tracks & playlist.")
    conn.close()

if __name__ == '__main__':
    clean_up()
