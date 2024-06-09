from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
from dotenv import load_dotenv
import pylast

# Load environment variables from .env file
load_dotenv("client_vars.env")

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for session management

# Configure Spotify API credentials
sp_oauth = SpotifyOAuth(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
    scope="playlist-modify-public user-library-read user-top-read"
)

# Initialize Last.fm API
lastfm_network = pylast.LastFMNetwork(
    api_key=os.getenv('LASTFM_API_KEY'),
    api_secret=os.getenv('LASTFM_API_SECRET')
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    if request.form['input_type'] == 'song':
        spotify_link = request.form['spotify_link']
        playlist = get_playlist_from_song(spotify_link)
    elif request.form['input_type'] == 'top_tracks':
        playlist = get_playlist_from_top_tracks()

    playlist_id = "your_playlist_id"  # Replace "your_playlist_id" with the actual playlist ID
    playlist_name = "Your Playlist Name"  # Replace "Your Playlist Name" with the actual playlist name

    return render_template('playlist.html', playlist_name=playlist_name, playlist_id=playlist_id)

def get_playlist_from_song(spotify_link):
    track = get_track_details_from_spotify(spotify_link)
    artist = track['artists'][0]['name']
    similar_tracks = lastfm_network.get_artist(artist).get_similar()
    playlist = [similar_track.item.title for similar_track in similar_tracks]
    return playlist

def get_playlist_from_top_tracks():
    top_tracks = get_user_top_tracks_from_spotify()
    playlist = []
    for item in top_tracks['items']:
        if 'track' in item:
            track = item['track']
            artist = track['artists'][0]['name']
            similar_tracks = lastfm_network.get_artist(artist).get_similar()
            playlist.extend([similar_track.item.title for similar_track in similar_tracks])
    return playlist



def get_track_details_from_spotify(spotify_link):
    # Initialize Spotipy with OAuth
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    # Get track details from Spotify
    track = sp.track(spotify_link)
    return track

def get_user_top_tracks_from_spotify():
    # Initialize Spotipy with OAuth
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    # Get user's top tracks from Spotify
    top_tracks = sp.current_user_top_tracks()
    return top_tracks

if __name__ == '__main__':
    app.run(debug=True)