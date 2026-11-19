"""Tests for shared feature-service validation primitives."""

import unittest

from backend.app.validation import positive_int
from backend.app.booking import BookingRequestError
from backend.app.booking_cancellation import BookingCancellationError
from backend.app.booking_payment import PaymentConfirmationError


class SharedPositiveIntegerValidationTests(unittest.TestCase):
    def test_accepts_canonical_positive_integer_values(self):
        self.assertEqual(positive_int(7, "booking", BookingRequestError), 7)
        self.assertEqual(positive_int("12", "booking", BookingRequestError), 12)

    def test_rejects_booleans_zero_negative_and_noncanonical_values(self):
        for value in (True, False, 0, -1, "01", "1.0", None, [], 1.5):
            with self.subTest(value=value):
                with self.assertRaises(BookingRequestError):
                    positive_int(value, "booking", BookingRequestError, "Select")

    def test_preserves_feature_specific_exception_types_and_wording(self):
        with self.assertRaisesRegex(PaymentConfirmationError, "Enter a valid booking"):
            positive_int("bad", "booking", PaymentConfirmationError)
        with self.assertRaisesRegex(BookingCancellationError, "Enter a valid passenger"):
            positive_int(0, "passenger", BookingCancellationError)
        with self.assertRaisesRegex(BookingRequestError, "Select a valid train"):
            positive_int(False, "train", BookingRequestError, "Select")


if __name__ == "__main__":
    unittest.main()
