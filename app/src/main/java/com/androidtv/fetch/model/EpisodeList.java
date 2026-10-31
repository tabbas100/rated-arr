package com.androidtv.fetch.model;

import java.util.List;

/** A show's episodes by season, and whether Sonarr already has the show. */
public final class EpisodeList {

    public final boolean inLibrary;
    public final List<Season> seasons;

    public EpisodeList(boolean inLibrary, List<Season> seasons) {
        this.inLibrary = inLibrary;
        this.seasons = seasons;
    }
}
