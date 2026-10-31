package com.androidtv.fetch.model;

import java.util.List;

/** One row to discover on the home screen, such as "recommended" films or "trendingShows". */
public final class Shelf {

    public final String id;
    /** The show a "becauseYouHave" row is about; empty for other rows. */
    public final String subject;
    /** "tmdb" for rows from TMDB, which must be credited; empty for Radarr's own. */
    final String source;
    public final List<Item> items;

    public Shelf(String id, String subject, String source, List<Item> items) {
        this.id = id;
        this.subject = subject;
        this.source = source;
        this.items = items;
    }

    public boolean fromTmdb() {
        return "tmdb".equals(source);
    }
}
