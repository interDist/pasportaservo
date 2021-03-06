import logging
import re
from collections import namedtuple
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS
from django.core.mail import send_mail
from django.http import (
    HttpResponse, HttpResponseRedirect, JsonResponse, QueryDict,
)
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from braces.views import FormInvalidMessageMixin

from core.auth import ANONYMOUS, OWNER, SUPERVISOR, AuthMixin
from core.forms import UserRegistrationForm
from core.models import SiteConfiguration

from ..forms import (
    PlaceBlockForm, PlaceCreateForm, PlaceForm,
    PlaceLocationForm, UserAuthorizedOnceForm, UserAuthorizeForm,
)
from ..mixins import (
    CreateMixin, DeleteMixin, PlaceMixin, PlaceModifyMixin,
    ProfileIsUserMixin, ProfileModifyMixin, UpdateMixin,
)
from ..models import Place, Profile

User = get_user_model()


class PlaceCreateView(
        CreateMixin, AuthMixin, ProfileIsUserMixin, ProfileModifyMixin, PlaceModifyMixin, FormInvalidMessageMixin,
        generic.CreateView):
    model = Place
    form_class = PlaceCreateForm
    form_invalid_message = _("The data is not saved yet! Note the specified errors.")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['profile'] = self.create_for
        return kwargs


class PlaceUpdateView(
        UpdateMixin, AuthMixin, PlaceMixin, ProfileModifyMixin, PlaceModifyMixin, FormInvalidMessageMixin,
        generic.UpdateView):
    form_class = PlaceForm
    form_invalid_message = _("The data is not saved yet! Note the specified errors.")


class PlaceLocationUpdateView(
        UpdateMixin, AuthMixin, PlaceMixin,
        generic.UpdateView):
    form_class = PlaceLocationForm
    update_partial = True

    def get_success_url(self, *args, **kwargs):
        return reverse_lazy('place_detail_verbose', kwargs={'pk': self.object.pk})


class PlaceDeleteView(
        DeleteMixin, AuthMixin, PlaceMixin, ProfileModifyMixin,
        generic.DeleteView):
    pass


class PlaceDetailView(AuthMixin, PlaceMixin, generic.DetailView):
    """
    Details about a place; allows also anonymous (unauthenticated) user access.
    For such users, the registration form will be displayed.
    """
    model = Place
    minimum_role = ANONYMOUS
    verbose_view = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['owner_phones'] = self.object.owner.phones.filter(deleted=False)
        context['register_form'] = UserRegistrationForm
        context['blocking'] = self.calculate_blocking(self.object)
        return context

    @staticmethod
    def calculate_blocking(place):
        block = {}
        today = date.today()
        if place.is_blocked:
            block['enabled'] = True
            if place.blocked_from and place.blocked_from > today:
                block['display_from'] = True
                block['format_from'] = "MONTH_DAY_FORMAT" if place.blocked_from.year == today.year else "DATE_FORMAT"
            if place.blocked_until and place.blocked_until >= today:
                block['display_until'] = True
                block['format_until'] = "MONTH_DAY_FORMAT" if place.blocked_until.year == today.year else "DATE_FORMAT"
        else:
            block['enabled'] = False
        block['form'] = PlaceBlockForm(instance=place)
        return block

    def validate_access(self):
        if getattr(self, '_access_validated', None):
            return self._access_validated
        user = self.request.user
        place = self.object
        result = namedtuple('AccessConstraint', 'redirect, is_authorized, is_supervisor, is_family_member')
        auth_log = logging.getLogger('PasportaServo.auth')

        # Require the unauthenticated user to login in the following cases:
        #   - the place was deleted
        #   - place owner blocked unauth'd viewing
        #   - place is not visible to the public.
        if not user.is_authenticated:
            cases = [place.deleted, not place.owner.pref.public_listing, not place.visibility.visible_online_public]
            if any(cases):
                auth_log.debug("One of the conditions satisfied: "
                               "[deleted = %s, not accessible by visitors = %s, not accessible by users = %s]",
                               *cases)
                self._access_validated = result(self.handle_no_permission(), None, None, None)
                return self._access_validated

        is_authorized = user in place.authorized_users_cache(also_deleted=True, complete=False)
        is_supervisor = self.role >= SUPERVISOR
        is_family_member = getattr(user, 'profile', None) in place.family_members_cache()
        self.__dict__.setdefault('debug', {}).update(
            {'authorized': is_authorized, 'family member': is_family_member}
        )
        content_unavailable = False

        # Block access for regular authenticated users in the following cases:
        #   - the place was deleted
        #   - place is not visible to the public.
        if not is_supervisor and not self.role == OWNER:
            cases = [place.deleted, not place.visibility.visible_online_public]
            if any(cases):
                auth_log.debug("One of the conditions satisfied: "
                               "[deleted = %s, not accessible by users = %s]",
                               *cases)
                content_unavailable = True

        self._access_validated = result(content_unavailable, is_authorized, is_supervisor, is_family_member)
        return self._access_validated

    def get_template_names(self):
        if getattr(self, '_access_validated', None) and self._access_validated.redirect:
            return ['core/content_unavailable.html']
        else:
            return super().get_template_names()

    def render_to_response(self, context, **response_kwargs):
        barrier = self.validate_access()
        if barrier.redirect:
            if isinstance(barrier.redirect, HttpResponse):
                return barrier.redirect
            else:
                return super().render_to_response(
                    dict(context, object_name=self.object._meta.verbose_name), **response_kwargs
                )
        # Automatically redirect the user to the verbose view if permission granted (in authorized_users list).
        if barrier.is_authorized and not barrier.is_supervisor and not isinstance(self, PlaceDetailVerboseView):
            # We switch the class to avoid fetching all data again from the database,
            # because everything we need is already available here.
            # TODO: Combine the two views into one class.
            self.__class__ = PlaceDetailVerboseView
            return self.render_to_response(context, **response_kwargs)
        else:
            return super().render_to_response(context, **response_kwargs)

    def get_debug_data(self):
        return self.debug


