from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
from dotenv import load_dotenv
import pylast
import asyncio

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
async def generate_playlist():
    playlist_name = request.form['playlist_name']  # Get the playlist name from the form

    if request.form['input_type'] == 'song':
        spotify_link = request.form['spotify_link']
        playlist, playlist_name, playlist_id = await get_playlist_from_song(spotify_link)
    elif request.form['input_type'] == 'top_tracks':
        playlist, playlist_name, playlist_id = await get_playlist_from_top_tracks()

    return render_template('playlist.html', playlist_name=playlist_name, playlist_id=playlist_id)

async def get_playlist_from_song(spotify_link):
    track = get_track_details_from_spotify(spotify_link)
    artist = track['artists'][0]['name']
    similar_tracks = lastfm_network.get_artist(artist).get_similar()
    playlist = [similar_track.item.title for similar_track in similar_tracks]

    return playlist, playlist_name, playlist_id

async def get_playlist_from_top_tracks():
    top_tracks = get_user_top_tracks_from_spotify()
    playlist = []
    tasks = []
    for track in top_tracks:
        artist_name = track['artists'][0]['name']
        track_name = track['name']
        print(f"Fetching similar tracks for: {track_name} by {artist_name}")
        tasks.append(get_similar_tracks_async(artist_name, track_name))

    similar_tracks_lists = await asyncio.gather(*tasks)

    print("Similar tracks lists: ", similar_tracks_lists)

    for similar_tracks in similar_tracks_lists:
        if similar_tracks:  # Ensure the list is not empty
            playlist.append(similar_tracks[0].item.title)  # Add only the top similar track

    playlist_name = request.form['playlist_name']

    # Create playlist on Spotify
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    user_id = sp.current_user()['id']
    playlist_description = "Playlist generated from your top tracks"
    playlist_response = sp.user_playlist_create(user=user_id, name=playlist_name, public=True, description=playlist_description)
    playlist_id = playlist_response['id']

    return playlist, playlist_name, playlist_id

async def get_similar_tracks_async(artist_name, track_name):
    similar_tracks = await asyncio.get_event_loop().run_in_executor(None, lambda: lastfm_network.get_track(artist_name, track_name).get_similar())
    print(f"Similar tracks for {track_name} by {artist_name}: {similar_tracks}")
    return similar_tracks

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
    return top_tracks['items']  # Ensure we're returning the 'items' list

if __name__ == '__main__':
    app.run(debug=True)