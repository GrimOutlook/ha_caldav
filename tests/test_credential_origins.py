"""Discovery and redirects must not expand where account credentials are sent."""

from unittest.mock import Mock, patch

import caldav
from caldav.davclient import requests
from caldav.elements import dav
import pytest
import requests_mock

from custom_components.ha_caldav.connection import (
    _resolve_bootstrap,
    build_client,
    trusted_origin,
)


@pytest.mark.parametrize(
    "target",
    [
        "https://foreign.example/cal/",
        "https://trusted.example:8443/cal/",
        "http://trusted.example/cal/",
    ],
)
def test_direct_foreign_requests_are_refused_before_the_transport(target: str) -> None:
    client = build_client("https://trusted.example/dav/", "u", "p", {})
    client.auth = requests.auth.HTTPBasicAuth("u", "p")
    with (
        patch.object(requests.Session, "request") as sent,
        pytest.raises(requests.exceptions.InvalidURL),
    ):
        client.request(target)
    sent.assert_not_called()
    client.close()


def test_foreign_home_set_cannot_receive_account_credentials() -> None:
    client = build_client("https://trusted.example/dav/", "u", "p", {})
    client.auth = requests.auth.HTTPBasicAuth("u", "p")
    principal = caldav.Principal(
        client=client, url="https://trusted.example/principal/"
    )
    principal.calendar_home_set = "https://foreign.example/cal/"
    with (
        patch.object(requests.Session, "request") as sent,
        pytest.raises(requests.exceptions.InvalidURL),
    ):
        principal.calendar_home_set.get_properties([dav.DisplayName()])
    sent.assert_not_called()
    client.close()


@pytest.mark.parametrize(
    "target",
    [
        "https://foreign.example/",
        "http://trusted.example/",
        "https://trusted.example:8443/",
    ],
)
def test_get_redirect_is_blocked_before_a_foreign_request(target: str) -> None:
    client = build_client("https://trusted.example/dav/", "u", "p", {})
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://trusted.example/dav/",
            status_code=302,
            headers={"Location": target},
        )
        foreign = mock.get(target, text="must not be requested")
        with pytest.raises(requests.exceptions.InvalidURL):
            client.request("https://trusted.example/dav/")
        assert foreign.call_count == 0
    client.close()


def test_bootstrap_does_not_forward_a_client_certificate_to_another_origin() -> None:
    with patch("custom_components.ha_caldav.connection.requests.request") as request:
        request.return_value.status_code = 302
        request.return_value.headers = {"Location": "https://foreign.example/dav/"}
        assert (
            _resolve_bootstrap(
                "https://trusted.example/.well-known/caldav",
                {"ssl_cert": "/client.pem"},
            )
            is None
        )
    assert request.call_count == 1
    assert request.call_args.kwargs["allow_redirects"] is False


def test_bootstrap_follows_only_explicitly_trusted_icloud_shards() -> None:
    source = "https://caldav.icloud.com/.well-known/caldav"
    target = "https://p42-caldav.icloud.com/dav/"
    with patch(
        "custom_components.ha_caldav.connection.requests.request",
        side_effect=[
            Mock(status_code=302, headers={"Location": target}, url=source, history=[]),
            Mock(status_code=200, headers={}, url=target, history=[]),
        ],
    ) as request:
        assert _resolve_bootstrap(source, {}) == target
    assert [call.args[1] for call in request.call_args_list] == [source, target]


@pytest.mark.parametrize("host", ["caldav.icloud.com", "p42-caldav.icloud.com"])
def test_icloud_shard_discovery_is_explicitly_trusted(host: str) -> None:
    assert trusted_origin("https://caldav.icloud.com/", f"https://{host}/dav/")


@pytest.mark.parametrize(
    "target",
    [
        "https://caldav.icloud.com.evil.example/",
        "https://evil-icloud.com/",
        "https://p42-caldav.icloud.com:8443/",
        "http://p42-caldav.icloud.com/",
    ],
)
def test_icloud_exception_does_not_allow_lookalikes_ports_or_downgrades(
    target: str,
) -> None:
    assert not trusted_origin("https://caldav.icloud.com/", target)
