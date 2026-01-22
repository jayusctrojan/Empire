"""
Input Validation Tests - Task 41.4
Comprehensive tests for security validators
"""

import pytest
from fastapi import HTTPException

from app.validators.security import (
    validate_path_traversal,
    validate_sql_injection,
    validate_xss,
    sanitize_metadata,
    validate_filename,
    validate_email_domain
)


class TestPathTraversalValidation:
    """Test path traversal prevention"""

    def test_valid_paths_pass(self):
        """Test that safe paths are allowed"""
        safe_paths = [
            "documents/report.pdf",
            "users/123/profile.jpg",
            "data/2024/january/stats.csv",
            "folder/subfolder/file.txt",
        ]

        for path in safe_paths:
            result = validate_path_traversal(path)
            assert result == path

    def test_parent_directory_blocked(self):
        """Test ../ is blocked"""
        with pytest.raises(HTTPException) as exc:
            validate_path_traversal("../../../etc/passwd")

        assert exc.value.status_code == 400
        assert "path" in str(exc.value.detail).lower()

    def test_current_directory_blocked(self):
        """Test ./ is blocked"""
        with pytest.raises(HTTPException):
            validate_path_traversal("./config/secrets.json")

    def test_home_directory_blocked(self):
        """Test ~/ is blocked"""
        with pytest.raises(HTTPException):
            validate_path_traversal("~/private/keys.pem")

    def test_null_byte_blocked(self):
        """Test null byte injection is blocked"""
        with pytest.raises(HTTPException):
            validate_path_traversal("file.txt\x00.jpg")

        with pytest.raises(HTTPException):
            validate_path_traversal("file%00.txt")

    def test_url_encoded_traversal_blocked(self):
        """Test URL-encoded path traversal is blocked"""
        # %2e%2e = ..
        with pytest.raises(HTTPException):
            validate_path_traversal("%2e%2e/passwd")

        # %252e = double-encoded .
        with pytest.raises(HTTPException):
            validate_path_traversal("%252e%252e/passwd")

    def test_backslash_blocked(self):
        """Test Windows-style backslash is blocked"""
        with pytest.raises(HTTPException):
            validate_path_traversal("..\\..\\windows\\system32")

    def test_empty_path_returns_empty(self):
        """Test empty path is allowed"""
        result = validate_path_traversal("")
        assert result == ""

    def test_none_path_returns_none(self):
        """Test None path is allowed"""
        result = validate_path_traversal(None)
        assert result is None


class TestSQLInjectionValidation:
    """Test SQL injection detection"""

    def test_valid_input_passes(self):
        """Test that safe input is allowed"""
        safe_inputs = [
            "john_doe",
            "user@example.com",
            "Product Name 123",
            "description with spaces",
        ]

        for inp in safe_inputs:
            result = validate_sql_injection(inp)
            assert result == inp

    def test_union_select_blocked(self):
        """Test UNION SELECT is detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("admin' UNION SELECT * FROM passwords--")

    def test_drop_table_blocked(self):
        """Test DROP TABLE is detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("'; DROP TABLE users;--")

    def test_or_equals_blocked(self):
        """Test OR 1=1 pattern is detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("admin' OR '1'='1")

        with pytest.raises(HTTPException):
            validate_sql_injection("admin' OR 1=1--")

    def test_insert_into_blocked(self):
        """Test INSERT INTO is detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("'; INSERT INTO admins VALUES ('hacker', 'admin')--")

    def test_update_set_blocked(self):
        """Test UPDATE SET is detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("'; UPDATE users SET role='admin' WHERE id=1--")

    def test_delete_from_blocked(self):
        """Test DELETE FROM is detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("'; DELETE FROM users WHERE 1=1--")

    def test_sql_comments_blocked(self):
        """Test SQL comment patterns are detected"""
        with pytest.raises(HTTPException):
            validate_sql_injection("admin'--")

        with pytest.raises(HTTPException):
            validate_sql_injection("admin' #")

        with pytest.raises(HTTPException):
            validate_sql_injection("admin' /* comment */")

    def test_empty_string_passes(self):
        """Test empty string is allowed"""
        result = validate_sql_injection("")
        assert result == ""

    def test_none_passes(self):
        """Test None is allowed"""
        result = validate_sql_injection(None)
        assert result is None


