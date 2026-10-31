package com.androidtv.fetch.model;

/** A quality profile, such as "HD-1080p", that decides which release Radarr or Sonarr grabs. */
public final class Profile {

    public final int id;
    public final String name;

    public Profile(int id, String name) {
        this.id = id;
        this.name = name;
    }
}
