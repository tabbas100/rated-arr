package com.androidtv.fetch.model;

import java.util.ArrayList;
import java.util.List;

/** The genres offered for films and for shows, in the order the chips show them. */
public final class Genres {

    public final List<Genre> films;
    public final List<Genre> shows;

    public Genres(List<Genre> films, List<Genre> shows) {
        this.films = films;
        this.shows = shows;
    }

    public static Genres none() {
        return new Genres(new ArrayList<>(), new ArrayList<>());
    }

    public List<Genre> of(Item.Kind kind) {
        return kind == Item.Kind.FILM ? films : shows;
    }
}
