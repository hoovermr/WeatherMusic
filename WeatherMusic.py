# -*- coding: utf-8 -*-
from flask import Flask, render_template, redirect, request, session
from random import shuffle
from timezonefinder import TimezoneFinder
from pytz import timezone
import os
import time
import spotipy
import spotipy.oauth2
import pyowm
# import json


# spotify web api authorization credentials
CLIENT_ID = '273c232d912349fe92db1ca0f268d60f'
CLIENT_SECRET = '4eac1ce5862541c99eb5638045bae2e2'

# test redirect
#CLIENT_SIDE_URL = "http://127.0.0.1"
#PORT = 5000
#REDIRECT_URI = "{}:{}/callback".format(CLIENT_SIDE_URL, PORT)

# production redirect
CLIENT_SIDE_URL = 'http://todaysoundslike.me'
REDIRECT_URI = 'http://todaysoundslike.me/callback'

# open weather map api creds
owm = pyowm.OWM('2afa8543802728d0be8e1337cf61cf87')  # hoovermr's default key
application = Flask(__name__)
application.secret_key = os.urandom(24)


@application.route('/')
@application.route('/index')
def index(err=None):
    # redirect user to Spotify login/auth.
    sp_oauth = get_oauth()
    return redirect(sp_oauth.get_authorize_url())


@application.route('/callback', methods=['GET', 'POST'])
def callback():
    # This is the route which the Spotify OAuth redirects to.
    # We finish getting an access token here.
    if request.args.get("code"):
        session['auth_token'] = request.args["code"]
        try:
            get_spotify(request.args["code"])
            err = None
        except KeyError:
            err = 'auth_err'

    return render_template("index.html", err=err)


@application.route('/gen_playlist', methods=['GET', 'POST'])
def gen_playlist():
    if request.form['location']:
        f_location = request.form['location']
    try:
        sp = get_spotify()
    except KeyError as e:
        print e
        return index(err='auth_err')

    w, obs, loc, err = get_weather(f_location)
    if err is not None:
        return render_template("index.html", err=err)

    naive_datetime_astz = get_loc_naive_datetime(obs)
    factor = w.get_temperature('fahrenheit')['temp'] / 100
    if factor > 1:
        factor = 0.95
    elif factor < 0:
        factor = 0.05
    day_night = 'night' if w.get_reference_time() > w.get_sunset_time() else 'day'
    items = get_weather_playlist(sp, factor, obs)

    track_ids = []
    for item in items:
        track_ids.append(item['track']['id'])
    session['track_ids'] = track_ids
    session['location'] = loc.get_name() + ', ' + loc.get_country()
    session['temp'] = w.get_temperature('fahrenheit')['temp']
    session['time'] = naive_datetime_astz.strftime('%I:%M %p')
    session['dn_code'] = day_night + '-' + str(w.get_weather_code())
    session['w_status'] = w.get_detailed_status()
    session.modified = True

    return render_template("gen_playlist.html",
                           w=w,
                           loc=loc,
                           day_night=day_night,
                           items=items,
                           datetime=naive_datetime_astz.strftime('%I:%M %p'))


@application.route('/make_playlist', methods=['GET', 'POST'])
def make_playlist():
    # create sp playlist for the user
    track_ids = session.pop('track_ids', None)
    location = session.pop('location', None)
    temp = session.pop('temp', None)
    w_time = session.pop('time', None)
    dn_code = session.pop('dn_code', None)
    w_status = session.pop('w_status', None)

    try:
        sp = get_spotify()
    except KeyError:
        return index(err='auth_err')
    user_id = sp.current_user()["id"]

    playlist_name = location + ' - ' + str("{0:.0f}".format(temp)) + unicode(' °F ', 'utf-8') + w_status.title()
    playlist = sp.user_playlist_create(user_id, playlist_name)
    sp.user_playlist_add_tracks(user_id, playlist['id'], track_ids)

    return render_template("make_playlist.html",
                           location=location,
                           temp=temp,
                           time=w_time,
                           dn_code=dn_code,
                           playlist_uri=playlist['uri'])


def get_loc_naive_datetime(obs):
    loc = obs.get_location()
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lng=loc.get_lon(), lat=loc.get_lat())
    tz = timezone(tz_name)
    naive_datetime = obs.get_reception_time(timeformat='date')
    return naive_datetime.astimezone(tz)


