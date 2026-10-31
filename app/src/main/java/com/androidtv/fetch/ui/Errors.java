package com.androidtv.fetch.ui;

import android.content.Context;

import com.androidtv.fetch.R;
import com.androidtv.fetch.gateway.FetchException;

/** What to tell the viewer about a failed call, in one sentence. */
public final class Errors {

    private Errors() {
    }

    public static String message(Context context, FetchException error) {
        switch (error.reason) {
            case OFFLINE:
                return context.getString(R.string.error_offline);
            case BUSY:
                return context.getString(R.string.error_busy);
            case NOT_FOUND:
                return context.getString(R.string.error_not_found);
            case ALREADY_ADDED:
                return context.getString(R.string.already_added);
            case REJECTED:
                return context.getString(R.string.error_rejected, error.detail);
            default:
                return context.getString(R.string.error_server, error.detail.isEmpty() ? error.reason.name() : error.detail);
        }
    }
}
