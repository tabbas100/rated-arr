package com.androidtv.fetch.model;

/** A film or show as the gateway describes it. */
public final class Item {

    public enum Kind { FILM, SHOW }

    public final Kind kind;
    /** TMDB id for films, TVDB id for shows. */
    public final int id;
    public final String title;
    public final int year;
    public final String overview;
    public final String poster;
    public final String fanart;
    public final int runtimeMinutes;
    public final String genres;
    /** 0 to 10, 0 when unknown. */
    public final double rating;
    /** The network for shows, empty for films. */
    public final String network;
    /** Seasons without specials, 0 for films. */
    public final int seasons;
    public final boolean inLibrary;
    public final boolean downloaded;
    /** The item as the gateway sent it, to hand to another screen. */
    public final String json;

    public Item(Kind kind, int id, String title, int year, String overview, String poster, String fanart,
         int runtimeMinutes, String genres, double rating, String network, int seasons, boolean inLibrary,
         boolean downloaded, String json) {
        this.kind = kind;
        this.id = id;
        this.title = title;
        this.year = year;
        this.overview = overview;
        this.poster = poster;
        this.fanart = fanart;
        this.runtimeMinutes = runtimeMinutes;
        this.genres = genres;
        this.rating = rating;
        this.network = network;
        this.seasons = seasons;
        this.inLibrary = inLibrary;
        this.downloaded = downloaded;
        this.json = json;
    }

    /** The same title after its file was deleted. */
    public Item withoutFile() {
        return new Item(kind, id, title, year, overview, poster, fanart, runtimeMinutes, genres, rating, network,
                seasons, inLibrary, false, json);
    }

    /** The same title after it was removed from the library. */
    public Item removed() {
        return new Item(kind, id, title, year, overview, poster, fanart, runtimeMinutes, genres, rating, network,
                seasons, false, false, json);
    }

    /** The same title across searches and the library. */
    public String key() {
        return kind + ":" + id;
    }
}