def get_saved_tracks(sp, obs):
    # get a user's saved tracks playlist
    result_list = []
    results = sp.current_user_saved_tracks(limit=50, offset=0)
    result_list.append(results)
    if results['total'] > 50:
        upper = round((results['total'] - 50) / 50)
        # max out at 300 tracks [50 tracks * 6 api calls]
        if upper > 5:
            upper = 5
        for x in range(1, int(upper) + 1):
            results = sp.current_user_saved_tracks(limit=50, offset=50*x)
            result_list.append(results)
    # get a 50/50 mix of featured and saved tracks
    naive_datetime_astz = get_loc_naive_datetime(obs)
    # limit of 4 ~200 tracks
    response = sp.featured_playlists(locale=obs.get_location().get_country(),
                                     limit=4, timestamp=naive_datetime_astz.isoformat())
    for x in range(0, len(response['playlists']['items'])):
        tracks = sp.user_playlist_tracks(user=response['playlists']['items'][x]['owner']['id'],
                                         playlist_id=response['playlists']['items'][x]['id'], limit=50)
        result_list.append(tracks)
    return result_list


def get_weather(f_loc):
    # get pyowm weather object
    try:
        obs = owm.weather_at_place(f_loc)
        w = obs.get_weather()
        loc = obs.get_location()
        err = None
        return w, obs, loc, err
    except pyowm.exceptions.not_found_error.NotFoundError as e:
        print e
        err = 'loc_err'
        return None, None, None, err
    except pyowm.exceptions.api_call_error.BadGatewayError as e:
        print e
        err = 'loc_err'
        return None, None, None, err


def get_weather_playlist(sp, factor, obs):
    # map weather and track info together
    result_list = get_saved_tracks(sp, obs)

    # unpack tracks from tracks response
    uris = []
    item_list = []
    for results in result_list:
        for item in results['items']:
            item_list.append(item)
            uris.append(item['track']['uri'])
    result_list[:] = []

    # print 'number of songs queried: ' + str(len(uris))
    feature_resp = []

    for group in chunker(uris, 50):
        feature_resp.append(sp.audio_features(group))

    # unpack tracks from features response
    all_features = []
    for features in feature_resp:
        for feature in features:
            all_features.append(feature)
    feature_resp[:] = []

    playlist = []
    for item, feature in zip(item_list, all_features):
        if feature is None:
            continue
        track = item['track']
        # using boundary of 0.05 as a test run
        if factor - 0.06 < feature['valence'] < factor + 0.06:
            playlist.append(item)
            # print track['name'] + ' - ' + track['artists'][0]['name'] + ' Valence: ' + str(feature['valence'])
    # print 'number of items after mapping: ' + str(len(playlist))

    shuffle(playlist)
    return playlist[:20]


def get_oauth():
    # return a Spotipy Oauth2 object.
    return spotipy.oauth2.SpotifyOAuth(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI,
                                       scope='user-library-read playlist-modify-public')


def get_spotify(auth_token=None):
    # TODO: find a better way to store tokens
    # return an authenticated Spotify object and store in session.
    token_info = {}
    if 'access_token' in session:
        token_info["access_token"] = session['access_token']
        token_info["expires_at"] = session['expires_at']
        token_info["refresh_token"] = session['refresh_token']
    else:
        token_info["access_token"], token_info["expires_at"], token_info["refresh_token"] = None, None, None

    oauth = get_oauth()
    if token_info["access_token"] is None:
        if auth_token is None:
            raise KeyError('no authentication token present')
        else:
            try:
                token_info = oauth.get_access_token(auth_token)
            except spotipy.oauth2.SpotifyOauthError as e:
                print e

    if token_info["expires_at"] is not None:
        if time.time() > token_info["expires_at"]:
            print 'refresh stale token ' + str(time.time()) + ' expired: ' + str(token_info["expires_at"])
            token_info = oauth.refresh_access_token(token_info["refresh_token"])

    if bool(token_info) is True:
        session['access_token'] = token_info["access_token"]
        session['expires_at'] = token_info["expires_at"]
        session['refresh_token'] = token_info["refresh_token"]
        session.modified = True
    return spotipy.Spotify(token_info["access_token"])


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in xrange(0, len(seq), size))


if __name__ == '__main__':
    application.run(debug=True)
