from flask import Flask, render_template, redirect, request
import spotipy
import spotipy.oauth2
import pyowm

# spotipy authorization creds
client_id = '273c232d912349fe92db1ca0f268d60f'
client_secret = '4eac1ce5862541c99eb5638045bae2e2'

# Flask Parameters
CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 5000
REDIRECT_URI = "{}:{}/callback".format(CLIENT_SIDE_URL, PORT)

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

    get_saved_tracks(sp)
    get_weather()

    # match up the variance with the temperature
    # render the recommendation results
    return render_template("index.html")


def get_saved_tracks(sp):
    """get a user's saved tracks playlist"""
    if sp:
        results = sp.current_user_saved_tracks()
        for item in results['items']:
            track = item['track']
            feature = sp.audio_features([track['uri']])
            print track['name'] + ' - ' + track['artists'][0]['name'] + ' Valence: ' + str(feature[0]['valence'])
    else:
        print "Can't get token"


def get_weather():
    """get weather details like temperature"""
    observation = owm.weather_at_place('London,uk') #start with london as default
    w = observation.get_weather()
    temp = w.get_temperature('fahrenheit')  # {'temp_max': 10.5, 'temp': 9.7, 'temp_min': 9.0}

    print(temp['temp'])
    print(w)


def get_oauth():
    """Return a Spotipy Oauth2 object."""
    return spotipy.oauth2.SpotifyOAuth(
        client_id, client_secret, REDIRECT_URI,
        scope='user-library-read', cache_path=".tokens")


def get_spotify(auth_token=None):
    """Return an authenticated Spotify object."""
    oauth = get_oauth()
    token_info = oauth.get_cached_token()
    if not token_info and auth_token:
        token_info = oauth.get_access_token(auth_token)
    return spotipy.Spotify(token_info["access_token"])


if __name__ == '__main__':
    app.run()
