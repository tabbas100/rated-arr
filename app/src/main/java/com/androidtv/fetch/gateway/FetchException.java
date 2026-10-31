package com.androidtv.fetch.gateway;

import com.androidtv.fetch.model.Item;

/** A gateway call that failed, sorted into what the screen should say or do. */
public final class FetchException extends Exception {

    public enum Reason {
        /** No connection to the gateway, or it timed out. */
        OFFLINE,
        /** The token is missing, wrong or revoked: pair again. */
        NOT_PAIRED,
        /** The pairing request expired: start a new one. */
        PAIRING_EXPIRED,
        /** The title is already in the library. */
        ALREADY_ADDED,
        NOT_FOUND,
        /** Radarr or Sonarr refused, with its own reason in detail. */
        REJECTED,
        /** Too many requests, or the gateway is busy: try again shortly. */
        BUSY,
        /** Radarr or Sonarr is down, or the reply was unusable. */
        SERVER
    }

    public final Reason reason;
    public final String detail;
    /** For ALREADY_ADDED, the title as it is in the library; null otherwise. */
    public final Item item;

    public FetchException(Reason reason, String detail) {
        this(reason, detail, null, null);
    }

    public FetchException(Reason reason, String detail, Item item, Throwable cause) {
        super(reason + (detail.isEmpty() ? "" : ": " + detail), cause);
        this.reason = reason;
        this.detail = detail;
        this.item = item;
    }
}
