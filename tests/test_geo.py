from observatory import geo


def test_known_state_resolves_to_plausible_coordinates():
    lat, lon = geo.centroid("AZ")
    assert 31 < lat < 37
    assert -115 < lon < -109


def test_lookup_is_case_insensitive_and_tolerates_whitespace():
    assert geo.centroid("az") == geo.centroid(" AZ ") == geo.centroid("AZ")


def test_unknown_or_missing_state_returns_none():
    assert geo.centroid("ZZ") is None
    assert geo.centroid(None) is None
    assert geo.centroid("") is None


def test_every_centroid_is_a_plausible_us_coordinate():
    for code, (lat, lon) in geo.STATE_CENTROIDS.items():
        assert -180 < lon < 0, code
        assert 15 < lat < 72, code


def test_the_table_covers_all_fifty_states_and_dc():
    assert len(geo.STATE_CENTROIDS) == 51
    for code in ("CA", "TX", "NY", "AK", "HI", "DC"):
        assert code in geo.STATE_CENTROIDS
