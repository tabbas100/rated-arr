package com.androidtv.fetch.model;

/** A title in the library with what it takes up on disk. */
public final class LibraryEntry {

    public final Item item;
    /** Bytes on disk: the film's file, or all of a show's episode files. */
    public final long size;
    /** The film file's quality, such as "Bluray-1080p"; empty for shows. */
    public final String quality;
    /** "discImage" when Plex cannot play the file; empty when nothing is wrong. */
    final String problem;

    public LibraryEntry(Item item, long size, String quality, String problem) {
        this.item = item;
        this.size = size;
        this.quality = quality;
        this.problem = problem;
    }

    public boolean isDiscImage() {
        return "discImage".equals(problem);
    }
}
