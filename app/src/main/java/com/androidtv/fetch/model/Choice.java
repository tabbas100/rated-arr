package com.androidtv.fetch.model;

/** What applying an episode choice did: the show as it now is, and how many episodes are wanted and searched. */
public final class Choice {

    public final Item item;
    public final int chosen;
    public final int searching;
    /** Picks Sonarr has no episode for (numbering differs); normally 0. */
    public final int unmatched;

    public Choice(Item item, int chosen, int searching, int unmatched) {
        this.item = item;
        this.chosen = chosen;
        this.searching = searching;
        this.unmatched = unmatched;
    }
}
