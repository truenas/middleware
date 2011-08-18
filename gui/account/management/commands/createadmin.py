import sys
from optparse import make_option

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, UNUSABLE_PASSWORD

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--email', action='store', dest='email', type='string',
            help=''),
    )
    help = "Creates a new admin user with UNUSABLE_PASSWORD"
    usage_str = "Usage: ./manage.py createadmin [--email email]"

    def handle(self, email=None, verbosity=1, **options):

        if User.objects.filter(username__exact='admin').exists():
            print >>sys.stderr, "The admin user already exists"
            return None

        admin = User()
        admin.username = 'admin'
        admin.password = UNUSABLE_PASSWORD
        admin.is_superuser = True
        admin.is_staff = True
        if email is None:
            email = 'myemail@example.com'
        admin.email = email
        admin.save()
