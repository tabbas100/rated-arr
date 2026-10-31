package com.androidtv.fetch.model;

/** A genre to browse by: the gateway's id ("bad" for So bad it's good, else TMDB's) and its name. */
public final class Genre {

    public final String id;
    public final String name;

    public Genre(String id, String name) {
        this.id = id;
        this.name = name;
    }
}
