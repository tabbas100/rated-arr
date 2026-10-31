package com.androidtv.fetch.gateway;

import com.androidtv.fetch.model.CastMember;
import com.androidtv.fetch.model.Choice;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.EpisodeList;
import com.androidtv.fetch.model.Genre;
import com.androidtv.fetch.model.Genres;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.Library;
import com.androidtv.fetch.model.LibraryEntry;
import com.androidtv.fetch.model.Pairing;
import com.androidtv.fetch.model.PersonCredits;
import com.androidtv.fetch.model.Profile;
import com.androidtv.fetch.model.Profiles;
import com.androidtv.fetch.model.SearchResults;
import com.androidtv.fetch.model.Season;
import com.androidtv.fetch.model.Shelf;
import com.androidtv.fetch.model.Storage;
import com.androidtv.fetch.model.TitleDetails;
import com.androidtv.fetch.model.Watching;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Reads the gateway's JSON replies into the app's models. */
public final class GatewayJson {

    private GatewayJson() {
    }

    public static Item item(JSONObject o) {
        return new Item(kind(o.optString("kind")), o.optInt("id"), text(o, "title"), o.optInt("year"),
                text(o, "overview"), text(o, "poster"), text(o, "fanart"), o.optInt("runtime"), text(o, "genres"),
                o.optDouble("rating", 0), text(o, "network"), o.optInt("seasons"), o.optBoolean("inLibrary"),
                o.optBoolean("downloaded"), o.toString());
    }

    /** An item handed from one screen to another as its JSON text. */
    public static Item item(String json) throws FetchException {
        return item(object(json));
    }

