import pytest

from observatory import metrics


def test_carry_forward_fills_holes_with_the_previous_value():
    assert metrics.carry_forward([1.0, None, None, 4.0]) == [1.0, 1.0, 1.0, 4.0]


def test_carry_forward_leaves_leading_holes_alone():
    assert metrics.carry_forward([None, None, 3.0]) == [None, None, 3.0]


def test_zscore_of_the_last_value_against_its_history():
    series = [0.0] * 11 + [1.0]
    # mean of the 12 values is 1/12, population sd is sqrt(11)/12
    assert metrics.zscore(series) == pytest.approx(3.3166, abs=1e-3)


def test_zscore_is_none_below_the_minimum_history():
    assert metrics.zscore([1.0] * 11) is None


def test_zscore_is_zero_for_a_flat_series_rather_than_dividing_by_zero():
    assert metrics.zscore([5.0] * 20) == 0.0


def test_zscore_carries_holes_forward_before_scoring():
    # Twelve observed weeks, then a hole: the hole reuses the last value.
    assert metrics.zscore([2.0] * 12 + [None] * 3) == 0.0


# A source outage inside the warm-up window used to be scored as though the
# padding were data: the repeated value shrinks the spread and inflates |z|,
# and that inflated z propagates into stages, SAI, LFI and momentum.
OUTAGE = [1.0, 2.0, 3.0, 4.0, 5.0] + [None] * 10


def test_zscore_does_not_count_carried_forward_padding_as_history():
    assert metrics.zscore(OUTAGE) is None


def test_normalize_series_does_not_count_carried_forward_padding_as_history():
    assert metrics.normalize_series(OUTAGE) == [None] * len(OUTAGE)


def test_acceleration_does_not_count_carried_forward_padding_as_history():
    assert metrics.acceleration(OUTAGE) is None


def test_twelve_observed_weeks_followed_by_holes_still_scores():
    series = [float(i) for i in range(1, 13)] + [None] * 4
    assert metrics.zscore(series) is not None
    assert metrics.normalize_series(series)[-1] is not None
    assert metrics.acceleration(series) is not None


def test_acceleration_is_zero_for_a_straight_line():
    series = [float(i) for i in range(1, 21)]
    assert metrics.acceleration(series) == pytest.approx(0.0, abs=1e-9)


def test_acceleration_is_positive_when_growth_speeds_up():
    series = [float(i * i) for i in range(1, 21)]
    assert metrics.acceleration(series) > 0


def test_acceleration_is_negative_when_growth_slows():
    series = [float(i**0.5) for i in range(1, 21)]
    assert metrics.acceleration(series) < 0


def test_acceleration_needs_twelve_weeks():
    assert metrics.acceleration([1.0] * 11) is None


def test_cross_sectional_z_ranks_within_the_week():
    result = metrics.cross_sectional_z({"a": 1.0, "b": 2.0, "c": 3.0})
    assert result["b"] == pytest.approx(0.0)
    assert result["a"] < 0 < result["c"]


def test_cross_sectional_z_passes_through_missing_values():
    result = metrics.cross_sectional_z({"a": 1.0, "b": None, "c": 3.0})
    assert result["b"] is None


def test_mean_of_present_ignores_missing_components():
    assert metrics.mean_of_present([1.0, None, 3.0]) == 2.0
    assert metrics.mean_of_present([None, None]) is None
