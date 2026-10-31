package com.androidtv.fetch.gateway;

import com.androidtv.fetch.model.Choice;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.EpisodeList;
import com.androidtv.fetch.model.Genres;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.Library;
import com.androidtv.fetch.model.Pairing;
import com.androidtv.fetch.model.SearchResults;
import com.androidtv.fetch.model.Shelf;
import com.androidtv.fetch.model.TitleDetails;
import com.androidtv.fetch.model.Watching;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * The Fetch gateway's API. HTTPS and the certificate pins are enforced by the platform's network
 * security config; this class adds the bearer token, limits, and turns failures into FetchException.
 */
public final class GatewayClient {

    public interface Tokens {
        /** The device token, or "" before pairing. */
        String token();
    }

    private static final int CONNECT_TIMEOUT_MS = 10_000;
    private static final int READ_TIMEOUT_MS = 45_000;
    private static final int MAX_REPLY_BYTES = 2 * 1024 * 1024;

    private final String baseUrl;
    private final Tokens tokens;

    GatewayClient(String baseUrl, Tokens tokens) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.tokens = tokens;
    }

    public Pairing startPairing(String deviceName) throws FetchException {
        return GatewayJson.pairing(call("POST", "/v1/pair", body("device", deviceName), false));
    }

    /** The device token once the code is approved, "" while it waits. */
    public String pollPairing(String pairingId) throws FetchException {
        return GatewayJson.pairingToken(call("POST", "/v1/pair/poll", body("pairing", pairingId), false));
    }

    public SearchResults search(String query) throws FetchException {
        return GatewayJson.search(call("GET", "/v1/search?q=" + encode(query), null, true));
    }

    public JSONObject profiles() throws FetchException {
        return call("GET", "/v1/profiles", null, true);
    }

    /** @param profileId a quality profile, or 0 for the gateway's default */
    public Item addFilm(int tmdbId, int profileId) throws FetchException {
        JSONObject body = body("id", tmdbId);
        if (profileId > 0) put(body, "profile", profileId);
        return added(call("POST", "/v1/films", body, true));
    }

    /** @param seasons one of all, latest, first or future; @param profileId 0 for the default */
    public Item addShow(int tvdbId, String seasons, int profileId) throws FetchException {
        JSONObject body = body("id", tvdbId);
        put(body, "seasons", seasons);
        if (profileId > 0) put(body, "profile", profileId);
        return added(call("POST", "/v1/shows", body, true));
    }

    public EpisodeList episodes(int tvdbId) throws FetchException {
        return GatewayJson.episodes(call("GET", "/v1/episodes?show=" + tvdbId, null, true));
    }

    /** Makes exactly these [season, episode] pairs the wanted ones; @param profileId 0 for the default. */
    public Choice chooseEpisodes(int tvdbId, List<int[]> picks, int profileId) throws FetchException {
        org.json.JSONArray pairs = new org.json.JSONArray();
        for (int[] pick : picks) pairs.put(new org.json.JSONArray().put(pick[0]).put(pick[1]));
        JSONObject body = body("show", tvdbId);
        put(body, "episodes", pairs);
        if (profileId > 0) put(body, "profile", profileId);
        return GatewayJson.choice(call("POST", "/v1/episodes", body, true));
    }

    public List<Download> downloads() throws FetchException {
        return GatewayJson.downloads(call("GET", "/v1/downloads", null, true));
    }

    public List<Shelf> discover() throws FetchException {
        return GatewayJson.shelves(call("GET", "/v1/discover", null, true));
    }

    public TitleDetails details(Item.Kind kind, int id) throws FetchException {
        String path = "/v1/details?kind=" + (kind == Item.Kind.FILM ? "film" : "show") + "&id=" + id;
        return GatewayJson.details(call("GET", path, null, true));
    }

    public Genres genres() throws FetchException {
        return GatewayJson.genres(call("GET", "/v1/genres", null, true));
    }

    public List<Shelf> browse(Item.Kind kind, String genre) throws FetchException {
        String path = "/v1/browse?kind=" + (kind == Item.Kind.FILM ? "film" : "show") + "&genre=" + encode(genre);
        return GatewayJson.shelves(call("GET", path, null, true));
    }

    public Library library() throws FetchException {
        return GatewayJson.library(call("GET", "/v1/library", null, true));
    }

    /** Deletes a film's file (fileOnly), or removes a film or show with its files; returns the bytes freed. */
    public long deleteTitle(Item.Kind kind, int id, boolean fileOnly) throws FetchException {
        JSONObject body = body("kind", kind == Item.Kind.FILM ? "film" : "show");
        put(body, "id", id);
        put(body, "what", fileOnly ? "file" : "title");
        put(body, "confirm", "delete");
        return call("POST", "/v1/library/delete", body, true).optLong("freed");
    }

    /** Deletes the files of these [season, episode] pairs; returns the bytes freed. */
    public long deleteEpisodes(int tvdbId, List<int[]> picks) throws FetchException {
        org.json.JSONArray pairs = new org.json.JSONArray();
        for (int[] pick : picks) pairs.put(new org.json.JSONArray().put(pick[0]).put(pick[1]));
        JSONObject body = body("show", tvdbId);
        put(body, "episodes", pairs);
        put(body, "confirm", "delete");
        return call("POST", "/v1/library/episodes/delete", body, true).optLong("freed");
    }

    public List<Item> recent() throws FetchException {
        return GatewayJson.recent(call("GET", "/v1/recent", null, true));
    }

    public Watching watching() throws FetchException {
        return GatewayJson.watching(call("GET", "/v1/watching", null, true));
    }

    private static Item added(JSONObject reply) throws FetchException {
        JSONObject item = reply.optJSONObject("item");
        if (item == null) throw new FetchException(FetchException.Reason.SERVER, "no item in reply");
        return GatewayJson.item(item);
    }

    private JSONObject call(String method, String path, JSONObject body, boolean signed) throws FetchException {
        String token = signed ? tokens.token() : "";
        if (signed && token.isEmpty()) throw new FetchException(FetchException.Reason.NOT_PAIRED, "no token");
        HttpURLConnection connection = null;
        try {
            connection = open(method, path, token);
            if (body != null) send(connection, body);
            int status = connection.getResponseCode();
            String reply = read(status >= 400 ? connection.getErrorStream() : connection.getInputStream());
            if (status >= 400) throw GatewayJson.error(status, reply);
            return GatewayJson.object(reply);
        } catch (IOException e) {
            throw new FetchException(FetchException.Reason.OFFLINE, e.getClass().getSimpleName(), null, e);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private HttpURLConnection open(String method, String path, String token) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(baseUrl + path).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setInstanceFollowRedirects(false);
        connection.setUseCaches(false);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("User-Agent", "Fetch/" + BuildInfo.VERSION);
        if (!token.isEmpty()) connection.setRequestProperty("Authorization", "Bearer " + token);
        return connection;
    }

    private static void send(HttpURLConnection connection, JSONObject body) throws IOException {
        byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json");
        connection.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream out = connection.getOutputStream()) {
            out.write(bytes);
        }
    }

    // Purpose: the whole reply as UTF-8, refusing anything over 2 MB.
    private static String read(InputStream in) throws IOException {
        if (in == null) return "";
        try (InputStream stream = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int n;
            while ((n = stream.read(buffer)) > 0) {
                if (out.size() + n > MAX_REPLY_BYTES) throw new IOException("reply too large");
                out.write(buffer, 0, n);
            }
            return out.toString("UTF-8");
        }
    }

    private static JSONObject body(String key, Object value) {
        JSONObject body = new JSONObject();
        put(body, key, value);
        return body;
    }

    private static void put(JSONObject body, String key, Object value) {
        try {
            body.put(key, value);
        } catch (JSONException e) {
            throw new IllegalArgumentException("cannot put " + key, e);
        }
    }

    private static String encode(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8").replace("+", "%20");
        } catch (java.io.UnsupportedEncodingException e) {
            throw new AssertionError("UTF-8 is always supported", e);
        }
    }
}