    static List<Item> items(JSONArray array) {
        List<Item> out = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject o = array.optJSONObject(i);
            if (o != null && o.optInt("id") > 0) out.add(item(o));
        }
        return out;
    }

    static SearchResults search(JSONObject o) {
        return new SearchResults(items(array(o, "films")), items(array(o, "shows")), people(array(o, "people")),
                text(o, "suggestion"), unavailable(o));
    }

    private static List<PersonCredits> people(JSONArray array) {
        List<PersonCredits> out = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject p = array.optJSONObject(i);
            if (p == null || text(p, "name").isEmpty()) continue;
            out.add(new PersonCredits(text(p, "name"), p.optBoolean("directing"), p.optBoolean("named"),
                    items(array(p, "films")), items(array(p, "shows"))));
        }
        return out;
    }

    static List<Download> downloads(JSONObject o) {
        JSONArray array = array(o, "downloads");
        List<Download> out = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject d = array.optJSONObject(i);
            if (d == null) continue;
            out.add(new Download(kind(d.optString("kind")), d.optInt("id"), text(d, "title"), text(d, "detail"),
                    Math.max(0, Math.min(1, d.optDouble("progress", 0))), state(d.optString("state")),
                    text(d, "message"), text(d, "timeLeft"), text(d, "poster")));
        }
        return out;
    }

    public static EpisodeList episodes(JSONObject o) {
        List<Season> seasons = new ArrayList<>();
        JSONArray array = array(o, "seasons");
        for (int i = 0; i < array.length(); i++) {
            JSONObject s = array.optJSONObject(i);
            if (s == null) continue;
            List<Episode> episodes = new ArrayList<>();
            JSONArray list = array(s, "episodes");
            for (int j = 0; j < list.length(); j++) {
                JSONObject e = list.optJSONObject(j);
                if (e == null || e.optInt("number") <= 0) continue;
                episodes.add(new Episode(s.optInt("number"), e.optInt("number"), text(e, "title"), text(e, "airDate"),
                        e.optBoolean("aired"), e.optBoolean("downloaded"), e.optBoolean("wanted"), e.optLong("size")));
            }
            if (!episodes.isEmpty()) seasons.add(new Season(s.optInt("number"), episodes));
        }
        return new EpisodeList(o.optBoolean("inLibrary"), seasons);
    }

    static Choice choice(JSONObject o) throws FetchException {
        JSONObject item = o.optJSONObject("item");
        if (item == null) throw new FetchException(FetchException.Reason.SERVER, "no item in reply");
        return new Choice(item(item), o.optInt("chosen"), o.optInt("searching"), o.optInt("unmatched"));
    }

    public static TitleDetails details(JSONObject o) {
        List<String> makers = new ArrayList<>();
        JSONArray names = array(o, "makers");
        for (int i = 0; i < names.length(); i++) {
            String name = names.optString(i, "");
            if (!name.isEmpty()) makers.add(name);
        }
        List<CastMember> cast = new ArrayList<>();
        JSONArray people = array(o, "cast");
        for (int i = 0; i < people.length(); i++) {
            JSONObject c = people.optJSONObject(i);
            if (c != null && !text(c, "name").isEmpty()) cast.add(new CastMember(text(c, "name"), text(c, "character"), text(c, "photo")));
        }
        return new TitleDetails(text(o, "tagline"), text(o, "overview"), o.optDouble("rating", 0), o.optInt("votes"),
                text(o, "makersRole"), makers, cast);
    }

    static Genres genres(JSONObject o) {
        return new Genres(genreList(array(o, "films")), genreList(array(o, "shows")));
    }

    private static List<Genre> genreList(JSONArray array) {
        List<Genre> out = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject g = array.optJSONObject(i);
            if (g != null && !text(g, "id").isEmpty() && !text(g, "name").isEmpty()) out.add(new Genre(text(g, "id"), text(g, "name")));
        }
        return out;
    }

    static List<Shelf> shelves(JSONObject o) {
        List<Shelf> out = new ArrayList<>();
        JSONArray rows = array(o, "rows");
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row == null) continue;
            List<Item> items = items(array(row, "items"));
            if (!items.isEmpty()) out.add(new Shelf(text(row, "id"), text(row, "subject"), text(row, "source"), items));
        }
        return out;
    }

    static Library library(JSONObject o) {
        JSONObject s = o.optJSONObject("storage");
        Storage storage = s == null ? new Storage(0, 0, 0)
                : new Storage(s.optLong("used"), s.optLong("limit"), s.optLong("free"));
        return new Library(libraryEntries(array(o, "films")), libraryEntries(array(o, "shows")), storage);
    }

    static LibraryEntry libraryEntry(JSONObject o) {
        return new LibraryEntry(item(o), o.optLong("size"), text(o, "quality"), text(o, "problem"));
    }

    private static List<LibraryEntry> libraryEntries(JSONArray array) {
        List<LibraryEntry> out = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject o = array.optJSONObject(i);
            if (o != null && o.optInt("id") > 0) out.add(libraryEntry(o));
        }
        return out;
    }

    static List<Item> recent(JSONObject o) {
        return items(array(o, "items"));
    }

    /** The films' or shows' profiles from GET /v1/profiles. */
    public static Watching watching(JSONObject o) {
        JSONArray array = array(o, "items");
        List<Watching.Entry> entries = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject w = array.optJSONObject(i);
            if (w == null || text(w, "key").isEmpty() || text(w, "title").isEmpty()) continue;
            entries.add(new Watching.Entry("episode".equals(w.optString("kind")), text(w, "key"), text(w, "showKey"),
                    text(w, "seasonKey"), text(w, "title"), text(w, "episodeTitle"), w.optInt("season"), w.optInt("episode"), w.optLong("position"),
                    w.optLong("duration"), w.optLong("watchedAt") * 1000, text(w, "art")));
        }
        return new Watching(text(o, "server"), entries);
    }

    public static Profiles profiles(JSONObject o, Item.Kind kind) {
        JSONObject side = o.optJSONObject(kind == Item.Kind.FILM ? "films" : "shows");
        List<Profile> all = new ArrayList<>();
        JSONArray array = array(side, "profiles");
        for (int i = 0; i < array.length(); i++) {
            JSONObject p = array.optJSONObject(i);
            if (p != null && p.optInt("id") > 0) all.add(new Profile(p.optInt("id"), text(p, "name")));
        }
        return new Profiles(all, side == null ? 0 : side.optInt("default"));
    }

    static Pairing pairing(JSONObject o) throws FetchException {
        String id = text(o, "pairing"), code = text(o, "code");
        if (id.isEmpty() || code.isEmpty()) throw new FetchException(FetchException.Reason.SERVER, "bad pairing reply");
        return new Pairing(id, code, o.optInt("expiresIn", 600));
    }

    /** The token once approved, "" while the request waits. */
    static String pairingToken(JSONObject o) {
        return "approved".equals(o.optString("status")) ? text(o, "token") : "";
    }

    /** The failure an HTTP error status and the gateway's {"error": ...} body stand for. */
    static FetchException error(int status, String body) {
        JSONObject o = objectOrEmpty(body);
        String code = text(o, "error"), message = text(o, "message");
        switch (status) {
            case 401:
                return new FetchException(FetchException.Reason.NOT_PAIRED, code);
            case 404:
                return new FetchException("pairing_expired".equals(code)
                        ? FetchException.Reason.PAIRING_EXPIRED : FetchException.Reason.NOT_FOUND, code);
            case 409:
                return "already_added".equals(code)
                        ? new FetchException(FetchException.Reason.ALREADY_ADDED, "",
                                o.optJSONObject("item") != null ? item(o.optJSONObject("item")) : null, null)
                        : new FetchException(FetchException.Reason.REJECTED, message);
            case 429:
            case 503:
                return new FetchException(FetchException.Reason.BUSY, code);
            default:
                return new FetchException(FetchException.Reason.SERVER, code.isEmpty() ? "HTTP " + status : code);
        }
    }

    static JSONObject object(String json) throws FetchException {
        try {
            return new JSONObject(json);
        } catch (JSONException e) {
            throw new FetchException(FetchException.Reason.SERVER, "unreadable reply", null, e);
        }
    }

    private static JSONObject objectOrEmpty(String json) {
        try {
            return new JSONObject(json);
        } catch (JSONException e) {
            return new JSONObject();
        }
    }

    private static Set<Item.Kind> unavailable(JSONObject o) {
        Set<Item.Kind> out = EnumSet.noneOf(Item.Kind.class);
        JSONArray array = array(o, "unavailable");
        for (int i = 0; i < array.length(); i++) {
            String side = array.optString(i);
            if (side.equals("films")) out.add(Item.Kind.FILM);
            if (side.equals("shows")) out.add(Item.Kind.SHOW);
        }
        return out;
    }

    private static Item.Kind kind(String kind) {
        return "show".equals(kind) ? Item.Kind.SHOW : Item.Kind.FILM;
    }

    private static Download.State state(String state) {
        try {
            return Download.State.valueOf(state.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return Download.State.QUEUED;
        }
    }

    private static JSONArray array(JSONObject o, String key) {
        JSONArray a = o == null ? null : o.optJSONArray(key);
        return a == null ? new JSONArray() : a;
    }

    // Purpose: the field as text, or "" when it is missing or null (org.json would say "null").
    private static String text(JSONObject o, String key) {
        if (o == null || o.isNull(key)) return "";
        return o.optString(key, "");
    }
}
