# -*- coding: utf-8 -*-
from flask import Flask, render_template, redirect, request, session
import time
import spotipy
import spotipy.oauth2
import pyowm
from random import shuffle

# spotipy authorization creds
client_id = '273c232d912349fe92db1ca0f268d60f'
client_secret = '4eac1ce5862541c99eb5638045bae2e2'

# Flask Parameters
CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 5000
REDIRECT_URI = "{}:{}/callback".format(CLIENT_SIDE_URL, PORT)

# open weather map api creds
owm = pyowm.OWM('2afa8543802728d0be8e1337cf61cf87')  # hoovermr's default key
app = Flask(__name__)


@app.route('/')
@app.route('/index')
def index():
    """Redirect user to Spotify login/auth."""
    sp_oauth = get_oauth()
    return redirect(sp_oauth.get_authorize_url())


@app.route('/callback', methods=['GET', 'POST'])
def callback():
    # This is the route which the Spotify OAuth redirects to.
    # We finish getting an access token here.
    if request.args.get("code"):
        sp = get_spotify(request.args["code"])

    return render_template("index.html")


@app.route('/gen_playlist', methods=['GET', 'POST'])
def gen_playlist():
    if request.form['location']:
        location = request.form['location']

    sp = get_spotify()

    w, obs = get_weather(location)
    factor = w.get_temperature('fahrenheit')['temp'] / 100
    day_night = 'night' if w.get_reference_time() > w.get_sunset_time() else 'day'

    # match up the valence with the temperature
    items = get_weather_playlist(sp, factor)

    track_ids = []
    for item in items:
        track_ids.append(item['track']['id'])
    session['track_ids'] = track_ids
    session['location'] = location
    session['temp'] = w.get_temperature('fahrenheit')['temp']
    session['time'] = obs.get_reception_time(timeformat='iso')
    session['status'] = w.get_status()
    session['dn_code'] = day_night + '-' + str(w.get_weather_code())
    session.modified = True

    return render_template("gen_playlist.html",
                           w=w,
                           obs=obs,
                           day_night=day_night,
                           items=items)


@app.route('/make_playlist', methods=['GET', 'POST'])
def make_playlist():
    track_ids = session.pop('track_ids', None)
    location = session.pop('location', None)
    temp = session.pop('temp', None)
    w_time = session.pop('time', None)
    w_status = session.pop('status', None)
    dn_code = session.pop('dn_code', None)

    sp = get_spotify()
    user_id = sp.current_user()["id"]

    playlist_name = str("{0:.0f}".format(temp)) + unicode(' °F ', 'utf-8') + location + ' ' + time.strftime("%d/%m/%Y")
    playlist = sp.user_playlist_create(user_id, playlist_name)
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return render_template("make_playlist.html",
                           location=location,
                           temp=temp,
                           time=w_time,
                           status=w_status,
                           dn_code=dn_code,
                           playlist_uri=playlist['uri'])


def get_saved_tracks(sp):
    """get a user's saved tracks playlist"""
    # each loop is 50 tracks
    result_list = []
    for x in range(0, 4):
        results = sp.current_user_saved_tracks(limit=50, offset=50*x)
        result_list.append(results)
    return result_list


def get_weather(location):
    """get weather details like temperature"""
    observation = owm.weather_at_place(location)
    w = observation.get_weather()
    return w, observation


def get_weather_playlist(sp, factor):
    # get last X saved tracks
    result_list = get_saved_tracks(sp)

    uris = []
    for results in result_list:
        for item in results['items']:
            uris.append(item['track']['uri'])

    feature_list = []
    for group in chunker(uris, 50):
        feature_list.append(sp.audio_features(group))

    items = []
    # result_list and feature_list are both lists of lists
    for results, features in zip(result_list, feature_list):
        # results['items'] and features are both 50 entries long
        for item, feature in zip(results['items'], features):
            track = item['track']
            # using boundary of 0.1 as a test run
            if factor - 0.1 < feature['valence'] < factor + 0.1:
                items.append(item)
                print track['name'] + ' - ' + track['artists'][0]['name'] + ' Valence: ' + str(feature['valence'])
    shuffle(items)
    return items[:20]


def get_oauth():
    """Return a Spotipy Oauth2 object."""
    return spotipy.oauth2.SpotifyOAuth(
        client_id, client_secret, REDIRECT_URI,
        scope='user-library-read playlist-modify-public', cache_path=".tokens")


def get_spotify(auth_token=None):
    """Return an authenticated Spotify object."""
    oauth = get_oauth()
    token_info = oauth.get_cached_token()
    if not token_info and auth_token:
        token_info = oauth.get_access_token(auth_token)
    return spotipy.Spotify(token_info["access_token"])


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in xrange(0, len(seq), size))


if __name__ == '__main__':
    # set the secret key.  keep this really secret:
    app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
    app.run(debug=True)
