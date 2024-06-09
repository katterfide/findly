from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv("client_vars.env")

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for session management

# Configure Spotify API credentials
sp_oauth = SpotifyOAuth(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
    scope="playlist-modify-public user-library-read"
)

def get_audio_feature_criteria(request):
    criteria = {}
    for feature in ['danceability', 'energy', 'valence', 'acousticness', 'instrumentalness', 'speechiness', 'liveness']:
        if request.form.get(f'{feature}_toggle') == 'on':
            criteria[feature] = float(request.form.get(feature))
    return criteria

def get_top_tracks(sp):
    top_tracks = sp.current_user_top_tracks(limit=30)  # Get top 30 tracks
    genres = set()  # Use a set to store unique genres
    for track in top_tracks['items']:
        track_info = sp.track(track['id'])
        genres.update(track_info['artists'][0]['genres'])  # Extract genres from artists
    return top_tracks, genres

def get_recommendations(sp, genres, audio_features):
    recommendations = sp.recommendations(seed_genres=list(genres), limit=30, **audio_features)
    return recommendations['tracks']

def filter_recommendations(sp, recommendations, user_id):
    filtered_recommendations = []
    for track in recommendations:
        if not is_track_in_user_library(sp, user_id, track['id']):
            filtered_recommendations.append(track)
        if len(filtered_recommendations) >= 30:
            break
    return filtered_recommendations

def is_track_in_user_library(sp, user_id, track_id):
    saved_tracks = sp.current_user_saved_tracks()
    for item in saved_tracks['items']:
        if item['track']['id'] == track_id:
            return True
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    # Handle POST request
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()["id"]

    audio_features = get_audio_feature_criteria(request)
    top_tracks, genres = get_top_tracks(sp)
    recommendations = get_recommendations(sp, genres, audio_features)
    filtered_recommendations = filter_recommendations(sp, recommendations, user_id)

    playlist_name = "Generated Playlist"
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)

    # Check if playlist creation was successful
    if playlist:
        print("Playlist created successfully!")
        print("Playlist ID:", playlist['id'])
        print("Playlist Name:", playlist['name'])
    else:
        print("Failed to create playlist.")

    track_ids = [track['id'] for track in filtered_recommendations]
    sp.playlist_add_items(playlist['id'], track_ids)

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
    code = request.args.get('code')
    try:
        token_info = sp_oauth.get_access_token(code)
    except Exception as e:
        print(f"Error getting access token: {e}")
        return redirect(url_for('index'))
    session['token_info'] = token_info
    return redirect(url_for('playlist'))

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
