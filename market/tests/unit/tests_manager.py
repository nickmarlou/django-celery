from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time
from mixer.backend.django import mixer

from elk.utils.testing import TestCase, create_customer, create_teacher
from lessons import models as lessons
from market import models
from products import models as products


@freeze_time('2032-11-01')
class TestClassManager(TestCase):
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

    def test_nearest_scheduled_ok(self):
        c = self._schedule()
        c1 = self.customer.classes.nearest_scheduled()
        self.assertEqual(c1, c)

    def test_nearest_scheduled_ordering(self):
        c2 = self._schedule(date=self.tzdatetime(2032, 12, 1, 11, 30))
        self._schedule(date=self.tzdatetime(2032, 12, 5, 11, 30))

        c_found = self.customer.classes.nearest_scheduled()
        self.assertEquals(c_found, c2)

    def test_nearest_scheduled_fail(self):
        """
        Run without any scheduled class
        """
        c = self._schedule()
        c.cancel()
        c.save()

        self.assertIsNone(self.customer.classes.nearest_scheduled())  # should not throw anything

    @override_settings(TIME_ZONE='UTC')
    def test_starting_soon(self):
        self._schedule()
        with freeze_time('2032-12-01 10:00'):
            self.assertEquals(self.customer.classes.starting_soon(timedelta(minutes=89)).count(), 0)
            self.assertEquals(self.customer.classes.starting_soon(timedelta(minutes=91)).count(), 1)

    def test_hosted_lessons_starting_soon(self):
        teacher = create_teacher()
        lesson = mixer.blend(lessons.MasterClass, host=teacher, photo=mixer.RANDOM)
        mixer.blend('timeline.Entry', lesson=lesson, teacher=teacher, start=self.tzdatetime(2032, 12, 25, 12, 00))

        hosted_lessons_starting_soon = self.customer.classes.hosted_lessons_starting_soon()
        self.assertEqual(len(hosted_lessons_starting_soon), 1)
        self.assertEqual(hosted_lessons_starting_soon[0], lesson)

    def test_nearest_dont_return_past_classes(self):
        """
        Test if clases.nearest_scheduled() does not return classes in the past
        """
        self._schedule(date=self.tzdatetime(2032, 12, 1, 11, 30))
        c2 = self._schedule(date=self.tzdatetime(2032, 12, 5, 11, 30))
        c_found = self.customer.classes.nearest_scheduled(date=self.tzdatetime(2032, 12, 3, 11, 30))  # 2 days later, then the fist sccheduled class
        self.assertEquals(c_found, c2)

    def test_available_lesson_types(self):
        lesson_types = self.customer.classes.purchased_lesson_types()
        self.assertEquals(len(lesson_types), 5)  # if you have defined a new lesson, fill free to increase this value, it's ok

        self.assertIn(lessons.OrdinaryLesson.get_contenttype(), lesson_types)
        self.assertIn(lessons.MasterClass.get_contenttype(), lesson_types)

    def test_lesson_type_sorting(self):  # noqa
        """
        Planning dates should be sorted with the in-class defined sort order
        """
        lesson_types = self.customer.classes.purchased_lesson_types()

        sort_order = {}
        for m in ContentType.objects.filter(app_label='lessons'):
            Model = m.model_class()
            if not hasattr(Model, 'sort_order'):  # non-sortable models are possibly not lessons
                continue

            order = Model.sort_order()
            if order:
                sort_order[order] = Model

        sorted_lessons = []
        for i in sorted(list(sort_order.keys())):
            sorted_lessons.append(sort_order[i])

        for lesson_type in lesson_types:
            ordered_lesson = sorted_lessons.pop(0)
            self.assertEquals(lesson_type.model_class(), ordered_lesson)

    def test_find_student_classes_nothing(self):
        self.subscription.delete()
        no_students = models.Class.objects.find_student_classes(lesson_type=lessons.OrdinaryLesson.get_contenttype())
        self.assertEquals(len(no_students), 0)

    def test_find_student_classes(self):
        single = models.Class.objects.find_student_classes(lesson_type=lessons.OrdinaryLesson.get_contenttype())
        self.assertEqual(single[0].customer, self.customer)

    @freeze_time('2032-12-05 01:00')
    def test_dates_for_planning_today(self):
        timezone.activate('Europe/Moscow')
        dates = list(self.customer.classes.dates_for_planning())
        self.assertEquals(len(dates), 14)  # should return next two weeks

        self.assertEquals(dates[0], self.tzdatetime('UTC', 2032, 12, 5, 1, 0))  # the first day should be today
        # fill free to modify this if you've changed the booking lag

    @freeze_time('2032-12-05 02:00')
    @override_settings(PLANNING_DELTA=timedelta(hours=23))
    def test_dates_for_planning_tomorrow(self):
        timezone.activate('US/Eastern')

        dates = list(self.customer.classes.dates_for_planning())

        self.assertEquals(len(dates), 14)
        self.assertEquals(dates[0], self.tzdatetime('UTC', 2032, 12, 6, 2, 0))  # the first day should be tomorrow, because no lessons can by planned today after 02:00

    def test_mark_as_fully_used(self):
        c = self._schedule()
        c.mark_as_fully_used()
        c.refresh_from_db()
        self.assertTrue(c.is_fully_used)

    def test_renew(self):
        c = self._schedule()
        c.mark_as_fully_used()
        c.save()
        self.assertTrue(c.is_fully_used)
        self.assertIsNotNone(c.timeline)

        c.renew()
        c.save()

        self.assertFalse(c.is_fully_used)
        self.assertIsNone(c.timeline)

    def test_due_queryset_based_on_buy_date(self):
        self.assertEqual(models.Subscription.objects.due().count(), 0)

        with freeze_time('2032-12-20'):
            self.assertEqual(models.Subscription.objects.due().count(), 1)

    def test_due_queryset_based_on_first_lesson_date(self):
        self.assertEqual(models.Subscription.objects.due().count(), 0)

        self.subscription.first_lesson_date = self.tzdatetime(2011, 12, 1, 12, 0)  # set first lesson date to far-far ago
        self.subscription.save()

        self.assertEqual(models.Subscription.objects.due().count(), 1)

    def test_due_queryset_ignores_buy_date_of_lessons_that_have_first_lesson_date(self):
        self.subscription.buy_date = self.tzdatetime(2011, 12, 1, 12, 0)  # far-far ago
        self.subscription.first_lesson_date = self.tzdatetime(2032, 10, 29, 12, 0)  # almost yesterday

        self.subscription.save()

        self.assertEqual(models.Subscription.objects.due().count(), 0)
