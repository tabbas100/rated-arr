package com.androidtv.fetch.model;

/** A pairing request: the secret id the TV polls with and the code it shows. */
public final class Pairing {

    public final String id;
    public final String code;
    public final int expiresInSeconds;

    public Pairing(String id, String code, int expiresInSeconds) {
        this.id = id;
        this.code = code;
        this.expiresInSeconds = expiresInSeconds;
    }
}
