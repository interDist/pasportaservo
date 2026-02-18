from typing import cast

from django.urls import reverse_lazy

from pyquery import PyQuery

from core.views import AgreementRejectView, AgreementView

from .base import PageTemplate


class AgreementPage(PageTemplate):
    view_class = AgreementView
    url = reverse_lazy('agreement')
    explicit_url = {
        'en': '/account/consent/',
        'eo': '/konto/konsento/',
    }
    template = 'account/consent.html'
    redirects_unauthenticated = True

    def get_top_notice(self) -> PyQuery:
        return self.pyquery(".top-notice")

    def get_top_notice_class(self) -> str:
        return cast(str, self.get_top_notice().attr("class"))

    def get_terms_panel(self) -> PyQuery:
        return self.pyquery("#user-terms-panel")

    def get_terms_panel_class(self) -> str:
        return cast(str, self.get_terms_panel().attr("class"))

    def get_agreement_panel(self) -> PyQuery:
        return self.pyquery("#user-agreement-panel")

    def get_agreement_panel_class(self) -> str:
        return cast(str, self.get_agreement_panel().attr("class"))

    def get_policy_summary_panel(self) -> PyQuery:
        return self.pyquery("#user-agreement-panel .panel-info")

    def get_approve_button(self) -> PyQuery:
        return self.pyquery("#id_approve")

    def get_reject_button(self) -> PyQuery:
        return self.pyquery("#id_reject")

    def submit_action(self, action: str, next_url: str = None):
        data = {'action': action}
        url = str(self.url)
        if next_url:
            url += f'?next={next_url}'
        self._page = self._test_case.app.post(url, data, status='*')


class AgreementRejectPage(PageTemplate):
    view_class = AgreementRejectView
    url = reverse_lazy('agreement_reject')
    explicit_url = {
        'en': '/account/consent/reject/',
        'eo': '/konto/konsento/malakcepti/',
    }
    template = 'account/consent_rejected.html'
    redirects_unauthenticated = True

    def get_well(self) -> PyQuery:
        return self.pyquery(".well")

    def get_proceed_button(self) -> PyQuery:
        return self.pyquery("#id_proceed")

    def get_back_link(self) -> PyQuery:
        return self.pyquery("a.btn-default")

    def submit_proceed(self):
        self._page = self._test_case.app.post(str(self.url), status='*')
