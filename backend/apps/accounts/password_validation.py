import re
from django.core.exceptions import ValidationError


class AlphanumericPasswordValidator:
    def validate(self,password,user=None):
        if not 6<=len(password)<=128 or not re.fullmatch(r'[A-Za-z0-9]+',password) or not re.search(r'[A-Za-z]',password) or not re.search(r'[0-9]',password):
            raise ValidationError(self.get_help_text(),code='password_policy')

    def get_help_text(self):
        return '密码需6至128位，仅含英文字母和数字，且两者都包含。'
