from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
from dotenv import load_dotenv
import pylast
import asyncio
import random  # Import random module

# Load environment variables from .env file
load_dotenv("client_vars.env")

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for session management

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_playlist', methods=['POST'])
async def generate_playlist():
    playlist_name = request.form['playlist_name']  # Get the playlist name from the form

    if request.form['input_type'] == 'song':
        spotify_link = request.form['spotify_link']
        num_tracks = int(request.form['num_tracks'])  # Get the number of tracks for the playlist
        playlist, playlist_name, playlist_id = await get_playlist_from_song(spotify_link, num_tracks)
    elif request.form['input_type'] == 'top_tracks':
        recommendations_per_song = int(request.form['recommendations_per_song'])  # Get the number of recommendations per song
        playlist, playlist_name, playlist_id = await get_playlist_from_top_tracks(recommendations_per_song)

    return render_template('playlist.html', playlist_name=playlist_name, playlist_id=playlist_id)

async def get_playlist_from_song(spotify_link, num_tracks):
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    track = get_track_details_from_spotify(spotify_link)
    artist_name = track['artists'][0]['name']
    track_name = track['name']
    print(f"Fetching similar tracks for: {track_name} by {artist_name}")

    similar_tracks = await get_similar_tracks_async(artist_name, track_name)

    if not similar_tracks:
        # Fallback to Spotify's recommendation if Last.fm has no similar tracks
        results = sp.recommendations(seed_tracks=[track['id']], limit=num_tracks)
        similar_tracks = [{'item': {'title': rec['name'], 'artist': rec['artists'][0]['name']}} for rec in results['tracks']]

    sorted_similar_tracks = sorted(similar_tracks, key=lambda x: x.match if hasattr(x, 'match') else 0, reverse=True)

    # Create playlist on Spotify
    user_id = sp.current_user()['id']
    playlist_name = request.form['playlist_name']
    playlist_description = f"Playlist generated from the song: {track_name}"
    playlist_response = sp.user_playlist_create(user=user_id, name=playlist_name, public=True, description=playlist_description)
    playlist_id = playlist_response['id']

    playlist = []
    for similar_track in sorted_similar_tracks[:num_tracks]:
        similar_track_name = similar_track.item.title
        similar_artist_name = similar_track.item.artist
        if hasattr(similar_track, 'match'):
            similarity_score = round(similar_track.match, 2)
            print(f"Most similar track for {track_name} by {artist_name}: {similar_track_name} by {similar_artist_name} with similarity score: {similarity_score}")
        else:
            print(f"Most similar track for {track_name} by {artist_name}: {similar_track_name} by {similar_artist_name}")

        results = sp.search(q=f"track:{similar_track_name} artist:{similar_artist_name}", type='track')
        if results['tracks']['items']:
            track_uri = results['tracks']['items'][0]['uri']
            sp.playlist_add_items(playlist_id, [track_uri])
            playlist.append(similar_track_name)

    return playlist, playlist_name, playlist_id

async def get_playlist_from_top_tracks(recommendations_per_song):
    top_tracks = get_user_top_tracks_from_spotify()
    playlist = []
    tasks = []
    sp = spotipy.Spotify(auth_manager=sp_oauth)

    # Create playlist on Spotify
    user_id = sp.current_user()['id']
    playlist_name = request.form['playlist_name']
    playlist_description = "Playlist generated from your top tracks"
    playlist_response = sp.user_playlist_create(user=user_id, name=playlist_name, public=True, description=playlist_description)
    playlist_id = playlist_response['id']

    for track in top_tracks:
        artist_name = track['artists'][0]['name']
        track_name = track['name']
        print(f"Fetching similar tracks for: {track_name} by {artist_name}")
        tasks.append(get_similar_tracks_async(artist_name, track_name))

    similar_tracks_lists = await asyncio.gather(*tasks)

    for i, similar_tracks in enumerate(similar_tracks_lists):
        if similar_tracks:
            sorted_similar_tracks = sorted(similar_tracks, key=lambda x: x.match if hasattr(x, 'match') else 0, reverse=True)
            for similar_track in sorted_similar_tracks[:recommendations_per_song]:
                print(f"Most similar track for {top_tracks[i]['name']} by {top_tracks[i]['artists'][0]['name']}: {similar_track.item.title} by {similar_track.item.artist}")
                playlist.extend([similar_track.item.title, " ", similar_track.item.artist])  # Add the most similar track to the playlist

                # Search for the most similar track on Spotify
                results = sp.search(q=f"track:{similar_track.item.title} artist:{top_tracks[i]['artists'][0]['name']}", type='track')
                if results['tracks']['items']:
                    track_uri = results['tracks']['items'][0]['uri']  # Get the URI of the first search result
                    sp.playlist_add_items(playlist_id, [track_uri])  # Add the track to the playlist

    return playlist, playlist_name, playlist_id

async def get_similar_tracks_async(artist_name, track_name):
    try:
        similar_tracks = await asyncio.get_event_loop().run_in_executor(None, lambda: lastfm_network.get_track(artist_name, track_name).get_similar())
        if similar_tracks:
            return similar_tracks
        else:
            print(f"No similar tracks found for {track_name} by {artist_name} on Last.fm. Trying Spotify recommendations.")
            return None
    except Exception as e:
        print(f"Error fetching similar tracks for {track_name} by {artist_name}: {e}")
        return None

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