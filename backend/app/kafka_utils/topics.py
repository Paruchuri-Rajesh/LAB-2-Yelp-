class Topics:
    REVIEW_CREATED = "review.created"
    REVIEW_UPDATED = "review.updated"
    REVIEW_DELETED = "review.deleted"

    RESTAURANT_CREATED = "restaurant.created"
    RESTAURANT_UPDATED = "restaurant.updated"
    RESTAURANT_CLAIMED = "restaurant.claimed"

    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"

    BOOKING_STATUS = "booking.status"

    @classmethod
    def all(cls) -> list[str]:
        return [
            cls.REVIEW_CREATED, cls.REVIEW_UPDATED, cls.REVIEW_DELETED,
            cls.RESTAURANT_CREATED, cls.RESTAURANT_UPDATED, cls.RESTAURANT_CLAIMED,
            cls.USER_CREATED, cls.USER_UPDATED, cls.BOOKING_STATUS,
        ]
