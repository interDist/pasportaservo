from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings, tag
from django.utils.html import format_html

from factory import Faker
from django.utils import timezone # Added for dynamic_hosting_attributes

from hosting.gravatar import email_to_gravatar
from hosting.models import FamilyMember # Added for FamilyMemberModelProxyTests

from ..assertions import AdditionalAsserts
from ..factories import ProfileFactory, ProfileSansAccountFactory, UserFactory, PlaceFactory # Added PlaceFactory
from .test_managers import TrackingManagersTests


@tag('models', 'profile')
class ProfileModelTests(AdditionalAsserts, TrackingManagersTests, TestCase):
    factory = ProfileFactory

    @classmethod
    def setUpTestData(cls):
        cls.template_first_name = '<span class="first-name">{name}</span>'
        cls.template_last_name = '<span class="last-name">{name}</span>'
        cls.template_username = '<span class="profile-noname">{name}</span>'
        cls.template_joiner = '&ensp;'

        cls.basic_profile = ProfileFactory(first_name="Aaa", last_name="Bbb", with_email=True)

    def test_field_max_lengths(self):
        profile = self.basic_profile
        self.assertEqual(profile._meta.get_field('title').max_length, 5)
        self.assertEqual(profile._meta.get_field('first_name').max_length, 255)
        self.assertEqual(profile._meta.get_field('last_name').max_length, 255)
        self.assertEqual(profile._meta.get_field('pronoun').max_length, 10)

    def test_name(self):
        # A profile with name "Aa" is expected to be "Aa".
        profile = ProfileFactory.build(first_name="Aa", last_name="Bb")
        self.assertEqual(profile.name, "Aa")
        # A profile with name "Aa", names inversed, is expected to be "Aa".
        profile = ProfileFactory.build(first_name="Aa", last_name="Bb", names_inversed=True)
        self.assertEqual(profile.name, "Aa")
        # A profile with name "  Aa  " is expected to be "Aa".
        profile = ProfileFactory.build(first_name="  Aa  ", last_name="Bb")
        self.assertEqual(profile.name, "Aa")
        # A profile with name "" is expected to be "".
        profile = ProfileFactory.build(first_name="", last_name="Bb")
        self.assertEqual(profile.name, "")
        # A profile with name "  " is expected to be "".
        profile = ProfileFactory.build(first_name="  ", last_name="Bb")
        self.assertEqual(profile.name, "")

    def test_fullname(self):
        # Normal profile with both names is expected to be "Aa Bb".
        profile = ProfileFactory.build()
        self.assertEqual(profile.full_name, '{} {}'.format(profile.first_name, profile.last_name))

        # Normal profile with both names, inversed, is expected to be "Bb Aa".
        profile = ProfileFactory.build(names_inversed=True)
        self.assertEqual(profile.full_name, '{} {}'.format(profile.last_name, profile.first_name))

        # A profile with only last name is expected to be "Bb".
        profile = ProfileFactory.build(first_name="")
        self.assertEqual(profile.full_name, profile.last_name)
        # A profile with only last name, names inversed, is expected to be "Bb".
        profile = ProfileFactory.build(first_name="", names_inversed=True)
        self.assertEqual(profile.full_name, profile.last_name)

        # A profile with only first name is expected to be "Aa".
        profile = ProfileFactory.build(last_name="")
        self.assertEqual(profile.full_name, profile.first_name)
        # A profile with only first name, names inversed, is expected to be "Aa".
        profile = ProfileFactory.build(last_name="", names_inversed=True)
        self.assertEqual(profile.full_name, profile.first_name)

        # A profile with no names provided is expected to have empty output.
        profile = ProfileFactory.build(first_name="", last_name="")
        self.assertEqual(profile.full_name, "")
        # A profile with no names provided (inversed) is expected to have empty output.
        profile = ProfileFactory.build(first_name="", last_name="", names_inversed=True)
        self.assertEqual(profile.full_name, "")

    def test_profile_fullname_template(self):
        # Normal profile with both names is expected to be "Aa Bb".
        profile = ProfileFactory()
        self.assertEqual(profile.get_fullname_display(), self.template_joiner.join([
            format_html(self.template_first_name, name=profile.first_name),
            format_html(self.template_last_name, name=profile.last_name),
        ]))

        # Normal profile with both names, inversed, is expected to be "Bb Aa".
        profile = ProfileFactory(names_inversed=True)
        self.assertEqual(profile.get_fullname_display(), self.template_joiner.join([
            format_html(self.template_last_name, name=profile.last_name),
            format_html(self.template_first_name, name=profile.first_name),
        ]))

        # A profile with only last name is expected to be "Bb".
        profile = ProfileFactory(first_name="")
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_last_name, name=profile.last_name)
        ))
        # A profile with only last name, names inversed, is expected to be "Bb".
        profile = ProfileFactory(first_name="", names_inversed=True)
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_last_name, name=profile.last_name)
        ))

        # A profile with only first name is expected to be "Aa".
        profile = ProfileFactory(last_name="")
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_first_name, name=profile.first_name)
        ))
        # A profile with only first name, names inversed, is expected to be "Aa".
        profile = ProfileFactory(last_name="", names_inversed=True)
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_first_name, name=profile.first_name)
        ))

        # A profile with no names provided is expected to be "Uu".
        profile = ProfileFactory(first_name="", last_name="")
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_username, name=profile.user.username.title())
        ))
        # A profile with no names provided, names inversed, is expected to be "Uu".
        profile = ProfileFactory(first_name="", last_name="", names_inversed=True)
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_username, name=profile.user.username.title())
        ))
        # A profile with no user account and no names provided is expected to have empty output.
        profile = ProfileSansAccountFactory(first_name="", last_name="")
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_username, name=" ")
        ))
        # A profile with no user account and no names provided (inversed) is expected to have empty output.
        profile = ProfileSansAccountFactory(first_name="", last_name="", names_inversed=True)
        self.assertEqual(profile.get_fullname_display(), (
            format_html(self.template_username, name=" ")
        ))
        # When 'always', a profile with no user and no names provided is expected to have output of a dash.
        profile = ProfileSansAccountFactory(first_name="", last_name="")
        self.assertEqual(profile.get_fullname_always_display(), (
            format_html(self.template_username, name="--")
        ))
        # When 'always', a profile with no user, no names provided (inversed) is expected to have output of a dash.
        profile = ProfileSansAccountFactory(first_name="", last_name="", names_inversed=True)
        self.assertEqual(profile.get_fullname_always_display(), (
            format_html(self.template_username, name="--")
        ))

    def test_age(self):
        profile = ProfileFactory.build(birth_date=None)
        self.assertRaises(TypeError, lambda: profile.age)
        profile = ProfileFactory.build(birth_date=Faker('date_this_year', before_today=True, after_today=False))
        self.assertEqual(profile.age, 0)
        profile = ProfileFactory.build(birth_date=Faker('date_this_year', before_today=False, after_today=True))
        self.assertEqual(profile.age, 0)
        profile = ProfileFactory.build(birth_date=Faker('date_between', start_date='-725d', end_date='-366d'))
        self.assertEqual(profile.age, 1)
        profile = ProfileFactory.build(birth_date=Faker('date_between', start_date='+366d', end_date='+725d'))
        self.assertEqual(profile.age, -1)
        profile = ProfileFactory.build(birth_date=Faker('date_between', start_date='-6935d', end_date='-6575d'))
        self.assertEqual(profile.age, 18)

        profile = ProfileFactory.build(birth_date=None, death_date=Faker('date_this_year'))
        self.assertRaises(TypeError, lambda: profile.age)
        profile = ProfileFactory.build(
            birth_date=Faker('date_between', start_date='-2000d', end_date='-1825d'),
            death_date=Faker('date_between', start_date='-360d', end_date='-185d'))
        self.assertEqual(profile.age, 4)
        profile = ProfileFactory.build(
            birth_date=Faker('date_between', start_date='-2000d', end_date='-1825d'),
            death_date=Faker('date_between', start_date='+370d', end_date='+545d'))
        self.assertEqual(profile.age, 6)

    @tag('avatar')
    @patch('django.core.files.storage.FileSystemStorage.exists')
    @patch('django.core.files.storage.FileSystemStorage.save')
    def test_avatar_url(self, mock_storage_save, mock_storage_exists):
        # Avatar URL for normal profile is expected to be gravatar url for email.
        profile = ProfileFactory(with_email=True)
        self.assertEqual(
            profile.avatar_url,
            email_to_gravatar(profile.user.email, settings.DEFAULT_AVATAR_URL)
        )
        # Avatar URL for normal profile with invalid email is expected to be gravatar url for email.
        user = UserFactory(invalid_email=True)
        profile = user.profile
        self.assertEqual(
            profile.avatar_url,
            email_to_gravatar(user._clean_email, settings.DEFAULT_AVATAR_URL)
        )

        # Avatar URL for profile with no user account is expected to be gravatar url for fake family member email.
        profile = ProfileSansAccountFactory()
        self.assertEqual(
            profile.avatar_url,
            email_to_gravatar("family.member@pasportaservo.org", settings.DEFAULT_AVATAR_URL)
        )

        # Avatar URL for profile with uploaded profile picture is expected to be the path to the picture.
        fake = Faker._get_faker()
        upfile = SimpleUploadedFile(fake.file_name(extension='png'), fake.image(image_format='png'), 'image/png')
        mock_storage_save.return_value = "test_avatars/xyz.png"
        mock_storage_exists.return_value = True
        profile = ProfileFactory(avatar=upfile)
        self.assertEqual(profile.avatar_url, f"{settings.MEDIA_URL}test_avatars/xyz.png")

    @tag('avatar')
    @patch('django.core.files.storage.FileSystemStorage.exists')
    @patch('django.core.files.storage.FileSystemStorage.save')
    # https://cscheng.info/2018/08/21/mocking-a-file-storage-backend-in-django-tests.html
    def test_avatar_exists(self, mock_storage_save, mock_storage_exists):
        # Profile with no uploaded profile picture is expected to return False.
        profile = ProfileFactory()
        self.assertFalse(profile.avatar_exists())

        # Profile with uploaded profile picture not saved on disk is expected to return False.
        fake = Faker._get_faker()
        upfile = SimpleUploadedFile(fake.file_name(extension='png'), fake.image(image_format='png'), 'image/png')
        mock_storage_save.return_value = "test_avatars/xyz.png"
        mock_storage_exists.return_value = False
        profile = ProfileFactory(avatar=upfile)
        self.assertFalse(profile.avatar_exists())

        # Profile with uploaded profile picture properly saved on disk is expected to return True.
        mock_storage_exists.return_value = True
        self.assertTrue(profile.avatar_exists())

    def test_icon(self):
        profile = self.basic_profile
        self.assertSurrounding(profile.icon, "<span ", "></span>")
        self.assertIn(" title=", profile.icon)

    def test_str(self):
        # Normal profile with both names is expected to be "Aa Bb".
        profile = ProfileFactory()
        self.assertEqual(str(profile), '{} {}'.format(profile.first_name, profile.last_name))

        # A profile with no names provided is expected to be "Anonymous (uu)".
        profile = ProfileFactory(first_name="", last_name="")
        self.assertEqual(str(profile), '{} ({})'.format(str(profile.INCOGNITO), profile.user.username))

        # A profile with no user account and both names is expected to be "Aa Bb".
        profile = ProfileSansAccountFactory()
        self.assertEqual(str(profile), '{} {}'.format(profile.first_name, profile.last_name))
        # A profile with no user account and no names provided is expected to have output of a dash.
        profile = ProfileSansAccountFactory(first_name="", last_name="")
        self.assertEqual(str(profile), "--")

    def test_repr(self):
        profile = self.basic_profile
        self.assertSurrounding(repr(profile), f"<Profile #{profile.pk}:", ">")

    def test_rawdisplay(self):
        # Raw string for profile with a birth date is expected to include the birth year.
        profile = ProfileFactory()
        self.assertEqual(profile.rawdisplay(), f"{str(profile)} ({profile.birth_date.year})")
        profile = ProfileFactory(first_name="", last_name="")
        self.assertEqual(profile.rawdisplay(), f"{str(profile)} ({profile.birth_date.year})")
        profile = ProfileSansAccountFactory()
        self.assertEqual(profile.rawdisplay(), f"{str(profile)} ({profile.birth_date.year})")

        # Raw string for profile without a birth date is expected to include a question mark.
        profile = ProfileFactory(birth_date=None)
        self.assertEqual(profile.rawdisplay(), f"{str(profile)} (?)")
        profile = ProfileFactory(first_name="", last_name="", birth_date=None)
        self.assertEqual(profile.rawdisplay(), f"{str(profile)} (?)")
        profile = ProfileSansAccountFactory(birth_date=None)
        self.assertEqual(profile.rawdisplay(), f"{str(profile)} (?)")

    def test_lt(self):
        p1 = ProfileFactory(first_name="Aa", last_name="Yy")
        p2 = ProfileFactory(first_name="Aa", last_name="Zz")
        p3 = ProfileFactory(first_name="Bb", last_name="Yy")
        p4 = ProfileFactory(first_name="Bb", last_name="Zz")
        self.assertTrue(p1 < p2)
        self.assertTrue(p1 < p3)
        self.assertTrue(p1 < p4)
        self.assertFalse(p2 < p1)
        self.assertFalse(p2 < p3)
        self.assertTrue(p2 < p4)
        self.assertFalse(p3 < p1)
        self.assertTrue(p3 < p2)
        self.assertTrue(p3 < p4)
        self.assertFalse(p4 < p1)
        self.assertFalse(p4 < p2)
        self.assertFalse(p4 < p3)

    def test_get_basic_data(self):
        # The get_basic_data function is expected to be a class (only) method.
        self.assertRaises(AttributeError, lambda: self.basic_profile.get_basic_data(pk=1))
        ProfileModel = self.basic_profile.__class__

        # A DoesNotExist exception is expected for non-existing profiles.
        with self.assertNumQueries(1):
            with self.assertRaises(ObjectDoesNotExist):
                ProfileModel.get_basic_data(pk=-3)
        # The database query is expected to return sufficient data to generate URLs.
        with self.assertNumQueries(1):
            p = ProfileModel.get_basic_data(user=self.basic_profile.user)
            p.autoslug
            p.get_absolute_url()
            p.get_edit_url()
            p.get_admin_url()
        with self.assertNumQueries(1):
            p = ProfileModel.get_basic_data(pk=self.basic_profile.pk)
            p.autoslug
            p.get_absolute_url()
            p.get_edit_url()
            p.get_admin_url()
        # Additional database queries are expected when further data of profile is used.
        with self.assertNumQueries(5):
            p = ProfileModel.get_basic_data(email=self.basic_profile.email)
            p.age
            p.email_visibility

    def test_get_basic_data_from_request(self):
        request = RequestFactory().get('/pro/filo')
        request.user = self.basic_profile.user  # Simulate a logged-in user.
        other_profile = ProfileFactory(with_email=True)
        other_user = UserFactory(profile=None)
        ProfileModel = self.basic_profile.__class__

        default_200_result = dict.fromkeys((None, True, False), {'queries': 1, 'exists': True})
        default_404_result = dict.fromkeys((None, True, False), {'queries': 1, 'exists': False})
        test_config = [
            {
                'tag': "same user",
                'params': {'user': self.basic_profile.user},
                'result': {
                    None: {
                        'queries': 1, 'exists': True,
                    },
                    False: {
                        'queries': 0, 'exists': False,
                    },
                    True: {
                        'queries': 1, 'exists': True,
                    },
                },
            }, {
                'tag': "same user; user_id",
                'params': {'user_id': self.basic_profile.user_id},
                'result': {
                    None: {
                        'queries': 1, 'exists': True,
                    },
                    False: {
                        'queries': 0, 'exists': False,
                    },
                    True: {
                        'queries': 1, 'exists': True,
                    },
                },
            }, {
                'tag': "same profile; email",
                'params': {'email': self.basic_profile.email},
                'result': default_200_result,
            }, {
                'tag': "other profile; user",
                'params': {'user': other_profile.user},
                'result': default_200_result,
            }, {
                'tag': "other profile; pk",
                'params': {'pk': other_profile.pk},
                'result': default_200_result,
            }, {
                'tag': "other user",
                'params': {'user': other_user},
                'result': default_404_result,
            },
        ]

        def single_case_test(case):
            for test_data in test_config:
                with self.subTest(tag=test_data['tag']):
                    with self.assertNumQueries(test_data['result'][case]['queries']):
                        assert_exception = (
                            self.assertNotRaises if test_data['result'][case]['exists']
                            else self.assertRaises
                        )
                        with assert_exception(ObjectDoesNotExist):
                            ProfileModel.get_basic_data(request, **test_data['params'])

        # When the request does not contain information about the user's profile, the
        # database is expected to be queried.
        with self.subTest(case="info missing"):
            single_case_test(None)

        # When it is already known that the user does not have a profile, the database
        # is expected to be queried only when a different user's profile is requested,
        # or the filtering parameters do not include a user identification.
        request.user_has_profile = False
        with self.subTest(case="no profile"):
            single_case_test(False)

        # When it is already known that the user has a profile, the database is
        # expected to be queried in all cases.
        request.user_has_profile = True
        with self.subTest(case="has a profile"):
            single_case_test(True)

    def test_absolute_url(self):
        profile = self.basic_profile
        expected_urls = {
            'eo': '/profilo/{}/{}/',
            'en': '/profile/{}/{}/',
        }
        for lang in expected_urls:
            with override_settings(LANGUAGE_CODE=lang):
                with self.subTest(LANGUAGE_CODE=lang):
                    self.assertEqual(
                        profile.get_absolute_url(),
                        expected_urls[lang].format(profile.pk, profile.first_name.lower())
                    )

    def test_edit_url(self):
        profile = self.basic_profile
        expected_urls = {
            'eo': '/profilo/{}/{}/aktualigi/',
            'en': '/profile/{}/{}/edit/',
        }
        for lang in expected_urls:
            with override_settings(LANGUAGE_CODE=lang):
                with self.subTest(LANGUAGE_CODE=lang):
                    self.assertEqual(
                        profile.get_edit_url(),
                        expected_urls[lang].format(profile.pk, profile.first_name.lower())
                    )

    @override_settings(LANGUAGE_CODE='en')
    def test_admin_url(self):
        profile = self.basic_profile
        self.assertEqual(
            profile.get_admin_url(),
            '/management/hosting/profile/{}/change/'.format(profile.pk)
        )


