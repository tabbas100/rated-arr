package com.androidtv.fetch.watchnext;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Toast;

import com.androidtv.fetch.R;

/**
 * Opens one of Fetch's Watch Next rows in Plex. It shows nothing itself: it hands over to Plex and closes.
 * Other apps may start it, so it opens only a Plex film or episode link (PlexLink.isValid).
 */
public final class ResumeActivity extends Activity {

    static final String EXTRA_LINK = "link";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String link = getIntent().getStringExtra(EXTRA_LINK);
        try {
            if (!PlexLink.isValid(link)) throw new ActivityNotFoundException("not a Plex film or episode link");
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(link)).setPackage(PlexLink.PLEX_PACKAGE));
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, R.string.resume_failed, Toast.LENGTH_LONG).show();
        }
        finish();
    }
}
