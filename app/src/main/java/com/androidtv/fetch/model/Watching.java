package com.androidtv.fetch.model;

import java.util.List;

/** Plex's Continue Watching from the gateway, newest first, and the Plex server it plays from. */
public final class Watching {

    /** One film or episode to resume. */
    public static final class Entry {
        public final boolean episode;
        /** Plex's ids on its server, digits only: the item, and for an episode its show and season. */
        public final String key;
        public final String showKey;
        public final String seasonKey;
        /** The film's title, or the show's for an episode. */
        public final String title;
        public final String episodeTitle;
        public final int season;
        public final int episodeNumber;
        public final long positionMs;
        public final long durationMs;
        public final long watchedAtMs;
        /** A 16:9 picture on TMDB, or "". */
        public final String art;

        public Entry(boolean episode, String key, String showKey, String seasonKey, String title, String episodeTitle,
              int season, int episodeNumber, long positionMs, long durationMs, long watchedAtMs, String art) {
            this.episode = episode;
            this.key = key;
            this.showKey = showKey;
            this.seasonKey = seasonKey;
            this.title = title;
            this.episodeTitle = episodeTitle;
            this.season = season;
            this.episodeNumber = episodeNumber;
            this.positionMs = positionMs;
            this.durationMs = durationMs;
            this.watchedAtMs = watchedAtMs;
            this.art = art;
        }

        /** False for the next episode of a show, which nobody has started yet. */
        public boolean started() {
            return positionMs > 0;
        }
    }

    /** Plex's machine identifier. */
    public final String server;
    public final List<Entry> entries;

    public Watching(String server, List<Entry> entries) {
        this.server = server;
        this.entries = entries;
    }
}
