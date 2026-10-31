package com.androidtv.fetch.ui;

import android.graphics.Rect;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import com.androidtv.fetch.R;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.DownloadGroup;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.LibraryEntry;

/** Builds the rows' cards and gives every focusable card the same gentle zoom. */
public final class Cards {

    private static final float FOCUSED_SCALE = 1.07f;
    /** Wide rows grow less, so their edges stay on screen. */
    public static final float WIDE_FOCUSED_SCALE = 1.02f;
    private static final int ZOOM_MS = 160;

    private Cards() {
    }

    /** A titled, sideways-scrolling row added to parent; returns the row its cards go in. */
    public static ViewGroup section(LayoutInflater inflater, ViewGroup parent, CharSequence title, CharSequence note) {
        View section = inflater.inflate(R.layout.section_row, parent, false);
        ((TextView) section.findViewById(R.id.sectionTitle)).setText(title);
        TextView noteView = section.findViewById(R.id.sectionNote);
        noteView.setText(note);
        noteView.setVisibility(note.length() > 0 ? View.VISIBLE : View.GONE);
        parent.addView(section);
        return section.findViewById(R.id.sectionRow);
    }

    public static View poster(LayoutInflater inflater, ViewGroup row, Item item, View.OnClickListener onClick) {
        View card = inflater.inflate(R.layout.card_poster, row, false);
        ((TextView) card.findViewById(R.id.cardTitle)).setText(item.title);
        ((TextView) card.findViewById(R.id.cardLine)).setText(Labels.cardLine(item));
        bindPoster(card, item.title, item.poster);
        markInLibrary(card, item.inLibrary, item.downloaded);
        card.setContentDescription(item.title);
        card.setOnClickListener(onClick);
        zoomOnFocus(card);
        row.addView(card);
        return card;
    }

    /** A library title: its poster with the size and quality under it, amber when Plex cannot play it. */
    public static View libraryPoster(LayoutInflater inflater, ViewGroup row, LibraryEntry entry, View.OnClickListener onClick) {
        View card = poster(inflater, row, entry.item, onClick);
        TextView line = card.findViewById(R.id.cardLine);
        line.setText(Labels.libraryLine(entry));
        if (entry.isDiscImage()) line.setTextColor(card.getContext().getColor(R.color.warning));
        markInLibrary(card, false, false);
        return card;
    }

    /** Shows or hides the green badge: "In library", or "Ready" once downloaded. */
    public static void markInLibrary(View card, boolean inLibrary, boolean downloaded) {
        TextView badge = card.findViewById(R.id.badge);
        badge.setText(downloaded ? R.string.badge_downloaded : R.string.badge_in_library);
        badge.setVisibility(inLibrary ? View.VISIBLE : View.GONE);
    }

    /** One card for everything downloading for a title: a film, or all of a show's episodes. */
    public static View downloadGroup(LayoutInflater inflater, ViewGroup row, DownloadGroup group, View.OnClickListener onClick) {
        View card = inflater.inflate(R.layout.card_download, row, false);
        ((TextView) card.findViewById(R.id.cardTitle)).setText(group.title);
        Posters.load(card.findViewById(R.id.poster), group.poster, px(card, 56), null);
        bindDownloadGroup(card, group);
        card.setOnClickListener(onClick);
        zoomOnFocus(card);
        row.addView(card);
        return card;
    }

    /** The parts of a download card that change while it downloads; used again on every refresh. */
    public static void bindDownloadGroup(View card, DownloadGroup group) {
        Download first = group.downloads.get(0);
        String line = group.kind == Item.Kind.SHOW && group.downloads.size() > 1
                ? card.getResources().getQuantityString(R.plurals.episodes_count, group.downloads.size(), group.downloads.size())
                : first.detail;
        ((TextView) card.findViewById(R.id.cardLine)).setText(line);
        ((ProgressBar) card.findViewById(R.id.progress)).setProgress(
                (int) Math.round(Labels.averageProgress(group.downloads) * 1000));
        bindStatus(card.findViewById(R.id.status), group.downloads);
    }

    /** The status line, amber when any download needs attention. */
    public static void bindStatus(TextView status, java.util.List<Download> downloads) {
        status.setText(Labels.progressSummary(downloads));
        status.setTextColor(status.getContext().getColor(Download.anyProblem(downloads) ? R.color.warning : R.color.text_dim));
    }

    /** The poster image over its placeholder initials, with rounded corners. */
    public static void bindPoster(View holder, String title, String url) {
        View frame = holder.findViewById(R.id.posterFrame);
        frame.setClipToOutline(true);
        TextView initials = holder.findViewById(R.id.initials);
        initials.setText(Labels.initials(title));
        ImageView poster = holder.findViewById(R.id.poster);
        poster.setImageDrawable(null);
        Posters.load(poster, url, frame.getLayoutParams().width, () -> initials.setVisibility(View.INVISIBLE));
    }

    public static void zoomOnFocus(View view) {
        zoomOnFocus(view, FOCUSED_SCALE);
    }

    public static void zoomOnFocus(View view, float focusedScale) {
        view.setOnFocusChangeListener((v, focused) -> {
            float scale = focused ? focusedScale : 1f;
            v.animate().scaleX(scale).scaleY(scale).translationZ(focused ? 12f : 0f)
                    .setDuration(ZOOM_MS).setInterpolator(new DecelerateInterpolator()).start();
            if (focused) {
                keepInRow(v);
                keepOnPage(v);
            }
        });
    }

    /**
     * Scrolls the page so the focused card, with the lines under it and some room around, is fully
     * on screen. The platform scrolls only until the card's own edge shows, which cuts its title.
     */
    private static void keepOnPage(View card) {
        ScrollView page = pageOf(card);
        if (page == null) return;
        int margin = px(card, 28);
        Rect area = new Rect(0, -margin, card.getWidth(), card.getHeight() + margin);
        page.offsetDescendantRectToMyCoords(card, area);
        int top = page.getScrollY() + page.getPaddingTop();
        int bottom = page.getScrollY() + page.getHeight() - page.getPaddingBottom();
        if (area.bottom > bottom) page.smoothScrollBy(0, Math.min(area.bottom - bottom, area.top - top));
        else if (area.top < top) page.smoothScrollBy(0, area.top - top);
    }

    private static ScrollView pageOf(View view) {
        for (android.view.ViewParent parent = view.getParent(); parent != null; parent = parent.getParent()) {
            if (parent instanceof ScrollView) return (ScrollView) parent;
        }
        return null;
    }

    /**
     * Scrolls a sideways row so the focused card sits inside the row's side margins. The platform's
     * own scrolling ignores those margins, which leaves the last card half under the edge fade.
     */
    private static void keepInRow(View card) {
        if (!(card.getParent() instanceof View) || !(((View) card.getParent()).getParent() instanceof HorizontalScrollView)) {
            return;
        }
        HorizontalScrollView scroller = (HorizontalScrollView) ((View) card.getParent()).getParent();
        View row = (View) card.getParent();
        int left = row.getLeft() + card.getLeft() - scroller.getScrollX();
        int right = left + card.getWidth();
        int minLeft = scroller.getPaddingLeft();
        int maxRight = scroller.getWidth() - scroller.getPaddingRight();
        if (right > maxRight) scroller.smoothScrollBy(right - maxRight, 0);
        else if (left < minLeft) scroller.smoothScrollBy(left - minLeft, 0);
    }

    private static int px(View view, int dp) {
        return Math.round(dp * view.getResources().getDisplayMetrics().density);
    }
}
