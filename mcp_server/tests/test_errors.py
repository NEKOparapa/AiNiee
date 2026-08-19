from ainiee_mcp import errors


def test_all_errors_have_user_message():
    assert errors.AiNieeUnavailable("http://127.0.0.1:3388").user_message
    assert errors.AiNieeBusy("translating").user_message
    assert errors.NoProjectLoaded().user_message


def test_validation_error_lists_allowed():
    e = errors.ValidationError("bad language 'martian'", allowed={"english", "japanese"})
    assert "allowed" in e.user_message
    assert isinstance(e, errors.AiNieeError)


def test_subclass_hierarchy():
    for cls_inst in (
        errors.AiNieeUnavailable("x"),
        errors.AiNieeBusy(),
        errors.NoProjectLoaded(),
    ):
        assert isinstance(cls_inst, errors.AiNieeError)
