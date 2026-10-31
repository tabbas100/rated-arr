package com.androidtv.fetch.model;

/** The plan's disk space as Whatbox counts it: bytes used, the limit and what is free. */
public final class Storage {

    public final long used;
    public final long limit;
    public final long free;

    public Storage(long used, long limit, long free) {
        this.used = used;
        this.limit = limit;
        this.free = free;
    }
}
