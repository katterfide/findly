from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
import pylast
from flask_socketio import SocketIO
import logging

# Load environment variables from .env file
load_dotenv("client_vars.env")

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for session management
socketio = SocketIO(app)

sp_oauth = SpotifyOAuth(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
    scope="playlist-modify-public user-library-read user-top-read"
)

lastfm_network = pylast.LastFMNetwork(
    api_key=os.getenv('LASTFM_API_KEY'),
    api_secret=os.getenv('LASTFM_API_SECRET')
)

# Configure logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    session['messages'] = session.get('messages', [])
    return render_template('index.html', messages=session['messages'])

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    playlist_name = request.form['playlist_name']
    include_library_tracks = 'include_library_tracks' in request.form

    if request.form['input_type'] == 'song':
        spotify_link = request.form['spotify_link']
        num_tracks = int(request.form['num_tracks'])
        add_message(f"Generating playlist from song: {spotify_link}")
        playlist_id = get_playlist_from_song(spotify_link, num_tracks, include_library_tracks)
    elif request.form['input_type'] == 'top_tracks':
        recommendations_per_song = int(request.form['recommendations_per_song'])
        add_message("Generating playlist from top tracks")
        playlist_id = get_playlist_from_top_tracks(recommendations_per_song, include_library_tracks)

    # Redirect to the final page after playlist generation
    return redirect(url_for('playlist', playlist_name=playlist_name, playlist_id=playlist_id))

def get_playlist_from_song(spotify_link, num_tracks, include_library_tracks):
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    track = get_track_details_from_spotify(spotify_link)
    artist_name = track['artists'][0]['name']
    track_name = track['name']
    add_message(f"Fetching similar tracks for: {track_name} by {artist_name}")

    similar_tracks = get_similar_tracks_sync(artist_name, track_name)

    if not similar_tracks:
        add_message(f"No similar tracks found on Last.fm for {track_name} by {artist_name}. Falling back to Spotify recommendations.")
        results = sp.recommendations(seed_tracks=[track['id']], limit=num_tracks)
        similar_tracks = [{'name': rec['name'], 'artist': rec['artists'][0]['name']} for rec in results['tracks']]
    else:
        similar_tracks = [{'title': track.item.title, 'artist': track.item.artist, 'match': track.match} for track in similar_tracks]

    sorted_similar_tracks = sorted(similar_tracks, key=lambda x: x.get('match', 0), reverse=True)

    user_id = sp.current_user()['id']
    playlist_name = request.form['playlist_name']
    playlist_description = f"Playlist generated from the song: {track_name}"
    playlist_response = sp.user_playlist_create(user=user_id, name=playlist_name, public=True, description=playlist_description)
    playlist_id = playlist_response['id']

    playlist = []
    added_tracks = 0
    for similar_track in sorted_similar_tracks:
        if added_tracks >= num_tracks:
            break
        similar_track_name = similar_track['title'] if 'title' in similar_track else similar_track['name']
        similar_artist_name = similar_track['artist']
        results = sp.search(q=f"track:{similar_track_name} artist:{similar_artist_name}", type='track')
        if results['tracks']['items']:
            track_uri = results['tracks']['items'][0]['uri']
            if include_library_tracks or not is_track_in_user_playlists(sp, track_uri):
                add_message(f"Adding track {similar_track_name} by {similar_artist_name} to playlist.")
                sp.playlist_add_items(playlist_id, [track_uri])
                playlist.append(similar_track_name)
                added_tracks += 1
            else:
                add_message(f"Track {similar_track_name} by {similar_artist_name} is already in user's library or playlists. Skipping.")

    return playlist_id

def get_similar_tracks_sync(artist_name, track_name):
    try:
        similar_tracks = lastfm_network.get_track(artist_name, track_name).get_similar()
        if similar_tracks:
            return similar_tracks
        else:
            add_message(f"No similar tracks found for {track_name} by {artist_name} on Last.fm. Trying Spotify recommendations.")
            return None
    except Exception as e:
        add_message(f"Error fetching similar tracks for {track_name} by {artist_name}: {e}")
        return None

def get_track_details_from_spotify(spotify_link):
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    track = sp.track(spotify_link)
    return track

def is_track_in_user_playlists(sp, track_uri):
    user_playlists = sp.current_user_playlists()
    for playlist in user_playlists['items']:
        playlist_tracks = sp.playlist_tracks(playlist['id'])
        for item in playlist_tracks['items']:
            if item is not None and 'track' in item and item['track'] is not None and 'uri' in item['track'] and item['track']['uri'] == track_uri:
                add_message(f"Track {track_uri} found in playlist {playlist['name']}.")
                return True
    add_message(f"Track {track_uri} not found in any user playlists.")
    return False

def add_message(message):
    if 'messages' not in session:
        session['messages'] = []
    session['messages'].append(message)
    session.modified = True
    logging.info(f"Added message: {message}")  # Use logging instead of print
    socketio.emit('new_message', {'message': message})

@app.route('/get_messages')
def get_messages():
    messages = session.get('messages', [])
    logging.info(f"Returning messages: {messages}")  # Use logging instead of print
    return {'messages': messages}

@app.route('/playlist')
def playlist():
    playlist_name = request.args.get('playlist_name')
    playlist_id = request.args.get('playlist_id')
    return render_template('playlist.html', playlist_name=playlist_name, playlist_id=playlist_id)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
