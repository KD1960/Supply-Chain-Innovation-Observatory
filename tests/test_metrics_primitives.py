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
    # The tail has to change the answer, or this guards nothing. Eleven zeroes
    # and a spike, then three holes: carrying the spike forward pulls the mean
    # up from 1/15 to 40/15 and halves the z-score. Dropping the holes instead
    # would give 3.3166 — the value the same series without holes produces two
    # tests above.
    assert metrics.zscore([0.0] * 11 + [10.0] + [None] * 3) == pytest.approx(1.6583, abs=1e-3)


# A source outage inside the warm-up window used to be scored as though the
# padding were data: the repeated value shrinks the spread and inflates |z|,
# and that inflated z propagates into stages, SAI, LFI and momentum.
OUTAGE = [1.0, 2.0, 3.0, 4.0, 5.0] + [None] * 10


def test_zscore_does_not_count_carried_forward_padding_as_history():
    assert metrics.zscore(OUTAGE) is None


def test_mean_of_present_ignores_missing_components():
    assert metrics.mean_of_present([1.0, None, 3.0]) == 2.0
    assert metrics.mean_of_present([None, None]) is None
