package com.androidtv.fetch.model;

import java.util.List;
import java.util.Set;

/**
 * Films and shows matching a search, the person it names, and which of the two libraries did not answer.
 * When nothing matched, suggestion is the title closest by spelling that was searched instead.
 */
public final class SearchResults {

    public final List<Item> films;
    public final List<Item> shows;
    public final List<PersonCredits> people;
    public final String suggestion;
    public final Set<Item.Kind> unavailable;

    public SearchResults(List<Item> films, List<Item> shows, List<PersonCredits> people, String suggestion,
                  Set<Item.Kind> unavailable) {
        this.films = films;
        this.shows = shows;
        this.people = people;
        this.suggestion = suggestion;
        this.unavailable = unavailable;
    }

    public boolean isEmpty() {
        return films.isEmpty() && shows.isEmpty() && people.isEmpty();
    }
}
