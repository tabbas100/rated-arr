package com.androidtv.fetch.model;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.util.Arrays;

public class ProfilesTest {

    private final Profiles profiles = new Profiles(Arrays.asList(new Profile(1, "Any"), new Profile(4, "HD-1080p"),
            new Profile(5, "Ultra-HD")), 4);

    @Test
    public void pickPrefersTheRememberedProfile() {
        assertEquals(5, profiles.pick(5).id);
    }

    @Test
    public void pickFallsBackToTheDefaultWhenTheRememberedOneIsGone() {
        assertEquals(4, profiles.pick(99).id);
    }

    @Test
    public void nextWrapsRound() {
        assertEquals(1, profiles.next(profiles.pick(5)).id);
    }
}
