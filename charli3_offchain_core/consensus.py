"""Business logic for calculating the aggregation and consensus."""
from typing import List, Tuple
from statistics import median
import random

FACTOR_RESOLUTION = 10000


def random_median(numbers: List[int]) -> int:
    """Calculate the median from a list of numbers.

    The median is calculated as the middle value when the list is sorted.
    When the list has an even number of elements, the median is calculated
    as a random element from the middle two elements.

    Args:
        numbers (List[int]): A list of numerical values.

    Returns:
        int: Median value of the list.

    Examples:
        median([1, 2, 3, 4, 5, 6]) -> 3 or 4 (randomly)
    """
    numbers.sort()
    if len(numbers) % 2 == 0:
        median_1 = numbers[len(numbers) // 2]
        median_2 = numbers[len(numbers) // 2 - 1]
        result = random.choice([median_1, median_2])
    else:
        result = numbers[len(numbers) // 2]
    return result


def aggregation(
    iqr_multiplier: int, diver_in_percentage: int, node_feeds: List[int]
) -> Tuple[int, List[int], int, int]:
    """Calculate the median, on_consensus, lower bound, and upper bound of the aggregated feeds.

    Args:
        iqr_multiplier (int): k value for outlier detection. The recommended value is 0 (1.5),
                        the onchain code has the range restriction between 0 - 4
        diver (int): the divergence in percentage (10000)
        feeds (List[int]): the feeds to be aggregated

    Returns:
        Tuple[int, List[int], int, int]: A 4-tuple containing the median, on_consensus, lower bound,
                                         and upper bound of the aggregated feeds.
    """
    sort_feeds = sorted(node_feeds)
    _median = int(median(sort_feeds))
    l_feeds = len(sort_feeds)
    on_consensus = consensus(
        sort_feeds, l_feeds, _median, iqr_multiplier, diver_in_percentage
    )
    lower = on_consensus[0]
    upper = on_consensus[-1]
    return _median, on_consensus, lower, upper


def consensus(
    node_feeds: List[int],
    l_feeds: int,
    _median: int,
    iqr_multiplier: int,
    diver_in_percentage: int,
) -> List[int]:
    """Calculate the values in the consensus.

    Args:
        node_feeds (List[int]): Sorted node feeds list
        l_feeds (int): Length of the node_feeds
        _median (int): Median value among node_feeds
        iqr_multiplier (int): k value for outlier detection. The recommended value is 2,
                              the onchain code has the range restriction between 1 - N
        diver_in_percentage (int): Percentage of divergence from the median allowed to
                                   participate in the consensus

    Returns:
        List[int]: List of consensus values.
    """

    def divergence_from_median(node_feed: int) -> int:
        return (node_feed * FACTOR_RESOLUTION) // _median

    first_quart = first_quartile(node_feeds, l_feeds)
    third_quart = third_quartile(node_feeds, l_feeds)

    interquartile_range = third_quart - first_quart
    lower_bound = first_quart - (iqr_multiplier * interquartile_range)
    upper_bound = third_quart + (iqr_multiplier * interquartile_range)

    return [
        x
        for x in node_feeds
        if divergence_from_median(abs(x - _median)) <= diver_in_percentage
        and lower_bound <= x <= upper_bound
    ]


def first_quartile(node_feeds: List[int], l_feeds: int) -> float:
    """Calculate the first quartile of the input node feeds.

    Args:
        node_feeds (List[int]): Sorted node feeds list
        l_feeds (int): Length of the node_feeds

    Returns:
        float: Node feeds' first quartile
    """
    mid = l_feeds // 2
    return median(node_feeds[:mid])


def third_quartile(node_feeds: List[int], l_feeds: int) -> float:
    """Calculate the third quartile of the input node feeds.

    Args:
        node_feeds (List[int]): Sorted node feeds list
        l_feeds (int): Length of the node_feeds

    Returns:
        float: Node feeds' third quartile
    """
    mid = (l_feeds // 2) + (l_feeds % 2)
    return median(node_feeds[mid:])
