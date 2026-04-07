from discord_cli.auth.extract import parse_token_from_records


def test_parse_token_from_records_returns_plaintext_token() -> None:
    records = [
        ("other_key", "some_value"),
        ("token", '"plaintext-token-123"'),
    ]
    result = parse_token_from_records(records)
    assert result == "plaintext-token-123"


def test_parse_token_from_records_returns_none_when_missing() -> None:
    records = [("other_key", "some_value")]
    result = parse_token_from_records(records)
    assert result is None
