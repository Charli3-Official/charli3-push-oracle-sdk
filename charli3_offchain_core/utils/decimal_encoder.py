""" DecimalEncoder class for encoding Decimal objects to float for JSON serialization"""

import json
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """DecimalEncoder class for encoding Decimal objects to float for JSON serialization"""

    def default(self, obj):  # pylint: disable=W0237
        """Default method for encoding Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)  # Convert Decimal to float for JSON serialization
        return super(DecimalEncoder, self).default(obj)
