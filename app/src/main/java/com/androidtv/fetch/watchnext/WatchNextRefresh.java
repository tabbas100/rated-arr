package com.androidtv.fetch.watchnext;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;
import android.util.Log;

import com.androidtv.fetch.gateway.FetchException;
import com.androidtv.fetch.gateway.Session;
import com.androidtv.fetch.model.Watching;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Refreshes Fetch's Watch Next rows from the gateway. A home screen such as Cosy sends this whenever it
 * appears. At most one refresh starts per MIN_GAP_MS, and nothing happens before the TV is paired.
 */
public final class WatchNextRefresh extends BroadcastReceiver {

    private static final String TAG = "Fetch";
    private static final long MIN_GAP_MS = 30_000;
    private static final AtomicLong LAST_START = new AtomicLong(-MIN_GAP_MS);
    private static final ExecutorService WORKER = Executors.newSingleThreadExecutor();

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!due()) return;
        PendingResult pending = goAsync();
        Context app = context.getApplicationContext();
        WORKER.execute(() -> {
            try {
                refresh(app);
            } finally {
                pending.finish();
            }
        });
    }

    private static boolean due() {
        long now = SystemClock.elapsedRealtime();
        long last = LAST_START.get();
        return now - last >= MIN_GAP_MS && LAST_START.compareAndSet(last, now);
    }

    private static void refresh(Context context) {
        Session session = Session.get(context);
        if (!session.isPaired()) return;
        try {
            Watching watching = session.client.watching();
            WatchNextRows.replace(context, watching);
            Log.i(TAG, "watch next: " + watching.entries.size() + " rows from Plex");
        } catch (FetchException | SecurityException | IllegalArgumentException e) {
            Log.w(TAG, "watch next not refreshed: " + e);
        }
    }
}