class TestXSSValidation:
    """Test XSS attack prevention"""

    def test_valid_html_text_passes(self):
        """Test that safe text is allowed"""
        safe_texts = [
            "Hello, World!",
            "Email: user@example.com",
            "Price: $99.99",
            "Numbers: 123-456-7890",
        ]

        for text in safe_texts:
            result = validate_xss(text, strict=True)
            assert result == text

    def test_script_tag_blocked(self):
        """Test <script> tags are detected"""
        with pytest.raises(HTTPException):
            validate_xss("<script>alert('XSS')</script>", strict=True)

        with pytest.raises(HTTPException):
            validate_xss("<SCRIPT>alert('XSS')</SCRIPT>", strict=True)

    def test_javascript_protocol_blocked(self):
        """Test javascript: protocol is detected"""
        with pytest.raises(HTTPException):
            validate_xss("<a href='javascript:alert(1)'>Click</a>", strict=True)

    def test_event_handlers_blocked(self):
        """Test event handler attributes are detected"""
        with pytest.raises(HTTPException):
            validate_xss("<img src=x onerror=alert('XSS')>", strict=True)

        with pytest.raises(HTTPException):
            validate_xss("<body onload=alert('XSS')>", strict=True)

        with pytest.raises(HTTPException):
            validate_xss("<div onclick=alert('XSS')>", strict=True)

    def test_iframe_blocked(self):
        """Test <iframe> tags are detected"""
        with pytest.raises(HTTPException):
            validate_xss("<iframe src='evil.com'>", strict=True)

    def test_object_embed_blocked(self):
        """Test <object> and <embed> tags are detected"""
        with pytest.raises(HTTPException):
            validate_xss("<object data='evil.swf'>", strict=True)

        with pytest.raises(HTTPException):
            validate_xss("<embed src='evil.swf'>", strict=True)

    def test_svg_onload_blocked(self):
        """Test SVG with onload is detected"""
        with pytest.raises(HTTPException):
            validate_xss("<svg onload=alert('XSS')>", strict=True)

    def test_eval_blocked(self):
        """Test eval() is detected"""
        with pytest.raises(HTTPException):
            validate_xss("eval('malicious code')", strict=True)

    def test_sanitization_mode(self):
        """Test strict=False sanitizes instead of rejecting"""
        dirty_input = "Hello <script>alert('XSS')</script> World"
        clean_output = validate_xss(dirty_input, strict=False)

        # Should remove <script> but keep safe text
        assert "<script>" not in clean_output
        assert "Hello" in clean_output
        assert "World" in clean_output

    def test_sanitization_removes_all_patterns(self):
        """Test sanitization removes multiple XSS patterns"""
        dirty_input = """
            Text <script>alert(1)</script>
            <img src=x onerror=alert(2)>
            <iframe src='evil.com'>
            javascript:alert(3)
        """

        clean_output = validate_xss(dirty_input, strict=False)

        assert "<script>" not in clean_output
        assert "onerror" not in clean_output
        assert "<iframe>" not in clean_output
        assert "javascript:" not in clean_output

    def test_empty_string_passes(self):
        """Test empty string is allowed"""
        result = validate_xss("", strict=True)
        assert result == ""

    def test_none_passes(self):
        """Test None is allowed"""
        result = validate_xss(None, strict=True)
        assert result is None


