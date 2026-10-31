package com.androidtv.fetch.model;

import java.util.List;

/** What TMDB adds to the title page: tagline, plot, rating with its votes, who made it, and the cast. */
public final class TitleDetails {

    public final String tagline;
    public final String overview;
    /** 0 to 10, 0 when unknown. */
    public final double rating;
    public final int votes;
    /** "Director" for films, "Created by" for shows. */
    public final String makersRole;
    public final List<String> makers;
    public final List<CastMember> cast;

    public TitleDetails(String tagline, String overview, double rating, int votes, String makersRole, List<String> makers,
                 List<CastMember> cast) {
        this.tagline = tagline;
        this.overview = overview;
        this.rating = rating;
        this.votes = votes;
        this.makersRole = makersRole;
        this.makers = makers;
        this.cast = cast;
    }
}
