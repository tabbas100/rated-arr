package com.androidtv.fetch.screens;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.View;
import android.widget.TextView;

import com.androidtv.fetch.R;
import com.androidtv.fetch.gateway.FetchException;
import com.androidtv.fetch.gateway.Session;
import com.androidtv.fetch.model.Pairing;
import com.androidtv.fetch.ui.Background;
import com.androidtv.fetch.ui.Cards;
import com.androidtv.fetch.ui.Errors;

import java.security.GeneralSecurityException;
import java.util.Locale;

/**
 * First run: asks the gateway for a pairing code, shows it, and waits while the owner approves
 * it from the Mac over SSH. The device token then arrives once and is sealed in the Keystore.
 */
public class PairActivity extends Activity {

    private static final long POLL_MS = 2_000;
    private static final long RETRY_MS = 10_000;
    private static final long TICK_MS = 1_000;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable poll = this::poll;
    private final Runnable restart = this::requestCode;
    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            showCountdown();
            handler.postDelayed(this, TICK_MS);
        }
    };

    private Session session;
    private TextView code, state, expires, retry;
    private View spinner;
    private Pairing pairing;
    private long expiresAt;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_pair);
        session = Session.get(this);
        code = findViewById(R.id.code);
        state = findViewById(R.id.state);
        expires = findViewById(R.id.expires);
        retry = findViewById(R.id.retry);
        spinner = findViewById(R.id.spinner);
        retry.setOnClickListener(v -> requestCode());
        Cards.zoomOnFocus(retry);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (pairing == null || SystemClock.elapsedRealtime() >= expiresAt) requestCode();
        else startWaiting();
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacksAndMessages(null);
    }

    private void requestCode() {
        handler.removeCallbacksAndMessages(null);
        showWaiting(getString(R.string.pair_starting));
        Background.run(this, () -> session.client.startPairing(deviceName()), started -> {
            pairing = started;
            expiresAt = SystemClock.elapsedRealtime() + started.expiresInSeconds * 1000L;
            code.setText(started.code);
            startWaiting();
        }, this::showFailure);
    }

    private void startWaiting() {
        showWaiting(getString(R.string.pair_waiting));
        handler.post(tick);
        handler.postDelayed(poll, POLL_MS);
    }

    private void poll() {
        Pairing current = pairing;
        Background.run(this, () -> session.client.pollPairing(current.id), token -> {
            if (token.isEmpty()) handler.postDelayed(poll, POLL_MS);
            else finishPairing(token);
        }, error -> {
            if (error.reason == FetchException.Reason.PAIRING_EXPIRED) requestCode();
            else showFailure(error);
        });
    }

    private void finishPairing(String token) {
        handler.removeCallbacksAndMessages(null);
        try {
            session.tokens.save(token);
        } catch (GeneralSecurityException e) {
            showFailure(new FetchException(FetchException.Reason.SERVER, "secure storage unavailable", null, e));
            return;
        }
        startActivity(new Intent(this, MainActivity.class));
        finish();
    }

    // Purpose: "The code changes in 9:41"; a fresh code is fetched when it runs out.
    private void showCountdown() {
        long left = Math.max(0, expiresAt - SystemClock.elapsedRealtime()) / 1000;
        expires.setText(getString(R.string.pair_expires,
                String.format(Locale.ROOT, "%d:%02d", left / 60, left % 60)));
        if (left == 0) requestCode();
    }

    private void showWaiting(String text) {
        state.setText(text);
        state.setTextColor(getColor(R.color.text_dim));
        spinner.setVisibility(View.VISIBLE);
        retry.setVisibility(View.GONE);
    }

    // Purpose: say what went wrong, offer Try again, and try again by itself after a while.
    private void showFailure(FetchException error) {
        handler.removeCallbacksAndMessages(null);
        state.setText(Errors.message(this, error));
        state.setTextColor(getColor(R.color.warning));
        spinner.setVisibility(View.GONE);
        expires.setText("");
        retry.setVisibility(View.VISIBLE);
        retry.requestFocus();
        handler.postDelayed(restart, RETRY_MS);
    }

    // Purpose: the name the owner gave the TV ("Living Room TV"), shown when approving.
    private String deviceName() {
        String name = Settings.Global.getString(getContentResolver(), Settings.Global.DEVICE_NAME);
        return name != null && !name.trim().isEmpty() ? name.trim() : Build.MODEL;
    }
}
