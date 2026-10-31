package com.androidtv.fetch.model;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** The library tab's data: films, shows and the plan's disk space. */
public final class Library {

    public final List<LibraryEntry> films;
    public final List<LibraryEntry> shows;
    public final Storage storage;

    public Library(List<LibraryEntry> films, List<LibraryEntry> shows, Storage storage) {
        this.films = films;
        this.shows = shows;
        this.storage = storage;
    }

    /** Titles Plex cannot play, films first. */
    public List<LibraryEntry> problems() {
        List<LibraryEntry> out = new ArrayList<>();
        for (LibraryEntry entry : films) {
            if (entry.isDiscImage()) out.add(entry);
        }
        return largestFirst(out);
    }

    /** Titles that take up space, largest first. */
    public static List<LibraryEntry> largestFirst(List<LibraryEntry> entries) {
        List<LibraryEntry> out = new ArrayList<>();
        for (LibraryEntry entry : entries) {
            if (entry.size > 0) out.add(entry);
        }
        out.sort(Comparator.comparingLong((LibraryEntry e) -> e.size).reversed());
        return out;
    }
}
