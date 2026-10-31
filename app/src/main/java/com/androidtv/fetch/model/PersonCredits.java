package com.androidtv.fetch.model;

import java.util.List;

/** The person a search named, with their films and the shows they are a regular in. */
public final class PersonCredits {

    public final String name;
    /** True for a director, whose films read "Films by"; actors' read "Films with". */
    public final boolean directing;
    /** True when the search was this person's name or surname, so their rows come before title matches. */
    public final boolean named;
    public final List<Item> films;
    public final List<Item> shows;

    public PersonCredits(String name, boolean directing, boolean named, List<Item> films, List<Item> shows) {
        this.name = name;
        this.directing = directing;
        this.named = named;
        this.films = films;
        this.shows = shows;
    }
}
