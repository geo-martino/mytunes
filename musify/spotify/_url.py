from yarl import URL

API_URL = URL.build(scheme="https", host="api.spotify.com", path=f"/v1")
PUBLIC_URL = URL.build(scheme="https", host="open.spotify.com")
