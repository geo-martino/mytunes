from mytunes.libraries.remote.spotify.api import SpotifyAPI

api = SpotifyAPI(
    client_id="<YOUR CLIENT ID>",
    client_secret="<YOUR CLIENT SECRET>",
    scope=[
        "user-library-read",
        "user-follow-read",
        "playlist-read-collaborative",
        "playlist-read-private",
        "playlist-modify-public",
        "playlist-modify-private"
    ],
    # providing a `token_file_path` will save the generated token to your system
    # for quicker authorisations in future
    token_file_path="<PATH TO JSON TOKEN>"
)
