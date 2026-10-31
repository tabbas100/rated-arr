package com.androidtv.fetch.ui;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;

import com.androidtv.fetch.gateway.FetchException;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Runs gateway calls off the main thread and hands results back only while the screen still exists. */
public final class Background {

    public interface Call<T> {
        T run() throws FetchException;
    }

    public interface Done<T> {
        void accept(T value);
    }

    private static final ExecutorService POOL = Executors.newFixedThreadPool(4);
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private Background() {
    }

    public static <T> void run(Activity owner, Call<T> call, Done<T> onResult, Done<FetchException> onError) {
        POOL.execute(() -> {
            try {
                T result = call.run();
                post(owner, () -> onResult.accept(result));
            } catch (FetchException e) {
                post(owner, () -> onError.accept(e));
            } catch (RuntimeException e) {
                FetchException failure = new FetchException(FetchException.Reason.SERVER, "unexpected reply", null, e);
                post(owner, () -> onError.accept(failure));
            }
        });
    }

    private static void post(Activity owner, Runnable task) {
        MAIN.post(() -> {
            if (!owner.isFinishing() && !owner.isDestroyed()) task.run();
        });
    }
}
