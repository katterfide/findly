from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for session management


# Configure Spotify API credentials
sp_oauth = SpotifyOAuth(client_id="5b46a6cf5c894c4f818acd7b8f897cf3",
                                               client_secret="0b6f704b5c8b4b3db89d135e910be52f",
                                               redirect_uri="http://127.0.0.1:5000/callback",
                                               scope="playlist-modify-public")
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_playlist', methods=['GET', 'POST'])
def generate_playlist():
    if request.method == 'POST':
        mood = request.form.get('mood')
        print("Form submitted")
        print(f"Received mood: {mood}")

        if not mood:
            return jsonify({"error": "Mood is required"}), 400

        token_info = get_token()
        if not token_info:
            session['mood'] = mood  # Store the mood in the session before redirecting to login
            return redirect(url_for('login'))

        return create_playlist(mood, token_info)

    if request.method == 'GET':
        mood = session.pop('mood', None)
        token_info = get_token()
        if not token_info or not mood:
            return redirect(url_for('index'))  # Redirect to index if there's no mood or token

        return create_playlist(mood, token_info)

def create_playlist(mood, token_info):
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()["id"]
    print(f"User ID: {user_id}")

    playlist_name = f"{mood.capitalize()} Playlist"
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    print(f"Created playlist: {playlist['id']}")

    track_ids = ['1KUjwNaO5logIbpSnDe80h', '1KUjwNaO5logIbpSnDe80h']
    sp.playlist_add_items(playlist['id'], track_ids)
    print(f"Added tracks to playlist: {track_ids}")

    return redirect(url_for('playlist', playlist_id=playlist['id'], playlist_name=playlist_name))

@app.route('/playlist')
def playlist():
    playlist_id = request.args.get('playlist_id')
    playlist_name = request.args.get('playlist_name')
    return render_template('playlist.html', playlist_id=playlist_id, playlist_name=playlist_name)

@app.route('/login', methods=['GET'])
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    print("Callback reached")
    code = request.args.get('code')
    try:
        token_info = sp_oauth.get_access_token(code)
    except Exception as e:
        print(f"Error getting access token: {e}")
        return redirect(url_for('index'))
    session['token_info'] = token_info
    session['mood'] = session.pop('mood', None)  # Retrieve the mood stored before redirection
    return redirect(url_for('generate_playlist'))

def get_token():
    token_info = session.get('token_info', None)
    if not token_info:
        return None

    now = int(time.time())
    is_token_expired = token_info['expires_at'] - now < 60

    if is_token_expired:
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info

if __name__ == '__main__':
    app.run(debug=True, port=5000)