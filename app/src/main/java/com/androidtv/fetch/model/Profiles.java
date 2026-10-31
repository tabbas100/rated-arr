package com.androidtv.fetch.model;

import java.util.List;

/** The quality profiles of one library and the one used when the TV does not choose. */
public final class Profiles {

    final List<Profile> all;
    public final int defaultId;

    public Profiles(List<Profile> all, int defaultId) {
        this.all = all;
        this.defaultId = defaultId;
    }

    public boolean isEmpty() {
        return all.isEmpty();
    }

    /** The profile with this id if it still exists, else the server's default, else the first. */
    public Profile pick(int preferredId) {
        if (all.isEmpty()) throw new IllegalStateException("no quality profiles");
        Profile preferred = find(preferredId);
        if (preferred != null) return preferred;
        Profile fallback = find(defaultId);
        return fallback != null ? fallback : all.get(0);
    }

    /** The profile after this one, wrapping round. */
    public Profile next(Profile current) {
        return all.get((all.indexOf(current) + 1) % all.size());
    }

    private Profile find(int id) {
        for (Profile profile : all) {
            if (profile.id == id) return profile;
        }
        return null;
    }
}
