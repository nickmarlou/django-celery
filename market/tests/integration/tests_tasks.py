from unittest.mock import patch
from datetime import timedelta

from django.core import mail
from freezegun import freeze_time
from mixer.backend.django import mixer

from elk.utils.testing import TestCase, create_customer, create_teacher
from timeline.tasks import notify_15min_to_class
from market.tasks import notify_customers_with_forgotten_subscriptions
from lessons import models as lessons
from market import models
from products import models as products


@freeze_time('2032-11-01')
class TestForgottenSubscriptionsNotificationEmail(TestCase):
    fixtures = ('lessons', 'products')
    TEST_PRODUCT_ID = 1

    @classmethod
    def setUpTestData(cls):
        cls.customer = create_customer()
        cls.product = products.Product1.objects.get(pk=cls.TEST_PRODUCT_ID)
        cls.product.duration = timedelta(days=42)

    def setUp(self):
        self.subscription = models.Subscription(
            customer=self.customer,
            product=self.product,
            buy_price=150,
        )
        self.subscription.save()

    def _schedule(self, lesson_type=None, date=None):
        if date is None:
            date = self.tzdatetime(2032, 12, 1, 11, 30)

        if lesson_type is None:
            lesson_type = lessons.OrdinaryLesson.get_contenttype()

        c = self.customer.classes.filter(lesson_type=lesson_type, is_scheduled=False).first()
        """
        If this test will fail when you change the SortingHat behaviour, just
        replace the above lines with the SortingHat invocation
        """
        c.schedule(
            teacher=create_teacher(works_24x7=True),
            date=date,
            allow_besides_working_hours=True,
        )
        c.save()
        self.assertTrue(c.is_scheduled)
        return c

    def test_notification_with_subscriptions_forgotten_since_purchase(self):
        with freeze_time('2032-11-5'):
            notify_customers_with_forgotten_subscriptions()
            self.assertEqual(len(mail.outbox), 0)

        with freeze_time('2032-11-10'):
            notify_customers_with_forgotten_subscriptions()
            self.assertEqual(len(mail.outbox), 1)
            out_emails = [outbox.to[0] for outbox in mail.outbox]
            self.assertIn(self.customer.email, out_emails)

    def test_notification_with_subscriptions_forgotten_since_last_class(self):
        c = self._schedule()

        with freeze_time('2032-12-10'):
            notify_customers_with_forgotten_subscriptions()
            self.assertTrue(any(['we miss you' in message.subject for message in mail.outbox]))