""" Business logic for calculating the aggregation and consensus."""
from typing import List, Tuple
from statistics import median
import random

factor_resolution: int = 10000


def random_median(numbers: List[int]):
    """
    This function takes a list of numbers as an input and returns the median of the list.
    The median is calculated as the middle value when the list is sorted.
    When the list has an even number of elements, the median is calculated as a random element
    from the middle two elements.

    Parameters:
    numbers (list): a list of numerical values

    Returns:
    float: median value of the list

    Example:
    median([1, 2, 3, 4, 5, 6]) -> 3 or 4 (randomly)

    """
    numbers.sort()
    if len(numbers) % 2 == 0:
        median1 = numbers[len(numbers) // 2]
        median2 = numbers[len(numbers) // 2 - 1]
        result = random.choice([median1, median2])
    else:
        result = numbers[len(numbers) // 2]
    return result


def aggregation(
    mad_multi: int, diver: int, feeds: List[int]
) -> Tuple[int, List[int], int, int]:
    """
    Calculate the median, onConsensus, lower bound, and upper bound of the aggregated feeds.

    Parameters:
    - mad_multi: the MAD (mean absolute deviation)
    - diver: the divergence
    - feeds: the feeds to be aggregated

    Returns:
    - A 4-tuple containing the median, onConsensus, lower bound, and upper bound of the
      aggregated feeds.
    """

    def left_filter(feeds: List[int]) -> Tuple[int, List[int]]:
        """
        Filter the given feeds and return the lower bound and the values on consensus.

        Parameters:
        - feeds: the feeds to be filtered

        Returns:
        - A 2-tuple containing the lower bound and the values on consensus.
        """
        nonlocal mad, med
        for i, feed in enumerate(feeds):
            if is_in_consensus(mad_multi, diver, mad, med, feed):
                return feed, feeds[i:]
            return 0, []

    def is_in_consensus(
        mad_multiplier: int, div: int, mad: int, med: int, d: int
    ) -> bool:
        """
        Check if a value is accepted according to the consensus mechanism.

        Parameters:
        - mad_multiplier: the MAD multiplier
        - div: the divergence
        - mad: the MAD
        - med: the median
        - d: the value to be checked

        Returns:
        - True if the value is accepted by the consensus mechanism, False otherwise.
        """
        abs_diff = abs(med - d) * factor_resolution
        deviation = abs_diff // med
        return (abs_diff <= mad_multiplier * mad) or (deviation < div)

    s_feeds = sorted(feeds)
    med = int(median(s_feeds))
    mad = median(sorted([abs(f - med) for f in s_feeds]))
    lower, s_feeds_ = left_filter(s_feeds)
    upper, on_consensus = left_filter(s_feeds_[::-1])
    return med, on_consensus, lower, upper
