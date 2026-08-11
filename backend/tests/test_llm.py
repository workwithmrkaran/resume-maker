"""Provider chain and failover.

Every test here is offline: the point is the routing logic, not the models.
"""

import pytest

from app.llm import (LlmClient, LlmError, NoProvidersConfigured, Provider,
                     load_providers, should_failover)

ENV = {
    "LLM_PROVIDER_1_MODEL": "nvidia/nemotron-3-super-120b-a12b",
    "LLM_PROVIDER_1_API_KEY": "nvapi-primary",
    "LLM_PROVIDER_1_BASE_URL": "https://integrate.api.nvidia.com/v1",
    "LLM_PROVIDER_1_THINKING": "false",
    "LLM_PROVIDER_2_MODEL": "openai/gpt-oss-20b",
    "LLM_PROVIDER_2_API_KEY": "nvapi-fallback",
}


class FakeStatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def provider(name: str) -> Provider:
    return Provider(name=name, model=f"model-{name}", api_key=f"key-{name}",
                    base_url="https://example.test/v1")


class ScriptedClient(LlmClient):
    """An LlmClient whose transport is a list of scripted outcomes."""

    def __init__(self, providers, outcomes):
        super().__init__(providers)
        self.outcomes = dict(outcomes)
        self.calls = []

    def _call(self, provider, system, user, json_schema, plain=False):
        self.calls.append((provider.name, plain))
        outcome = self.outcomes[provider.name]
        if isinstance(outcome, list):
            outcome = outcome.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_providers_load_in_order():
    providers = load_providers(ENV)
    assert [p.model for p in providers] == [
        "nvidia/nemotron-3-super-120b-a12b", "openai/gpt-oss-20b",
    ]
    assert providers[1].base_url == "https://integrate.api.nvidia.com/v1"  # default


def test_incomplete_provider_block_is_skipped():
    assert load_providers({"LLM_PROVIDER_1_MODEL": "m"}) == []


def test_api_keys_are_redacted_in_descriptions():
    client = LlmClient(load_providers(ENV))
    rendered = str(client.describe())
    assert "nvapi-primary" not in rendered
    assert "nvapi-fallback" not in rendered


def test_first_provider_answers_and_second_is_untouched():
    client = ScriptedClient([provider("a"), provider("b")],
                            {"a": '{"ok":1}', "b": '{"ok":2}'})
    text, used = client.complete_json("sys", "user")
    assert text == '{"ok":1}'
    assert used.name == "a"
    assert client.calls == [("a", False)]


@pytest.mark.parametrize("status", [429, 402, 401, 500, 503])
def test_failover_when_primary_is_exhausted_or_broken(status):
    """The whole point: a spent free-tier key must not break the feature."""
    client = ScriptedClient([provider("a"), provider("b")],
                            {"a": FakeStatusError(status), "b": '{"ok":2}'})
    text, used = client.complete_json("sys", "user")
    assert used.name == "b"
    assert text == '{"ok":2}'


def test_failover_on_connection_error_without_status():
    client = ScriptedClient([provider("a"), provider("b")],
                            {"a": ConnectionError("reset"), "b": "{}"})
    _, used = client.complete_json("sys", "user")
    assert used.name == "b"


def test_empty_reply_counts_as_failure_and_fails_over():
    client = ScriptedClient([provider("a"), provider("b")],
                            {"a": "   ", "b": '{"ok":2}'})
    _, used = client.complete_json("sys", "user")
    assert used.name == "b"


def test_bad_request_does_not_burn_the_chain():
    """A 400 is our bug — the next provider would reject it identically."""
    client = ScriptedClient(
        [provider("a"), provider("b")],
        # First the structured call 400s, then the plain retry 400s too.
        {"a": [FakeStatusError(400), FakeStatusError(400)], "b": "{}"},
    )
    with pytest.raises(LlmError):
        client.complete_json("sys", "user")
    assert [name for name, _ in client.calls] == ["a", "a"]


def test_structured_output_rejection_retries_plain_on_same_provider():
    client = ScriptedClient([provider("a")],
                            {"a": [FakeStatusError(400), '{"ok":1}']})
    text, used = client.complete_json("sys", "user")
    assert text == '{"ok":1}'
    assert used.name == "a"
    assert client.calls == [("a", False), ("a", True)]


def test_all_providers_down_raises():
    client = ScriptedClient([provider("a"), provider("b")],
                            {"a": FakeStatusError(429), "b": FakeStatusError(503)})
    with pytest.raises(LlmError) as excinfo:
        client.complete_json("sys", "user")
    assert "a" in str(excinfo.value) and "b" in str(excinfo.value)


def test_no_providers_configured_is_explicit():
    with pytest.raises(NoProvidersConfigured):
        LlmClient([]).complete_json("sys", "user")


@pytest.mark.parametrize("status,expected", [
    (429, True), (402, True), (503, True), (401, True),
    (400, False), (404, False), (422, False),
])
def test_failover_classification(status, expected):
    assert should_failover(FakeStatusError(status)) is expected
