"""P00-005 acceptance: unified test entry works; core smoke."""
from pathlib import Path


def test_workspace_layout(temp_workspace):
    from app.core.paths import downloads_tmp_dir, final_dir, intermediate_dir, raw_root, vault_dir

    for p in (raw_root(), downloads_tmp_dir(), vault_dir(), intermediate_dir("b1"), final_dir("b1")):
        assert Path(p).exists()
    assert (temp_workspace / "raw" / ".raw_immutable").exists()


def test_error_codes():
    from app.core.errors import MetisError

    e = MetisError("INVALID_DOWNLOAD_CONTENT", provider_id="p1")
    d = e.to_dict()
    assert d["error_code"] == "INVALID_DOWNLOAD_CONTENT"
    assert d["retryable"] is False


def test_logging_redaction(temp_workspace, caplog):
    import logging

    from app.core.logging import get_logger, redact, register_secret

    register_secret("S3cr3t-Token-Value")
    assert "S3cr3t-Token-Value" not in redact("cookie=S3cr3t-Token-Value; rest")
    assert "***MASKED***" in redact("password=hunter2000")
    logger = get_logger("test")
    with caplog.at_level(logging.INFO):
        logger.info_ctx("attempt", password="abcdef123456")
    assert "abcdef123456" not in caplog.text
