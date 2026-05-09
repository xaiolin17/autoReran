import pytest
from app.core.validation import InputValidator


@pytest.mark.unit
class TestInputValidator:
    def test_sanitize_string_removes_html(self):
        assert InputValidator.sanitize_string("<script>alert('xss')</script>") == "scriptalert('xss')/script"
    
    def test_sanitize_string_handles_none(self):
        assert InputValidator.sanitize_string(None) is None
    
    def test_validate_stock_code_valid(self):
        assert InputValidator.validate_stock_code("AAPL123") == "AAPL123"
    
    def test_validate_stock_code_invalid(self):
        with pytest.raises(ValueError, match="股票代码格式无效"):
            InputValidator.validate_stock_code("invalid!@#")
    
    def test_validate_email_valid(self):
        assert InputValidator.validate_email("test@example.com") == "test@example.com"
    
    def test_validate_email_invalid(self):
        with pytest.raises(ValueError, match="邮箱格式无效"):
            InputValidator.validate_email("invalid-email")
    
    def test_validate_username_valid(self):
        assert InputValidator.validate_username("test_user123") == "test_user123"
    
    def test_validate_username_too_short(self):
        with pytest.raises(ValueError, match="用户名长度应在3-50个字符之间"):
            InputValidator.validate_username("ab")
    
    def test_validate_username_invalid_chars(self):
        with pytest.raises(ValueError, match="用户名只能包含字母、数字、下划线和中文"):
            InputValidator.validate_username("invalid!@#")
    
    def test_validate_password_valid(self):
        assert InputValidator.validate_password("Test1234") == "Test1234"
    
    def test_validate_password_too_short(self):
        with pytest.raises(ValueError, match="密码长度至少8个字符"):
            InputValidator.validate_password("Test123")
    
    def test_validate_password_no_uppercase(self):
        with pytest.raises(ValueError, match="密码应包含大写字母"):
            InputValidator.validate_password("test1234")
    
    def test_validate_password_no_lowercase(self):
        with pytest.raises(ValueError, match="密码应包含小写字母"):
            InputValidator.validate_password("TEST1234")
    
    def test_validate_password_no_number(self):
        with pytest.raises(ValueError, match="密码应包含数字"):
            InputValidator.validate_password("TestTest")
