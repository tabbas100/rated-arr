package com.androidtv.fetch.model;

/** One episode in the picker. Season 0 is specials. */
public final class Episode {

    public final int season;
    public final int number;
    public final String title;
    /** "2008-01-20", or empty when not announced. */
    public final String airDate;
    public final boolean aired;
    public final boolean downloaded;
    /** Sonarr already wants (monitors) it. */
    public final boolean wanted;
    /** The size of its file in bytes, 0 when it has none. */
    public final long size;

    public Episode(int season, int number, String title, String airDate, boolean aired, boolean downloaded, boolean wanted) {
        this(season, number, title, airDate, aired, downloaded, wanted, 0);
    }

    public Episode(int season, int number, String title, String airDate, boolean aired, boolean downloaded, boolean wanted,
            long size) {
        this.season = season;
        this.number = number;
        this.title = title;
        this.airDate = airDate;
        this.aired = aired;
        this.downloaded = downloaded;
        this.wanted = wanted;
        this.size = size;
    }
}