@tag('models', 'profile')
class PreferencesModelTests(AdditionalAsserts, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = ProfileFactory()

    def test_repr(self):
        self.assertTrue(hasattr(self.profile, 'pref'))
        self.assertSurrounding(repr(self.profile.pref), "<Preferences", f"|p#{self.profile.pk}>")

    def test_defaults(self):
        self.assertTrue(hasattr(self.profile, 'pref'))
        self.assertIs(
            self.profile.pref._meta.get_field('public_listing').default,
            True
        )
        self.assertIs(
            self.profile.pref._meta.get_field('site_analytics_consent').default,
            None
        )

    def test_mark_invalid_emails_scenarios(self):
        user1 = UserFactory(email="valid1@example.com")
        profile1 = user1.profile
        profile1.email = "public_valid1@example.com"
        profile1.save()

        user2 = UserFactory(email="valid2@example.com")
        # Profile2 will not have a public email initially

        user3 = UserFactory(email=f"{settings.INVALID_PREFIX}already_invalid@example.com")
        profile3 = user3.profile
        profile3.email = f"{settings.INVALID_PREFIX}public_already_invalid@example.com"
        profile3.save()

        # Test with empty list
        Profile.mark_invalid_emails([])
        user1.refresh_from_db(); profile1.refresh_from_db()
        self.assertEqual(user1.email, "valid1@example.com")
        self.assertEqual(profile1.email, "public_valid1@example.com")

        # Test with some valid, some already invalid, some non-existent
        emails_to_mark = [
            "valid1@example.com", # Will be marked
            "public_valid1@example.com", # Will be marked
            f"{settings.INVALID_PREFIX}already_invalid@example.com", # Already marked, no change
            "nonexistent@example.com" # No effect
        ]
        Profile.mark_invalid_emails(emails_to_mark)

        user1.refresh_from_db(); profile1.refresh_from_db()
        user3.refresh_from_db(); profile3.refresh_from_db()

        self.assertEqual(user1.email, f"{settings.INVALID_PREFIX}valid1@example.com")
        self.assertEqual(profile1.email, f"{settings.INVALID_PREFIX}public_valid1@example.com")
        self.assertEqual(user3.email, f"{settings.INVALID_PREFIX}already_invalid@example.com") # Unchanged
        self.assertEqual(profile3.email, f"{settings.INVALID_PREFIX}public_already_invalid@example.com") # Unchanged

        # Ensure user2's email which was not in the list is unchanged
        user2.refresh_from_db()
        self.assertEqual(user2.email, "valid2@example.com")


    def test_mark_valid_emails_scenarios(self):
        user1 = UserFactory(email=f"{settings.INVALID_PREFIX}invalid1@example.com")
        profile1 = user1.profile
        profile1.email = f"{settings.INVALID_PREFIX}public_invalid1@example.com"
        profile1.save()

        user2 = UserFactory(email=f"{settings.INVALID_PREFIX}invalid2@example.com")
        # Profile2 will not have a public email initially

        user3 = UserFactory(email="already_valid@example.com")
        profile3 = user3.profile
        profile3.email = "public_already_valid@example.com"
        profile3.save()

        # Test with empty list
        Profile.mark_valid_emails([])
        user1.refresh_from_db(); profile1.refresh_from_db()
        self.assertEqual(user1.email, f"{settings.INVALID_PREFIX}invalid1@example.com")
        self.assertEqual(profile1.email, f"{settings.INVALID_PREFIX}public_invalid1@example.com")

        # Test with some invalid, some already valid, some non-existent
        emails_to_unmark = [
            f"{settings.INVALID_PREFIX}invalid1@example.com", # Will be unmarked
            f"{settings.INVALID_PREFIX}public_invalid1@example.com", # Will be unmarked
            "already_valid@example.com", # Already valid, no change
            "nonexistent@example.com" # No effect
        ]
        Profile.mark_valid_emails(emails_to_unmark)

        user1.refresh_from_db(); profile1.refresh_from_db()
        user3.refresh_from_db(); profile3.refresh_from_db()

        self.assertEqual(user1.email, "invalid1@example.com")
        self.assertEqual(profile1.email, "public_invalid1@example.com")
        self.assertEqual(user3.email, "already_valid@example.com") # Unchanged
        self.assertEqual(profile3.email, "public_already_valid@example.com") # Unchanged

        # Ensure user2's email which was not in the list is unchanged
        user2.refresh_from_db()
        self.assertEqual(user2.email, f"{settings.INVALID_PREFIX}invalid2@example.com")

    def test_confirm_all_info_no_related_objects(self):
        profile = ProfileFactory(user=UserFactory(profile=None)) # Ensure no existing relations from factory
        self.assertIsNone(profile.confirmed_on)

        profile.confirm_all_info(True)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.confirmed_on)

        profile.confirm_all_info(False)
        profile.refresh_from_db()
        self.assertIsNone(profile.confirmed_on)

    def test_dynamic_hosting_attributes(self):
        profile = ProfileFactory()
        self.assertEqual(profile.has_places_for_hosting, 0)
        self.assertEqual(profile.has_places_for_meeting, 0)
        self.assertEqual(profile.is_hosting, 0) # is_hosting is an alias for has_places_for_hosting
        self.assertEqual(profile.is_meeting, 0)
        self.assertEqual(profile.has_places_for_in_book, 0)
        self.assertEqual(profile.is_accepting_guests, 0)

        # Add a place for hosting
        place1 = ProfileFactory.create_place_for(profile, available=True, in_book=True)
        profile.refresh_from_db() # Refresh to clear cached properties if any, though not strictly needed for this
        # Re-fetch profile to ensure Place relations are seen by the properties if they re-query
        profile_reloaded = Profile.objects.get(pk=profile.pk)

        self.assertEqual(profile_reloaded.has_places_for_hosting, 1)
        self.assertEqual(profile_reloaded.is_hosting, 1)
        self.assertEqual(profile_reloaded.has_places_for_in_book, 1)
        self.assertEqual(profile_reloaded.is_accepting_guests, 1)
        self.assertEqual(profile_reloaded.has_places_for_meeting, 0) # Not meeting

        # Add a place for meeting only
        place2 = ProfileFactory.create_place_for(profile, available=False, tour_guide=True, in_book=False)
        profile_reloaded = Profile.objects.get(pk=profile.pk)
        self.assertEqual(profile_reloaded.has_places_for_hosting, 1)
        self.assertEqual(profile_reloaded.has_places_for_meeting, 1)
        self.assertEqual(profile_reloaded.is_accepting_guests, 1) # Still 1 from place1
        self.assertEqual(profile_reloaded.has_places_for_in_book, 1) # Still 1 from place1

        # Make place1 not available for hosting
        place1.available = False
        place1.save()
        profile_reloaded = Profile.objects.get(pk=profile.pk)
        self.assertEqual(profile_reloaded.has_places_for_hosting, 0)
        self.assertEqual(profile_reloaded.is_hosting, 0)
        self.assertEqual(profile_reloaded.is_accepting_guests, 0) # No hosting places accept guests
        self.assertEqual(profile_reloaded.has_places_for_meeting, 1) # place2 still meeting
        self.assertEqual(profile_reloaded.has_places_for_in_book, 0) # place1 was in book but now not available

        # Delete place2
        place2.deleted_on = timezone.now()
        place2.save()
        profile_reloaded = Profile.objects.get(pk=profile.pk)
        self.assertEqual(profile_reloaded.has_places_for_meeting, 0)


