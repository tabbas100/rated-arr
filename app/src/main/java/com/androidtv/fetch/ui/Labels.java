package com.androidtv.fetch.ui;

import com.androidtv.fetch.model.Choice;
import com.androidtv.fetch.model.Download;
import com.androidtv.fetch.model.Episode;
import com.androidtv.fetch.model.Have;
import com.androidtv.fetch.model.Item;
import com.androidtv.fetch.model.LibraryEntry;
import com.androidtv.fetch.model.Storage;
import com.androidtv.fetch.model.TitleDetails;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** The short lines of text under titles and on download cards. */
public final class Labels {

    private static final String DOT = " · ";

    private Labels() {
    }

    /** "2010 · 2h 28m · Action, Thriller · ★ 8.8" for films, "2008 · AMC · 5 seasons · ★ 9.5" for shows. */
    public static String details(Item item) {
        List<String> parts = new ArrayList<>();
        if (item.year > 0) parts.add(String.valueOf(item.year));
        if (item.kind == Item.Kind.FILM && item.runtimeMinutes > 0) parts.add(runtime(item.runtimeMinutes));
        if (item.kind == Item.Kind.SHOW && !item.network.isEmpty()) parts.add(item.network);
        if (item.kind == Item.Kind.SHOW && item.seasons > 0) parts.add(seasons(item.seasons));
        if (!item.genres.isEmpty()) parts.add(item.genres);
        if (item.rating > 0) parts.add(rating(item.rating));
        return String.join(DOT, parts);
    }

    /**
     * The library status on a title's page before the episode counts arrive: "In your library" for a
     * show, "In your library · Ready to watch" for a downloaded film.
     */
    public static String libraryStatus(Item item) {
        if (item.kind == Item.Kind.SHOW) return "In your library";
        return "In your library" + DOT + (item.downloaded ? "Ready to watch" : "Not downloaded yet");
    }

    /** "In your library · 305 of 369 episodes": downloaded of aired, the same count as the episode picker. */
    public static String episodesStatus(List<Episode> episodes) {
        int aired = Have.aired(episodes);
        if (aired == 0) return "In your library" + DOT + "No episodes have aired yet";
        return "In your library" + DOT + Have.downloaded(episodes) + " of " + episodeCount(aired);
    }

    /** The line under a poster card: the year and the rating. */
    static String cardLine(Item item) {
        List<String> parts = new ArrayList<>();
        if (item.year > 0) parts.add(String.valueOf(item.year));
        if (item.rating > 0) parts.add(rating(item.rating));
        return String.join(DOT, parts);
    }

    static String runtime(int minutes) {
        if (minutes < 60) return minutes + "m";
        return String.format(Locale.ROOT, "%dh %02dm", minutes / 60, minutes % 60);
    }

    static String seasons(int count) {
        return count == 1 ? "1 season" : count + " seasons";
    }

    static String rating(double rating) {
        return String.format(Locale.ROOT, "★ %.1f", rating);
    }

    /** "Downloading · 75% · 12m left", "Waiting in the queue", "Needs attention" and so on. */
    static String downloadStatus(Download download) {
        int percent = (int) Math.round(download.progress * 100);
        switch (download.state) {
            case DOWNLOADING:
                return "Downloading" + DOT + percent + "%" + (download.timeLeft.isEmpty() ? "" : DOT + download.timeLeft + " left");
            case PAUSED:
                return "Paused" + DOT + percent + "%";
            case IMPORTING:
                return "Finishing up";
            case PROBLEM:
                return download.message.isEmpty()
                        ? "Needs attention in " + (download.kind == Item.Kind.FILM ? "Radarr" : "Sonarr")
                        : download.message;
            default:
                return "Waiting in the queue";
        }
    }