class TestMetadataSanitization:
    """Test metadata sanitization"""

    def test_clean_metadata_unchanged(self):
        """Test that clean metadata passes through"""
        clean_meta = {
            "title": "Document Title",
            "author": "John Doe",
            "tags": ["tag1", "tag2"],
            "count": 42,
            "nested": {
                "field1": "value1",
                "field2": "value2"
            }
        }

        result = sanitize_metadata(clean_meta, strict=False)
        assert result == clean_meta

    def test_xss_in_strings_sanitized(self):
        """Test XSS in string values is sanitized"""
        dirty_meta = {
            "title": "Title <script>alert('XSS')</script>",
            "description": "<img src=x onerror=alert(1)>"
        }

        clean_meta = sanitize_metadata(dirty_meta, strict=False)

        assert "<script>" not in str(clean_meta)
        assert "onerror" not in str(clean_meta)
        assert "Title" in clean_meta["title"]

    def test_nested_metadata_sanitized(self):
        """Test nested dictionaries are sanitized recursively"""
        dirty_meta = {
            "level1": {
                "level2": {
                    "level3": "<script>alert('deep XSS')</script>"
                }
            }
        }

        clean_meta = sanitize_metadata(dirty_meta, strict=False)

        assert "<script>" not in str(clean_meta)

    def test_list_items_sanitized(self):
        """Test list items are sanitized"""
        dirty_meta = {
            "tags": [
                "safe_tag",
                "<script>alert('XSS')</script>",
                "another_safe_tag"
            ]
        }

        clean_meta = sanitize_metadata(dirty_meta, strict=False)

        assert "<script>" not in str(clean_meta["tags"])
        assert "safe_tag" in clean_meta["tags"]
        assert "another_safe_tag" in clean_meta["tags"]

    def test_path_traversal_in_keys_blocked(self):
        """Test path traversal in metadata keys is blocked"""
        dirty_meta = {
            "../../../etc/passwd": "value"
        }

        with pytest.raises(HTTPException):
            sanitize_metadata(dirty_meta, strict=True)

    def test_sql_injection_in_keys_blocked(self):
        """Test SQL injection in metadata keys is blocked"""
        dirty_meta = {
            "key' OR '1'='1": "value"
        }

        with pytest.raises(HTTPException):
            sanitize_metadata(dirty_meta, strict=True)

    def test_empty_metadata_passes(self):
        """Test empty metadata is allowed"""
        result = sanitize_metadata({}, strict=False)
        assert result == {}

    def test_none_metadata_passes(self):
        """Test None metadata is allowed"""
        result = sanitize_metadata(None, strict=False)
        assert result is None


class TestFilenameValidation:
    """Test filename validation"""

    def test_valid_filenames_pass(self):
        """Test that safe filenames are allowed"""
        valid_filenames = [
            "document.pdf",
            "report_2024.docx",
            "image-file.png",
            "data.csv",
            "archive.tar.gz",
        ]

        for filename in valid_filenames:
            result = validate_filename(filename)
            assert result == filename

    def test_path_traversal_blocked(self):
        """Test path traversal in filename is blocked"""
        with pytest.raises(HTTPException):
            validate_filename("../../../etc/passwd")

    def test_forbidden_characters_blocked(self):
        """Test forbidden characters are blocked"""
        forbidden = ['<', '>', ':', '"', '|', '?', '*']

        for char in forbidden:
            with pytest.raises(HTTPException):
                validate_filename(f"file{char}.txt")

    def test_max_length_enforced(self):
        """Test filename length limit (255 chars)"""
        # Valid: exactly 255 chars
        long_filename = "a" * 251 + ".txt"  # 255 total
        result = validate_filename(long_filename)
        assert result == long_filename

        # Invalid: 256 chars
        too_long = "a" * 252 + ".txt"  # 256 total
        with pytest.raises(HTTPException):
            validate_filename(too_long)

    def test_empty_filename_blocked(self):
        """Test empty filename is rejected"""
        with pytest.raises(HTTPException):
            validate_filename("")

    def test_none_filename_blocked(self):
        """Test None filename is rejected"""
        with pytest.raises(HTTPException):
            validate_filename(None)


class TestEmailDomainValidation:
    """Test email domain allowlist"""

    def test_allowed_domain_passes(self):
        """Test email from allowed domain passes"""
        result = validate_email_domain(
            "user@example.com",
            allowed_domains=["example.com", "company.com"]
        )
        assert result is True

    def test_disallowed_domain_blocked(self):
        """Test email from disallowed domain is blocked"""
        with pytest.raises(HTTPException):
            validate_email_domain(
                "user@evil.com",
                allowed_domains=["example.com", "company.com"]
            )

    def test_case_insensitive_matching(self):
        """Test domain matching is case-insensitive"""
        result = validate_email_domain(
            "User@EXAMPLE.COM",
            allowed_domains=["example.com"]
        )
        assert result is True

    def test_no_allowlist_allows_all(self):
        """Test no allowlist allows any domain"""
        result = validate_email_domain(
            "user@any-domain.com",
            allowed_domains=None
        )
        assert result is True

        result = validate_email_domain(
            "user@another.org",
            allowed_domains=[]
        )
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
