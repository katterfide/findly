from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for session management

# Configure Spotify API credentials
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="5b46a6cf5c894c4f818acd7b8f897cf3",
                                               client_secret="0b6f704b5c8b4b3db89d135e910be52f",
                                               redirect_uri="http://127.0.0.1:5000/callback",
                                               scope="playlist-modify-public"))


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    print("Form submitted")
    mood = request.form.get('mood')
    print(f"Received mood: {mood}")

    if not mood:
        return jsonify({"error": "Mood is required"}), 400

    playlist_name = f"{mood.capitalize()} Playlist"
    user_id = sp.current_user()["id"]
    print(f"User ID: {user_id}")

    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    print(f"Created playlist: {playlist['id']}")

    # Placeholder logic for adding tracks (replace with actual logic)
    track_ids = ['1KUjwNaO5logIbpSnDe80h', '1KUjwNaO5logIbpSnDe80h']
    sp.playlist_add_items(playlist['id'], track_ids)
    print(f"Added tracks to playlist: {track_ids}")

    return redirect(url_for('playlist', playlist_id=playlist['id'], playlist_name=playlist_name))

@app.route('/playlist')
def playlist():
    playlist_id = request.args.get('playlist_id')
    playlist_name = request.args.get('playlist_name')
    return render_template('playlist.html', playlist_id=playlist_id, playlist_name=playlist_name)

@app.route('/callback')
def callback():
    print("Callback reached")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