class PlaceDetailVerboseView(PlaceDetailView):
    verbose_view = True

    def render_to_response(self, context, **response_kwargs):
        barrier = self.validate_access()
        if barrier.redirect:
            if isinstance(barrier.redirect, HttpResponse):
                return barrier.redirect
            else:
                return super().render_to_response(
                    dict(context, object_name=self.object._meta.verbose_name), **response_kwargs
                )
        # Automatically redirect the user to the scarce view if permission to details not granted.
        cases = [
            self.role >= OWNER,
            not self.request.user.is_authenticated,
            barrier.is_authorized,
            barrier.is_family_member,
        ]
        if any(cases):
            return super().render_to_response(context, **response_kwargs)
        else:
            return HttpResponseRedirect(reverse_lazy('place_detail', kwargs={'pk': self.kwargs['pk']}))


class PlaceBlockView(AuthMixin, PlaceMixin, generic.View):
    http_method_names = ['put']
    exact_role = OWNER

    def put(self, request, *args, **kwargs):
        place = self.get_object()
        if place.deleted:
            return JsonResponse({'result': False, 'err': {NON_FIELD_ERRORS: [_("Deleted place"), ]}})
        form = PlaceBlockForm(data=QueryDict(request.body), instance=place)
        data_correct = form.is_valid()
        response = {'result': data_correct}
        if data_correct:
            form.save()
        else:
            response.update({'err': form.errors})
        return JsonResponse(response)


class UserAuthorizeView(AuthMixin, generic.FormView):
    """
    Form view to add a user to the list of authorized users for a place,
    to be able to see the complete details.
    """
    template_name = 'hosting/place_authorized_users.html'
    form_class = UserAuthorizeForm
    exact_role = OWNER

    def dispatch(self, request, *args, **kwargs):
        self.place = get_object_or_404(Place, pk=self.kwargs['pk'])
        kwargs['auth_base'] = self.place
        return super().dispatch(request, *args, **kwargs)

    def get_permission_denied_message(self, object, context_omitted=False):
        return _("Only the owner of the place can access this page")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['place'] = self.place
        m = re.match(r'^/([a-zA-Z]+)/', self.request.GET.get('next', default=''))
        if m:
            context['back_to'] = m.group(1).lower()

        def order_by_name(user):
            try:
                return (" ".join((user.profile.first_name, user.profile.last_name)).strip()
                        or user.username).lower()
            except Profile.DoesNotExist:
                return user.username.lower()

        context['authorized_set'] = [
            (user, UserAuthorizedOnceForm(initial={'user': user.pk}, auto_id=False))
            for user
            in sorted(self.place.authorized_users_cache(also_deleted=True), key=order_by_name)
        ]
        return context

    def form_valid(self, form):
        if not form.cleaned_data['remove']:
            # For addition, "user" is the username.
            user = get_object_or_404(User, username=form.cleaned_data['user'])
            if user not in self.place.authorized_users_cache(also_deleted=True):
                self.place.authorized_users.add(user)
                if not user.email.startswith(settings.INVALID_PREFIX):
                    self.send_email(user, self.place)
        else:
            # For removal, "user" is the primary key.
            user = get_object_or_404(User, pk=form.cleaned_data['user'])
            self.place.authorized_users.remove(user)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('authorize_user', kwargs={'pk': self.kwargs['pk']})

    def send_email(self, user, place):
        config = SiteConfiguration.get_solo()
        subject = _("[Pasporta Servo] You received an Authorization")
        email_template_text = get_template('email/new_authorization.txt')
        email_template_html = get_template('email/new_authorization.html')
        email_context = {
            'site_name': config.site_name,
            'user': user,
            'place': place,
        }
        send_mail(
            subject,
            email_template_text.render(email_context),
            settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=email_template_html.render(email_context),
            fail_silently=False,
        )