@tag('models', 'profile', 'familymember')
class FamilyMemberModelProxyTests(TestCase):
    def test_owner_property_no_user_no_current_owner(self):
        # Create a Profile instance that would represent a FamilyMember without a user account
        family_member_profile = ProfileSansAccountFactory()
        # Cast to FamilyMember proxy model
        family_member_instance = FamilyMember.objects.get(pk=family_member_profile.pk)

        # Ensure _current_owner is not set
        if hasattr(family_member_instance, '_current_owner'):
            delattr(family_member_instance, '_current_owner')

        self.assertIsNone(family_member_instance.user_id)
        self.assertIsNone(family_member_instance.owner,
                          "Owner should be None if no user_id and _current_owner is not set.")

    def test_owner_property_with_user_ignores_external_set(self):
        # Create a Profile instance that has a user account
        user_profile = ProfileFactory()
        # Cast to FamilyMember proxy model
        family_member_instance = FamilyMember.objects.get(pk=user_profile.pk)

        self.assertIsNotNone(family_member_instance.user_id)

        # Try to set _current_owner externally
        another_profile = ProfileFactory()
        family_member_instance.owner = another_profile # Uses the setter

        # Owner should still be self (user_profile) because user_id exists
        self.assertEqual(family_member_instance.owner, user_profile,
                         "Owner should be self if user_id exists, ignoring external _current_owner.")
        self.assertNotEqual(family_member_instance.owner, another_profile)

    def test_owner_property_no_user_with_current_owner(self):
        family_member_profile = ProfileSansAccountFactory()
        family_member_instance = FamilyMember.objects.get(pk=family_member_profile.pk)

        current_owner_profile = ProfileFactory()
        family_member_instance.owner = current_owner_profile # Uses the setter

        self.assertIsNone(family_member_instance.user_id)
        self.assertEqual(family_member_instance.owner, current_owner_profile,
                         "Owner should be _current_owner if no user_id and _current_owner is set.")
