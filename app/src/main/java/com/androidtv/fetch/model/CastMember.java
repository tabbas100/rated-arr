package com.androidtv.fetch.model;

/** One actor on the title page: their name, the part they play, and a photo URL ("" for none). */
public final class CastMember {

    public final String name;
    public final String character;
    public final String photo;

    public CastMember(String name, String character, String photo) {
        this.name = name;
        this.character = character;
        this.photo = photo;
    }
}
