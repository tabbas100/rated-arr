package com.androidtv.fetch.ui;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;
import android.widget.ImageView;

import com.androidtv.fetch.R;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Loads posters and backdrops into ImageViews: https only, from the two image hosts the gateway
 * allows, at most 4 MB each, decoded at about the size they are shown, cached in memory.
 */
public final class Posters {

    private static final int MAX_BYTES = 4 * 1024 * 1024;
    private static final ExecutorService POOL = Executors.newFixedThreadPool(4);
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final LruCache<String, Bitmap> CACHE =
            new LruCache<String, Bitmap>((int) (Runtime.getRuntime().maxMemory() / 8)) {
                @Override
                protected int sizeOf(String key, Bitmap bitmap) {
                    return bitmap.getByteCount();
                }
            };

    private Posters() {
    }

    /** Shows the image at url in view, scaled for about widthPx; leaves view as it is when there is none. */
    public static void load(ImageView view, String url, int widthPx, Runnable onShown) {
        view.setTag(R.id.poster_url, url);
        if (!ImageHosts.isAllowed(url)) return;
        String key = url + "@" + widthPx;
        Bitmap cached = CACHE.get(key);
        if (cached != null) {
            show(view, cached, onShown);
            return;
        }
        POOL.execute(() -> {
            Bitmap bitmap = fetch(url, widthPx);
            if (bitmap == null) return;
            CACHE.put(key, bitmap);
            MAIN.post(() -> {
                if (url.equals(view.getTag(R.id.poster_url))) show(view, bitmap, onShown);
            });
        });
    }

    private static void show(ImageView view, Bitmap bitmap, Runnable onShown) {
        view.setImageBitmap(bitmap);
        if (onShown != null) onShown.run();
    }

    // Purpose: download and decode one image, or null on any failure (the card keeps its placeholder).
    private static Bitmap fetch(String url, int widthPx) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(20_000);
            connection.setInstanceFollowRedirects(false);
            if (connection.getResponseCode() != 200) return null;
            return decode(readLimited(connection.getInputStream()), widthPx);
        } catch (IOException | OutOfMemoryError e) {
            return null;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static byte[] readLimited(InputStream in) throws IOException {
        try (InputStream stream = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16384];
            int n;
            while ((n = stream.read(buffer)) > 0) {
                if (out.size() + n > MAX_BYTES) throw new IOException("image too large");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }

    // Purpose: decode at the smallest power-of-two scale that is still at least widthPx wide.
    private static Bitmap decode(byte[] data, int widthPx) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
        if (bounds.outWidth <= 0) return null;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = 1;
        while (bounds.outWidth / (options.inSampleSize * 2) >= widthPx) options.inSampleSize *= 2;
        return BitmapFactory.decodeByteArray(data, 0, data.length, options);
    }
}
