package com.androidtv.fetch.model;

/** One entry of the download queue. */
public final class Download {

    public enum State { QUEUED, DOWNLOADING, PAUSED, IMPORTING, PROBLEM }

    public final Item.Kind kind;
    /** TMDB id for films, TVDB id for shows: the title this download belongs to; 0 when unknown. */
    final int id;
    public final String title;
    /** "S02E05 · Title" for an episode, the quality for a film. */
    public final String detail;
    /** 0 to 1. */
    public final double progress;
    public final State state;
    /** Why it needs attention, in Sonarr's or Radarr's words; empty when nothing is wrong. */
    public final String message;
    /** "1h 05m", or empty when unknown. */
    public final String timeLeft;
    final String poster;

    public Download(Item.Kind kind, int id, String title, String detail, double progress, State state, String message,
             String timeLeft, String poster) {
        this.kind = kind;
        this.id = id;
        this.title = title;
        this.detail = detail;
        this.progress = progress;
        this.state = state;
        this.message = message;
        this.timeLeft = timeLeft;
        this.poster = poster;
    }

    /** The same key as the Item it belongs to. */
    public String key() {
        return kind + ":" + id;
    }

    /** True when any of the downloads needs attention. */
    public static boolean anyProblem(java.util.List<Download> downloads) {
        for (Download download : downloads) {
            if (download.state == State.PROBLEM) return true;
        }
        return false;
    }
}
