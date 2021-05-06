from elk.celery import app as celery

from market.models import Subscription
from mailer.owl import Owl


@celery.task
def notify_customers_with_forgotten_subscriptions():
    """
    This task send email notification to customers
    about their active, but forgotten subscriptions
    """
    forgotten_subscriptions = Subscription.objects.forgotten()

    for subscription in forgotten_subscriptions:
        customer_email = subscription.customer.email
        
        if customer_email:
            owl = Owl(
                template='mail/subscription/student/forgotten.html',
                ctx={
                    's': subscription,
                },
                to=[customer_email],
            )
            owl.send()

