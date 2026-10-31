package com.androidtv.fetch.model;

import java.util.List;

/** A season and its episodes; number 0 is specials. */
public final class Season {

    public final int number;
    public final List<Episode> episodes;

    public Season(int number, List<Episode> episodes) {
        this.number = number;
        this.episodes = episodes;
    }
}
