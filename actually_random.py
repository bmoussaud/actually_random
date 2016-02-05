#!/usr/bin/env python
# Copyright (C) 2016 Shea G Craig
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""I like to rip mountain bike trails to my giant Spotify playlist,
"Bottomless Happiness". Unfortunately, Spotify's "shuffle" play feature
is not really random. The algorithm is not public information, but some
tracks get played more frequently than others. If you play the playlist
during a ride one day, then ride the next day, chances are extremely
high that you'll hear a lot of the same songs again.

This is annoying to me.

I want all of my jams, and I want them to not repeat until I have had
the auditory satisfaction of enjoying each and every one.

This script allows you to copy an existing playlist after randomizing
the tracks. You can then play without shuffle and get the equivalent of
what you actually wanted.
"""

import base64
import copy
import json
import random
import urllib

from flask import (Flask, request, redirect, g, render_template, url_for,
                   session, flash)
from flask.ext.bootstrap import Bootstrap
from flask.ext.wtf import Form
from wtforms import StringField, SubmitField
from wtforms.validators import Required, NoneOf

import requests
import spotipy
from spotipy import util


app = Flask(__name__)
bootstrap = Bootstrap(app)

# Flask Parameters
CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 8080
REDIRECT_URI = "{}:{}/playlists".format(CLIENT_SIDE_URL, PORT)
SCOPE = "playlist-modify-public playlist-modify-private"


def get_oauth():
    prefs = get_prefs()
    return spotipy.oauth2.SpotifyOAuth(
        prefs["ClientID"], prefs["ClientSecret"], REDIRECT_URI, scope=SCOPE,
        cache_path=".tokens")


def get_spotify():
    oauth = get_oauth()
    token_info = oauth.get_cached_token()
    return spotipy.Spotify(token_info["access_token"])


def get_prefs():
    """Get application prefs plist and set secret key.

    Args:
        path: String path to a plist file.
    """
    with open("config.json") as prefs_file:
        prefs = json.load(prefs_file)
    app.secret_key = prefs["SecretKey"]

    return prefs


def finish_auth(auth_token):
    sp_oauth = get_oauth()
    response_data = sp_oauth.get_access_token(auth_token)


@app.route("/")
def index():
    sp_oauth = get_oauth()
    return redirect(sp_oauth.get_authorize_url())


@app.route("/playlists")
def playlists():
    if session.get("saved"):
        flash("Playlist '{}' saved.".format(session["new_playlist_name"]))
        session["saved"] = False
        del session["new_playlist_name"]

    finish_auth(request.args["code"])
    spotify = get_spotify()
    user_id = spotify.current_user()["id"]
    results = spotify.user_playlists(user_id)

    playlists = results["items"]
    playlist_names = [{"id": playlist["id"], "name": playlist["name"]} for
                      playlist in playlists]
    while results["next"]:
        results = sp.next(playlists)
        playlist_names.extend([{"id": playlist["id"], "name": playlist["name"]}
                               for playlist in results])

    session["playlist_names"] = [item["name"] for item in playlist_names]
    print(playlist_names)
    return render_template("playlists.html", sorted_array=playlist_names)


@app.route("/playlist/<playlist_id>", methods=["GET", "POST"])
def shuffle_playlist(playlist_id):
    # TODO: Refactor

    class PlaylistNameForm(Form):
        name = StringField("Playlist Name", validators=[
            Required(), NoneOf(session["playlist_names"],
                               message="That name is already in use!")])
        submit = SubmitField("Save")

    form = PlaylistNameForm()

    if form.validate_on_submit():
        # If the playlist form is valid, save the new playlist and
        # redirect to playlist page.
        session["new_playlist_name"] = form.name.data
        print("Going to save {} with contents:".format(form.name.data))
        for track in session["shuffled"]:
            print("\t" + track)
        session["saved"] = True
        form.name.data = ""
        return redirect(url_for("index"))

    if (playlist_id == session.get("playlist_id") and
        all(key in session for key in
            ("original", "shuffled", "name", "images"))):
        track_names = session["original"]
        name = session["name"]
        shuffled_names = session["shuffled"]
        images = session["images"]
    else:
        session["playlist_id"] = playlist_id
        spotify = get_spotify()
        user_id = spotify.current_user()["id"]
        results = spotify.user_playlist(user_id, playlist_id)

        tracks = results["tracks"]
        track_names = [track["track"]["name"] for track in tracks["items"]]
        while tracks["next"]:
            tracks = spotify.next(tracks)
            track_names.extend([track["track"]["name"] for track in
                                tracks["items"]])
        session["original"] = track_names

        session["name"] = results["name"]
        name = session["name"]

        session["images"] = results["images"]
        images = session["images"]

        shuffled_names = copy.copy(track_names)
        random.shuffle(shuffled_names)
        session["shuffled"] = shuffled_names

    return render_template(
        "playlist.html", name=name, sorted_array=track_names,
        shuffled_array=shuffled_names, images=images, form=form)


if __name__ == "__main__":
    app.run(debug=True, port=PORT)
