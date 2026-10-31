package com.androidtv.fetch.screens;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.androidtv.fetch.R;
import com.androidtv.fetch.gateway.FetchException;
import com.androidtv.fetch.gateway.Session;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.DownloadGroup;
import com.androidtv.fetch.ui.Background;
import com.androidtv.fetch.ui.Cards;
import com.androidtv.fetch.ui.Errors;

import java.util.ArrayList;
import java.util.List;

/**
 * Everything downloading for one title, one row each: a show's episodes or a film. Opened from a
 * card in the Downloading row; refreshed every 10 seconds while it is on screen.
 */
public class DownloadsActivity extends Activity {

    static final String EXTRA_KEY = "key";
    static final String EXTRA_TITLE = "title";
    static final String EXTRA_POSTER = "poster";
    private static final long REFRESH_MS = 10_000;

    private Session session;
    private String key;
    private LinearLayout rows;
    private TextView summary;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        @Override
        public void run() {
            Background.run(DownloadsActivity.this, session.client::downloads, DownloadsActivity.this::show,
                    DownloadsActivity.this::showError);
            handler.postDelayed(this, REFRESH_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        session = Session.get(this);
        key = getIntent().getStringExtra(EXTRA_KEY);
        String title = getIntent().getStringExtra(EXTRA_TITLE);
        if (key == null || title == null) {
            finish();
            return;
        }
        setContentView(R.layout.activity_downloads);
        ((TextView) findViewById(R.id.title)).setText(title);
        Cards.bindPoster(findViewById(android.R.id.content), title, getIntent().getStringExtra(EXTRA_POSTER));
        rows = findViewById(R.id.rows);
        summary = findViewById(R.id.summary);
    }

    @Override
    protected void onResume() {
        super.onResume();
        handler.post(refresh);
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(refresh);
    }

    // Purpose: this title's downloads as rows; the same rows are updated in place while their count holds.
    private void show(List<Download> queue) {
        List<Download> mine = new ArrayList<>();
        for (Download download : queue) {
            if (DownloadGroup.keyOf(download).equals(key)) mine.add(download);
        }
        if (mine.isEmpty()) {
            rows.removeAllViews();
            summary.setText(R.string.downloads_done);
            return;
        }
        Cards.bindStatus(summary, mine);
        if (rows.getChildCount() != mine.size()) rebuild(mine.size());
        for (int i = 0; i < mine.size(); i++) bind(rows.getChildAt(i), mine.get(i));
    }

    private void rebuild(int count) {
        rows.removeAllViews();
        LayoutInflater inflater = getLayoutInflater();
        for (int i = 0; i < count; i++) {
            View row = inflater.inflate(R.layout.row_download, rows, false);
            Cards.zoomOnFocus(row, Cards.WIDE_FOCUSED_SCALE);
            rows.addView(row);
        }
        rows.getChildAt(0).requestFocus();
    }

    private static void bind(View row, Download download) {
        ((TextView) row.findViewById(R.id.label)).setText(download.detail.isEmpty() ? download.title : download.detail);
        ((ProgressBar) row.findViewById(R.id.progress)).setProgress((int) Math.round(download.progress * 1000));
        List<Download> one = new ArrayList<>();
        one.add(download);
        Cards.bindStatus(row.findViewById(R.id.status), one);
    }

    private void showError(FetchException error) {
        if (error.reason == FetchException.Reason.NOT_PAIRED) {
            session.forget();
            startActivity(new Intent(this, PairActivity.class));
            finishAffinity();
            return;
        }
        summary.setText(Errors.message(this, error));
    }
}
