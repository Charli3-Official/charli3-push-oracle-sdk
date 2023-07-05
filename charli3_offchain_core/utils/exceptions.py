"""Custom exceptions for the application. """


class CollateralException(Exception):
    """Custom exception for handling collateral-related issues."""


class TxSubmissionFailedException(Exception):
    """Custom exception for handling transaction submission failures."""