    /**
     * One line for everything downloading for one title: "Downloading · 45% · 12m left" for a film,
     * "Downloading 3 episodes · 45%" for a show, or the most urgent state when nothing moves.
     */
    public static String progressSummary(List<Download> downloads) {
        if (downloads.size() == 1) return downloadStatus(downloads.get(0));
        Download problem = null;
        int downloading = 0;
        for (Download d : downloads) {
            if (d.state == Download.State.PROBLEM) problem = d;
            if (d.state == Download.State.DOWNLOADING) downloading++;
        }
        if (problem != null) return downloadStatus(problem);
        int percent = (int) Math.round(averageProgress(downloads) * 100);
        if (downloading == 0) return episodeCount(downloads.size()) + " waiting in the queue";
        return "Downloading " + episodeCount(downloads.size()) + DOT + percent + "%";
    }

    public static double averageProgress(List<Download> downloads) {
        double total = 0;
        for (Download d : downloads) total += d.progress;
        return downloads.isEmpty() ? 0 : total / downloads.size();
    }

    /** What happened after the picker saved: "Added. Sonarr is looking for 14 episodes now." and so on. */
    public static String choiceMessage(Choice choice) {
        String text;
        if (choice.chosen == 0) text = "Saved. No episodes are wanted now.";
        else if (choice.searching == 0) text = "Saved. " + episodeCount(choice.chosen) + " wanted; they download as they air.";
        else if (choice.searching == 1) text = "Added. Sonarr is looking for 1 episode now.";
        else text = "Added. Sonarr is looking for " + choice.searching + " episodes now.";
        if (choice.unmatched > 0) text += " " + episodeCount(choice.unmatched) + " didn’t match Sonarr’s list.";
        return text;
    }

    private static String episodeCount(int count) {
        return count == 1 ? "1 episode" : count + " episodes";
    }

    /** Bytes in decimal units, as Whatbox shows them: "850 MB", "37.4 GB", "2.08 TB". */
    public static String size(long bytes) {
        String[] units = {"B", "KB", "MB", "GB", "TB", "PB"};
        double value = bytes;
        int unit = 0;
        while (value >= 1000 && unit < units.length - 1) {
            value /= 1000;
            unit++;
        }
        String pattern = unit == 0 || value >= 100 ? "%.0f" : value >= 10 ? "%.1f" : "%.2f";
        return trimZeros(String.format(Locale.ROOT, pattern, value)) + " " + units[unit];
    }

    // Purpose: "3.90" as "3.9" and "12.0" as "12", so sizes read like Whatbox's.
    private static String trimZeros(String number) {
        if (!number.contains(".")) return number;
        return number.replaceAll("0+$", "").replaceAll("\\.$", "");
    }

    /** "1.82 TB of 3.9 TB used · 2.08 TB free", the same numbers as Whatbox's page. */
    public static String storage(Storage storage) {
        return size(storage.used) + " of " + size(storage.limit) + " used" + DOT + size(storage.free) + " free";
    }

    /** "Directed by John Gray · ★ 5.4 from 454 votes on TMDB"; "" when TMDB has neither. */
    public static String credits(TitleDetails details) {
        List<String> parts = new ArrayList<>();
        if (!details.makers.isEmpty()) {
            String role = "Director".equals(details.makersRole) ? "Directed by " : "Created by ";
            parts.add(role + String.join(", ", details.makers));
        }
        if (details.rating > 0 && details.votes > 0) {
            String votes = details.votes == 1 ? "1 vote" : String.format(Locale.US, "%,d votes", details.votes);
            parts.add(String.format(Locale.ROOT, "★ %.1f from %s on TMDB", details.rating, votes));
        }
        return String.join(DOT, parts);
    }

    /** The line under a library card: size and quality, or the problem. */
    static String libraryLine(LibraryEntry entry) {
        if (entry.isDiscImage()) return size(entry.size) + DOT + "Disc image";
        return entry.quality.isEmpty() ? size(entry.size) : size(entry.size) + DOT + entry.quality;
    }

    /** Initials for a poster that has no image: "BB" for Breaking Bad. */
    static String initials(String title) {
        StringBuilder out = new StringBuilder();
        for (String word : title.trim().split("\\s+")) {
            if (!word.isEmpty() && Character.isLetterOrDigit(word.codePointAt(0))) {
                out.appendCodePoint(Character.toUpperCase(word.codePointAt(0)));
            }
            if (out.length() >= 2) break;
        }
        return out.toString();
    }
}
